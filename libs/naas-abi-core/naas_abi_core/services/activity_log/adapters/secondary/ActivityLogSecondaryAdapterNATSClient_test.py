import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread
from unittest.mock import AsyncMock

import nats
import pytest
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
    ActivityLogSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)
from naas_abi_core.services.activity_log.tests.activity_log__secondary_adapter__generic_test import (
    GenericActivityLogSecondaryAdapterTest,
)

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    ActivityLogSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = ActivityLogSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = ActivityLogSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# ActivityLogPrimaryAdapterNATS encodes CallError.
# ---------------------------------------------------------------------------


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

    monkeypatch.setattr("naas_abi_core.engine.nats_rpc.issue_service_token", fake_issue)

    client = ActivityLogSecondaryAdapterNATSClient(
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

    monkeypatch.setattr("naas_abi_core.engine.nats_rpc.issue_service_token", fake_issue)

    client = ActivityLogSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real ActivityLogPrimaryAdapterNATS
# wrapping a real ActivityLogSqliteAdapter, and the client talking to it over
# the wire. Skips cleanly when Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs ActivityLogPrimaryAdapterNATS on its own background event loop
    for as long as a test needs it -- the server-side mirror of the client's
    own background loop, since nats-py has no synchronous API on either
    side."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: ActivityLogPrimaryAdapterNATS | None = None

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

        thread = Thread(
            target=_run, daemon=True, name="activity-log-nats-primary-test-loop"
        )
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = ActivityLogPrimaryAdapterNATS(
            self._wrapped_adapter, self._jwt_secret
        )
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
        # pattern in NATSJetStreamAdapter_test.py /
        # ObjectStorageSecondaryAdapterNATSClient_test.py.
        from testcontainers.core.container import DockerContainer

        with DockerContainer("nats:2-alpine").with_exposed_ports(4222) as container:
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
class TestActivityLogSecondaryAdapterNATSClient(GenericActivityLogSecondaryAdapterTest):
    """Round-trips the shared adapter contract through a real primary adapter
    (wrapping a real SQLite adapter) and the real client, over a live NATS
    server."""

    @pytest.fixture
    def adapter_class(self):
        return ActivityLogSecondaryAdapterNATSClient

    @pytest.fixture
    def adapter(self, nats_url, tmp_path):
        wrapped = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
        server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
        server.start()

        client = ActivityLogSecondaryAdapterNATSClient(
            nats_url=nats_url,
            jwt_secret=JWT_SECRET,
            service_identity="api",
            timeout_seconds=10.0,
        )
        yield client
        client.close()
        server.stop()
        wrapped.shutdown()


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url, tmp_path):
    wrapped = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = ActivityLogSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.record(ActivityEvent(actor_id="user:1", event_type="x"))
    finally:
        client.close()
        server.stop()
        wrapped.shutdown()
