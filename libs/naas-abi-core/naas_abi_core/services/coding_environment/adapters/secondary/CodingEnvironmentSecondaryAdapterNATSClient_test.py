import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread
from unittest.mock import AsyncMock

import naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient as _client_module
import nats
import pytest
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_RUNNING,
    PHASE_STOPPED,
    AccessDeniedError,
    AgentNeverConnectedError,
    ProvisionFailedError,
    ProvisionTimeoutError,
    QuotaExceededError,
    TemplateNotFoundError,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
)
from naas_abi_core.services.coding_environment.tests.coding_environment__secondary_adapter__generic_test import (
    GenericCodingEnvironmentSecondaryAdapterTest,
)

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    CodingEnvironmentSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = CodingEnvironmentSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = CodingEnvironmentSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Optional local-only methods are simply absent from this client -- there is
# no NATS subject for any of them (see the module docstring).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method_name",
    [
        "wait_until_ready",
        "get_workspace_ui_url",
        "get_runtime_binding",
        "get_harness_binding",
    ],
)
def test_optional_local_only_methods_are_not_defined(method_name):
    client = CodingEnvironmentSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert not hasattr(client, method_name)


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# CodingEnvironmentPrimaryAdapterNATS encodes CallError.code, including the
# optional status round trip.
# ---------------------------------------------------------------------------

_ERROR_MAPPING = [
    ("PROVISION_FAILED", ProvisionFailedError),
    ("PROVISION_TIMEOUT", ProvisionTimeoutError),
    ("AGENT_NEVER_CONNECTED", AgentNeverConnectedError),
    ("TEMPLATE_NOT_FOUND", TemplateNotFoundError),
    ("WORKSPACE_NOT_FOUND", WorkspaceNotFoundError),
    ("WORKSPACE_NAME_CONFLICT", WorkspaceNameConflictError),
    ("QUOTA_EXCEEDED", QuotaExceededError),
    ("ACCESS_DENIED", AccessDeniedError),
]


@pytest.mark.parametrize(("code", "exc_cls"), _ERROR_MAPPING)
def test_raise_for_error_maps_code_to_exception_with_status(code, exc_cls):
    with pytest.raises(exc_cls) as excinfo:
        _raise_for_error(
            common_pb2.CallError(code=code, message="x", status=404)
        )
    assert excinfo.value.status == 404


@pytest.mark.parametrize(("code", "exc_cls"), _ERROR_MAPPING)
def test_raise_for_error_maps_code_to_exception_without_status(code, exc_cls):
    with pytest.raises(exc_cls) as excinfo:
        _raise_for_error(common_pb2.CallError(code=code, message="x"))
    assert excinfo.value.status is None


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

    client = CodingEnvironmentSecondaryAdapterNATSClient(
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

    client = CodingEnvironmentSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real
# CodingEnvironmentPrimaryAdapterNATS wrapping a real InMemoryAdapter, and
# the client talking to it over the wire. Skips cleanly when
# Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs CodingEnvironmentPrimaryAdapterNATS on its own background event
    loop for as long as a test needs it -- the server-side mirror of the
    client's own background loop, since nats-py has no synchronous API on
    either side."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: CodingEnvironmentPrimaryAdapterNATS | None = None

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
            target=_run, daemon=True, name="coding-environment-nats-primary-test-loop"
        )
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = CodingEnvironmentPrimaryAdapterNATS(
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
        # pattern in NATSJetStreamAdapter_test.py / object_storage's own
        # ObjectStorageSecondaryAdapterNATSClient_test.py.
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
class TestCodingEnvironmentSecondaryAdapterNATSClient(
    GenericCodingEnvironmentSecondaryAdapterTest
):
    """Gates the generic (method-existence) contract behind a real NATS
    container being reachable, matching the shape of the other
    coding_environment adapters' contract tests."""

    @pytest.fixture
    def adapter_class(self, nats_url):
        return CodingEnvironmentSecondaryAdapterNATSClient


@pytest.mark.integration
def test_full_lifecycle_round_trips_through_real_nats(nats_url):
    wrapped = InMemoryAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()

    client = CodingEnvironmentSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    try:
        user_id = client.ensure_user(
            external_id="ext-1", email="a@b.com", username="alice"
        )
        assert user_id

        templates = client.list_templates()
        assert templates[0].id == "tmpl-default"

        status = client.provision(
            user_id=user_id, template_id="tmpl-default", name="dev", params={"cpu": "2"}
        )
        assert status.phase == PHASE_RUNNING
        assert status.agent_ready is True

        fetched = client.get_status(workspace_id=status.id)
        assert fetched.id == status.id

        environments = client.list_environments(user_id=user_id)
        assert [e.id for e in environments] == [status.id]

        access = client.get_access(
            workspace_id=status.id, user_id=user_id, app_slug="code-server"
        )
        assert access.token is not None

        stopped = client.stop(workspace_id=status.id)
        assert stopped.phase == PHASE_STOPPED

        started = client.start(workspace_id=status.id)
        assert started.phase == PHASE_RUNNING

        logs = client.get_logs(workspace_id=status.id)
        assert logs

        client.delete(workspace_id=status.id)
        with pytest.raises(WorkspaceNotFoundError):
            client.get_status(workspace_id=status.id)
    finally:
        client.close()
        server.stop()


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url):
    wrapped = InMemoryAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = CodingEnvironmentSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.list_templates()
    finally:
        client.close()
        server.stop()
