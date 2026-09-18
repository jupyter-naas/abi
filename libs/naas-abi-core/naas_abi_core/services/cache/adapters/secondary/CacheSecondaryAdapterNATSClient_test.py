import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread
from unittest.mock import AsyncMock

import naas_abi_core.services.cache.adapters.secondary.CacheSecondaryAdapterNATSClient as _client_module
import nats
import pytest
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.cache.adapters.primary.cache__primary_adapter__NATS import (
    CachePrimaryAdapterNATS,
)
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)
from naas_abi_core.services.cache.adapters.secondary.CacheSecondaryAdapterNATSClient import (
    CacheSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
)

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    CacheSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = CacheSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = CacheSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# CachePrimaryAdapterNATS encodes CallError.code.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_cache_not_found():
    with pytest.raises(CacheNotFoundError):
        _raise_for_error(common_pb2.CallError(code="CACHE_NOT_FOUND", message="x"))


def test_raise_for_error_maps_cache_expired():
    with pytest.raises(CacheExpiredError):
        _raise_for_error(common_pb2.CallError(code="CACHE_EXPIRED", message="x"))


def test_raise_for_error_maps_unknown_code_to_runtime_error():
    with pytest.raises(RuntimeError, match="INTERNAL"):
        _raise_for_error(common_pb2.CallError(code="INTERNAL", message="boom"))


def test_raise_for_error_maps_unauthenticated_to_runtime_error():
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        _raise_for_error(
            common_pb2.CallError(code="UNAUTHENTICATED", message="no token")
        )


# ---------------------------------------------------------------------------
# Token issuance: issued once, reused, reissued only close to expiry.
# ---------------------------------------------------------------------------


def test_token_is_issued_once_and_reused(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr(_client_module, "issue_service_token", fake_issue)

    client = CacheSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )

    assert client._current_token() == "token-1"
    assert client._current_token() == "token-1"
    assert calls == ["api"]


def test_token_is_reissued_when_close_to_expiry(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr(_client_module, "issue_service_token", fake_issue)

    client = CacheSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real CachePrimaryAdapterNATS
# wrapping a real CacheFSAdapter, and the client talking to it over the
# wire. Skips cleanly when Docker/testcontainers is unavailable.
#
# There is no existing generic ICacheAdapter contract test file (unlike
# object_storage), so this round-trips every ICacheAdapter method directly
# here rather than retrofitting a generic-contract-test framework that
# doesn't exist yet for cache.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs CachePrimaryAdapterNATS on its own background event loop for as
    long as a test needs it -- the server-side mirror of the client's own
    background loop, since nats-py has no synchronous API on either side."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: CachePrimaryAdapterNATS | None = None

    def start(self) -> None:
        ready = ThreadingEvent()
        errors: list[BaseException] = []

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(self._start_async())
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                ready.set()
            if not errors:
                loop.run_forever()
            loop.close()

        thread = Thread(target=_run, daemon=True, name="cache-nats-primary-test-loop")
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = CachePrimaryAdapterNATS(self._wrapped_adapter, self._jwt_secret)
        await self._primary.start(self._nc)

    def stop(self) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._stop_async(), loop)
            future.result(timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            # Best-effort teardown of a test-only harness -- the loop gets
            # stopped and the thread joined regardless, right below.
            logger.debug(f"test harness: error stopping NATS test server: {exc}")
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    async def _stop_async(self) -> None:
        if self._primary is not None:
            await self._primary.stop()
        if self._nc is not None:
            await self._nc.close()


@pytest.fixture(scope="session")
def nats_url():
    try:
        # Imported here, not at module level: testcontainers is a dev-only
        # dependency, absent from environments that don't run
        # `uv sync --all-extras` for this package -- see the identical
        # pattern in NATSJetStreamAdapter_test.py / ObjectStorageSecondaryAdapterNATSClient_test.py.
        from testcontainers.core.container import DockerContainer

        with (
            DockerContainer("nats:2-alpine").with_exposed_ports(4222)
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(4222)
            url = f"nats://{host}:{port}"

            deadline = time.time() + 30
            last_exc: Exception | None = None

            async def _probe() -> None:
                nc = await nats.connect(url, connect_timeout=2)
                await nc.close()

            while time.time() < deadline:
                try:
                    asyncio.run(_probe())
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    time.sleep(0.5)
            else:
                pytest.fail(f"NATS container did not become ready in time: {last_exc}")

            yield url
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.mark.integration
class TestCacheSecondaryAdapterNATSClient:
    """Round-trips every ICacheAdapter method through a real primary adapter
    (wrapping a real filesystem adapter) and the real client, over a live
    NATS server."""

    @pytest.fixture
    def client(self, nats_url, tmp_path):
        wrapped = CacheFSAdapter(str(tmp_path))
        server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
        server.start()

        client = CacheSecondaryAdapterNATSClient(
            nats_url=nats_url,
            jwt_secret=JWT_SECRET,
            service_identity="api",
            timeout_seconds=10.0,
        )
        yield client
        client.close()
        server.stop()

    def test_set_then_get_round_trips_cached_data(self, client):
        client.set("k1", CachedData(key="k1", data="hello", data_type=DataType.TEXT))

        result = client.get("k1")

        assert result.key == "k1"
        assert result.data == "hello"
        assert result.data_type == DataType.TEXT

    def test_get_missing_key_raises_cache_not_found(self, client):
        with pytest.raises(CacheNotFoundError):
            client.get("missing")

    def test_exists_reflects_presence(self, client):
        assert client.exists("k2") is False

        client.set("k2", CachedData(key="k2", data="v", data_type=DataType.TEXT))

        assert client.exists("k2") is True

    def test_set_if_absent_writes_once_then_refuses(self, client):
        wrote_first = client.set_if_absent(
            "k3", CachedData(key="k3", data="v1", data_type=DataType.TEXT)
        )
        wrote_second = client.set_if_absent(
            "k3", CachedData(key="k3", data="v2", data_type=DataType.TEXT)
        )

        assert wrote_first is True
        assert wrote_second is False
        assert client.get("k3").data == "v1"

    def test_delete_removes_entry(self, client):
        client.set("k4", CachedData(key="k4", data="v", data_type=DataType.TEXT))

        client.delete("k4")

        assert client.exists("k4") is False

    def test_delete_missing_key_raises_cache_not_found(self, client):
        with pytest.raises(CacheNotFoundError):
            client.delete("missing-delete")

    @pytest.mark.parametrize("data_type", list(DataType))
    def test_data_type_round_trips_for_every_value(self, client, data_type):
        key = f"dt-{data_type.value}"
        client.set(key, CachedData(key=key, data="payload", data_type=data_type))

        result = client.get(key)

        assert result.data_type == data_type
        assert result.data == "payload"


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url, tmp_path):
    wrapped = CacheFSAdapter(str(tmp_path))
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = CacheSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.set("key", CachedData(key="key", data="v", data_type=DataType.TEXT))
    finally:
        client.close()
        server.stop()
