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
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
    SecretSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)

JWT_SECRET = "test-shared-secret"


class _InMemorySecretAdapter(ISecretAdapter):
    def __init__(self) -> None:
        self.secrets: dict[str, str | None] = {}

    def get(self, key: str, default=None):
        return self.secrets.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.secrets[key] = value

    def remove(self, key: str) -> None:
        self.secrets.pop(key, None)

    def list(self) -> dict[str, str | None]:
        return dict(self.secrets)


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    SecretSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = SecretSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = SecretSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# SecretPrimaryAdapterNATS encodes CallError.code.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_secret_auth_failed():
    error = common_pb2.CallError(code="SECRET_AUTH_FAILED", message="nope")
    with pytest.raises(SecretAuthenticationError):
        _raise_for_error(error)


def test_raise_for_error_maps_unknown_code_to_runtime_error():
    error = common_pb2.CallError(code="SOMETHING_ELSE", message="huh")
    with pytest.raises(RuntimeError, match="SOMETHING_ELSE"):
        _raise_for_error(error)


def test_raise_for_error_maps_unauthenticated_to_runtime_error():
    error = common_pb2.CallError(code="UNAUTHENTICATED", message="no token")
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        _raise_for_error(error)


# ---------------------------------------------------------------------------
# Token issuance / reissue.
# ---------------------------------------------------------------------------


def test_token_is_issued_once_and_reused(monkeypatch):
    issued = []

    def _fake_issue(identity, secret):
        issued.append(identity)
        return f"token-{len(issued)}"

    monkeypatch.setattr(
        "naas_abi_core.engine.nats_rpc.issue_service_token", _fake_issue
    )
    client = SecretSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )

    first = client._current_token()
    second = client._current_token()

    assert first == second == "token-1"
    assert issued == ["api"]


def test_token_is_reissued_when_close_to_expiry(monkeypatch):
    issued = []

    def _fake_issue(identity, secret):
        issued.append(identity)
        return f"token-{len(issued)}"

    monkeypatch.setattr(
        "naas_abi_core.engine.nats_rpc.issue_service_token", _fake_issue
    )
    client = SecretSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client._current_token()
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    second_token = client._current_token()

    assert second_token == "token-2"
    assert issued == ["api", "api"]


# ---------------------------------------------------------------------------
# Real live round trip against a real NATS server (testcontainers).
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs a real SecretPrimaryAdapterNATS on its own background loop,
    mirroring the identical test harness in every sibling
    *SecondaryAdapterNATSClient_test.py."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: SecretPrimaryAdapterNATS | None = None

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

        thread = Thread(target=_run, daemon=True, name="secret-nats-primary-test-loop")
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = SecretPrimaryAdapterNATS(
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
def test_get_set_remove_list_round_trip_through_real_nats(nats_url):
    wrapped = _InMemorySecretAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = SecretSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    try:
        assert client.get("NOPE") is None
        assert client.get("NOPE", "fallback") == "fallback"
        client.set("API_KEY", "sk-live-123")
        assert client.get("API_KEY") == "sk-live-123"
        assert client.list() == {"API_KEY": "sk-live-123"}
        client.remove("API_KEY")
        assert client.get("API_KEY") is None
    finally:
        client.close()
        server.stop()


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url):
    wrapped = _InMemorySecretAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = SecretSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.get("K")
    finally:
        client.close()
        server.stop()
