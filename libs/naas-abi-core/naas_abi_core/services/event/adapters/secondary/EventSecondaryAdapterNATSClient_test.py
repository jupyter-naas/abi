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
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
    EventSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventPort import EventNotFoundError, InvalidEventError

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    EventSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = EventSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = EventSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# EventPrimaryAdapterNATS encodes CallError.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_event_not_found():
    with pytest.raises(EventNotFoundError):
        _raise_for_error(common_pb2.CallError(code="EVENT_NOT_FOUND", message="x"))


def test_raise_for_error_maps_invalid_event():
    with pytest.raises(InvalidEventError):
        _raise_for_error(common_pb2.CallError(code="INVALID_EVENT", message="x"))


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

    client = EventSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")

    assert client._current_token() == "token-1"
    assert client._current_token() == "token-1"
    assert calls == ["api"]


def test_token_is_reissued_when_close_to_expiry(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr("naas_abi_core.engine.nats_rpc.issue_service_token", fake_issue)

    client = EventSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real EventPrimaryAdapterNATS
# wrapping a real EventSQLiteAdapter, and the client talking to it over the
# wire. Skips cleanly when Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs EventPrimaryAdapterNATS on its own background event loop for as
    long as a test needs it -- the server-side mirror of the client's own
    background loop, since nats-py has no synchronous API on either side."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: EventPrimaryAdapterNATS | None = None

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

        thread = Thread(target=_run, daemon=True, name="event-nats-primary-test-loop")
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = EventPrimaryAdapterNATS(self._wrapped_adapter, self._jwt_secret)
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


@pytest.fixture
def _server_and_client(nats_url, tmp_path):
    wrapped = EventSQLiteAdapter(str(tmp_path / "events.sqlite"))
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()

    client = EventSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    yield client
    client.close()
    server.stop()
    wrapped.close()


@pytest.mark.integration
class TestEventSecondaryAdapterNATSClient:
    """Round-trips IEventAdapter's six methods through a real primary adapter
    (wrapping a real SQLite adapter) and the real client, over a live NATS
    server."""

    def test_append_round_trips_stored_event(self, _server_and_client):
        client = _server_and_client
        stored = client.append(
            "urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"payload-1"
        )

        assert stored.id == "urn:e1"
        assert stored.event_type == "urn:Type:A"
        assert stored.seq == 1
        assert stored.timestamp == "2026-01-01T00:00:00"
        assert stored.payload == b"payload-1"

    def test_query_filters_and_orders_by_seq(self, _server_and_client):
        client = _server_and_client
        client.append("urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"p1")
        client.append("urn:e2", "urn:Type:B", "2026-01-01T00:00:01", b"p2")
        client.append("urn:e3", "urn:Type:A", "2026-01-01T00:00:02", b"p3")

        rows = client.query(event_type="urn:Type:A")

        assert [r.id for r in rows] == ["urn:e1", "urn:e3"]

    def test_query_with_json_filter_pushes_down(self, _server_and_client):
        client = _server_and_client
        client.append(
            "urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b'{"status": "ok"}'
        )
        client.append(
            "urn:e2", "urn:Type:A", "2026-01-01T00:00:01", b'{"status": "fail"}'
        )

        rows = client.query(event_type="urn:Type:A", json_filter={"status": ["ok"]})

        assert [r.id for r in rows] == ["urn:e1"]

    def test_max_seq_reflects_appended_events(self, _server_and_client):
        client = _server_and_client
        assert client.max_seq(event_type="urn:Type:A") == 0

        client.append("urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"p1")
        client.append("urn:e2", "urn:Type:A", "2026-01-01T00:00:01", b"p2")

        assert client.max_seq(event_type="urn:Type:A") == 2

    def test_get_cursor_defaults_to_zero(self, _server_and_client):
        client = _server_and_client
        assert client.get_cursor("consumer-1", "urn:Type:A") == 0

    def test_set_cursor_then_get_cursor_round_trips(self, _server_and_client):
        client = _server_and_client
        client.set_cursor("consumer-1", "urn:Type:A", 7)

        assert client.get_cursor("consumer-1", "urn:Type:A") == 7

    def test_query_for_consumer_catches_up_from_a_cursor(self, _server_and_client):
        client = _server_and_client
        client.append("urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"p1")
        client.append("urn:e2", "urn:Type:A", "2026-01-01T00:00:01", b"p2")
        client.append("urn:e3", "urn:Type:A", "2026-01-01T00:00:02", b"p3")

        # Seek the consumer past the first event, then confirm it only
        # catches up on events after the cursor.
        client.set_cursor("consumer-1", "urn:Type:A", 1)

        rows = client.query_for_consumer("consumer-1", "urn:Type:A")

        assert [r.id for r in rows] == ["urn:e2", "urn:e3"]
        # The cursor is advanced past what was just read.
        assert client.get_cursor("consumer-1", "urn:Type:A") == 3

        # Draining again with nothing new appended returns nothing.
        assert client.query_for_consumer("consumer-1", "urn:Type:A") == []

    def test_query_for_consumer_respects_limit(self, _server_and_client):
        client = _server_and_client
        client.append("urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"p1")
        client.append("urn:e2", "urn:Type:A", "2026-01-01T00:00:01", b"p2")
        client.append("urn:e3", "urn:Type:A", "2026-01-01T00:00:02", b"p3")

        rows = client.query_for_consumer("consumer-1", "urn:Type:A", limit=2)

        assert [r.id for r in rows] == ["urn:e1", "urn:e2"]
        assert client.get_cursor("consumer-1", "urn:Type:A") == 2


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url, tmp_path):
    wrapped = EventSQLiteAdapter(str(tmp_path / "events.sqlite"))
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = EventSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.append("urn:e1", "urn:Type:A", "2026-01-01T00:00:00", b"p1")
    finally:
        client.close()
        server.stop()
        wrapped.close()
