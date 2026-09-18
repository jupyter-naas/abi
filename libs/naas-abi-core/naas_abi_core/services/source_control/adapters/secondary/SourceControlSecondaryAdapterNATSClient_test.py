import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread
from unittest.mock import AsyncMock

import naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient as _client_module
import nats
import pytest
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    BranchNameConflictError,
    BranchNotFoundError,
    MergeBlockedError,
    MergeConflictError,
    ProposalNotFoundError,
    RepoNotFoundError,
    ValidationError,
)
from naas_abi_core.services.source_control.tests.source_control__secondary_adapter__generic_test import (
    GenericSourceControlSecondaryAdapterTest,
)

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    SourceControlSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = SourceControlSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = SourceControlSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# SourceControlPrimaryAdapterNATS encodes CallError.code.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_repo_not_found():
    with pytest.raises(RepoNotFoundError):
        _raise_for_error(common_pb2.CallError(code="REPO_NOT_FOUND", message="x"))


def test_raise_for_error_maps_branch_not_found():
    with pytest.raises(BranchNotFoundError):
        _raise_for_error(common_pb2.CallError(code="BRANCH_NOT_FOUND", message="x"))


def test_raise_for_error_maps_proposal_not_found():
    with pytest.raises(ProposalNotFoundError):
        _raise_for_error(common_pb2.CallError(code="PROPOSAL_NOT_FOUND", message="x"))


def test_raise_for_error_maps_branch_name_conflict():
    with pytest.raises(BranchNameConflictError):
        _raise_for_error(common_pb2.CallError(code="BRANCH_NAME_CONFLICT", message="x"))


def test_raise_for_error_maps_merge_conflict():
    with pytest.raises(MergeConflictError):
        _raise_for_error(common_pb2.CallError(code="MERGE_CONFLICT", message="x"))


def test_raise_for_error_maps_merge_blocked():
    with pytest.raises(MergeBlockedError):
        _raise_for_error(common_pb2.CallError(code="MERGE_BLOCKED", message="x"))


def test_raise_for_error_maps_access_denied():
    with pytest.raises(AccessDeniedError):
        _raise_for_error(common_pb2.CallError(code="ACCESS_DENIED", message="x"))


def test_raise_for_error_maps_validation_error():
    with pytest.raises(ValidationError):
        _raise_for_error(common_pb2.CallError(code="VALIDATION_ERROR", message="x"))


def test_raise_for_error_maps_unknown_code_to_runtime_error():
    with pytest.raises(RuntimeError, match="INTERNAL"):
        _raise_for_error(common_pb2.CallError(code="INTERNAL", message="boom"))


def test_raise_for_error_maps_unauthenticated_to_runtime_error():
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        _raise_for_error(
            common_pb2.CallError(code="UNAUTHENTICATED", message="no token")
        )


def test_raise_for_error_carries_status_when_present():
    with pytest.raises(RepoNotFoundError) as exc_info:
        _raise_for_error(
            common_pb2.CallError(code="REPO_NOT_FOUND", message="x", status=404)
        )
    assert exc_info.value.status == 404


def test_raise_for_error_leaves_status_none_when_absent():
    with pytest.raises(RepoNotFoundError) as exc_info:
        _raise_for_error(common_pb2.CallError(code="REPO_NOT_FOUND", message="x"))
    assert exc_info.value.status is None


# ---------------------------------------------------------------------------
# Token issuance: issued once, reused, reissued only close to expiry.
# ---------------------------------------------------------------------------


def test_token_is_issued_once_and_reused(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr(_client_module, "issue_service_token", fake_issue)

    client = SourceControlSecondaryAdapterNATSClient(
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

    client = SourceControlSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real SourceControlPrimaryAdapterNATS
# wrapping a real InMemoryAdapter, and the client talking to it over the
# wire. Skips cleanly when Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs SourceControlPrimaryAdapterNATS on its own background event loop
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
        self._primary: SourceControlPrimaryAdapterNATS | None = None

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
            target=_run, daemon=True, name="source-control-nats-primary-test-loop"
        )
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = SourceControlPrimaryAdapterNATS(
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
class TestSourceControlSecondaryAdapterNATSClient(GenericSourceControlSecondaryAdapterTest):
    """Round-trips the shared adapter contract through a real primary adapter
    (wrapping a real InMemoryAdapter) and the real client, over a live NATS
    server."""

    @pytest.fixture
    def adapter_class(self):
        return SourceControlSecondaryAdapterNATSClient

    @pytest.fixture
    def client(self, nats_url):
        wrapped = InMemoryAdapter()
        server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
        server.start()

        client = SourceControlSecondaryAdapterNATSClient(
            nats_url=nats_url,
            jwt_secret=JWT_SECRET,
            service_identity="api",
            timeout_seconds=10.0,
        )
        yield client
        client.close()
        server.stop()

    def test_ensure_repo_and_list_repos_round_trip(self, client):
        repo = client.ensure_repo(owner="alice", name="proj")
        assert repo.owner == "alice"
        assert repo.name == "proj"
        assert any(r.id == repo.id for r in client.list_repos())

    def test_proposal_and_merge_round_trip(self, client):
        client.ensure_repo(owner="alice", name="proj")
        client.create_branch(repo_id="alice/proj", name="feature", from_ref="main")
        proposal = client.create_proposal(
            repo_id="alice/proj",
            title="t",
            body="b",
            source_branch="feature",
            target_branch="main",
        )
        assert proposal.number == 1
        result = client.merge(repo_id="alice/proj", number=1)
        assert result.merged is True

    def test_repo_not_found_surfaces_as_repo_not_found_error(self, client):
        with pytest.raises(RepoNotFoundError):
            client.list_branches(repo_id="nope/nope")


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url):
    wrapped = InMemoryAdapter()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = SourceControlSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.list_repos()
    finally:
        client.close()
        server.stop()
