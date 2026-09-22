import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread

import naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient as _client_module
import nats
import pytest
import rdflib
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient import (
    TripleStoreSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import Graph, URIRef

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    from unittest.mock import AsyncMock

    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    TripleStoreSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = TripleStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = TripleStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. Must stay exactly symmetric with how
# TripleStorePrimaryAdapterNATS encodes CallError.code.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_subject_not_found():
    with pytest.raises(Exceptions.SubjectNotFoundError):
        _raise_for_error(
            common_pb2.CallError(code="SUBJECT_NOT_FOUND", message="x"), None
        )


def test_raise_for_error_maps_subscription_not_found():
    with pytest.raises(Exceptions.SubscriptionNotFoundError):
        _raise_for_error(
            common_pb2.CallError(code="SUBSCRIPTION_NOT_FOUND", message="x"), None
        )


def test_raise_for_error_maps_view_not_found():
    with pytest.raises(Exceptions.ViewNotFoundError):
        _raise_for_error(common_pb2.CallError(code="VIEW_NOT_FOUND", message="x"), None)


def test_raise_for_error_maps_graph_not_found():
    with pytest.raises(Exceptions.GraphNotFoundError):
        _raise_for_error(
            common_pb2.CallError(code="GRAPH_NOT_FOUND", message="x"), None
        )


def test_raise_for_error_maps_graph_already_exists():
    with pytest.raises(Exceptions.GraphAlreadyExistsError):
        _raise_for_error(
            common_pb2.CallError(code="GRAPH_ALREADY_EXISTS", message="x"), None
        )


def test_raise_for_error_maps_request_error_with_detail():
    detail = triple_store_pb2.TripleStoreRequestErrorDetail(
        operation="query",
        status_code=500,
        response_body="body",
        endpoint="http://x/query",
        attempts=2,
    )
    with pytest.raises(Exceptions.RequestError) as excinfo:
        _raise_for_error(
            common_pb2.CallError(code="REQUEST_ERROR", message="boom"), detail
        )
    exc = excinfo.value
    assert exc.operation == "query"
    assert exc.status_code == 500
    assert exc.response_body == "body"
    assert exc.endpoint == "http://x/query"
    assert exc.attempts == 2


def test_raise_for_error_maps_request_error_without_detail():
    with pytest.raises(Exceptions.RequestError) as excinfo:
        _raise_for_error(
            common_pb2.CallError(code="REQUEST_ERROR", message="boom"), None
        )
    assert excinfo.value.operation == "unknown"


def test_raise_for_error_maps_unknown_code_to_runtime_error():
    with pytest.raises(RuntimeError, match="INTERNAL"):
        _raise_for_error(common_pb2.CallError(code="INTERNAL", message="boom"), None)


def test_raise_for_error_maps_unauthenticated_to_runtime_error():
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        _raise_for_error(
            common_pb2.CallError(code="UNAUTHENTICATED", message="no token"), None
        )


# ---------------------------------------------------------------------------
# QueryResult reconstruction: a real rdflib.query.Result, not a duck-typed
# stand-in -- iterating yields real ResultRow objects, and typed values
# (URIRef vs Literal, datatype/lang) round-trip through N3.
# ---------------------------------------------------------------------------


def test_pb_to_query_result_reconstructs_select_with_typed_bindings():
    pb = triple_store_pb2.QueryResult(
        result_type="SELECT",
        select=triple_store_pb2.SelectResult(
            vars=["s", "label"],
            rows=[
                triple_store_pb2.Row(
                    bindings={
                        "s": "<http://x/s>",
                        "label": '"bonjour"@fr',
                    }
                )
            ],
        ),
    )

    result = _client_module._pb_to_query_result(pb)

    assert isinstance(result, rdflib.query.Result)
    rows = list(result)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, rdflib.query.ResultRow)
    assert row.s == URIRef("http://x/s")
    assert row.label == rdflib.Literal("bonjour", lang="fr")


def test_pb_to_query_result_reconstructs_ask():
    pb = triple_store_pb2.QueryResult(result_type="ASK", ask_answer=True)
    result = _client_module._pb_to_query_result(pb)
    assert result.type == "ASK"
    assert bool(result) is True


def test_pb_to_query_result_reconstructs_construct():
    g = Graph()
    g.add((URIRef("http://x/s"), URIRef("http://x/p"), URIRef("http://x/o")))
    pb = triple_store_pb2.QueryResult(
        result_type="CONSTRUCT",
        construct_triples_nt=g.serialize(format="nt", encoding="utf-8"),
    )
    result = _client_module._pb_to_query_result(pb)
    assert result.type == "CONSTRUCT"
    assert (URIRef("http://x/s"), URIRef("http://x/p"), URIRef("http://x/o")) in list(
        result
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

    client = TripleStoreSecondaryAdapterNATSClient(
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

    client = TripleStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real TripleStorePrimaryAdapterNATS
# wrapping a minimal in-memory ITripleStorePort, and the client talking to it
# over the wire. Skips cleanly when Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _InMemoryTripleStorePort(ITripleStorePort):
    """Minimal in-memory ITripleStorePort backing the integration test's
    server side. No embedded-store dependency (pyoxigraph etc.) needed --
    just enough real SPARQL/named-graph semantics (via rdflib.Dataset) to
    exercise the generic adapter contract end-to-end over the wire."""

    def __init__(self) -> None:
        self._ds = rdflib.Dataset(default_union=True)
        self._known_graphs: set[str] = set()

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        ctx = self._ds.graph(URIRef(str(graph_name)))
        for triple in triples:
            ctx.add(triple)
        self._known_graphs.add(str(graph_name))

    def remove(self, triples: Graph, graph_name: URIRef) -> None:
        ctx = self._ds.graph(URIRef(str(graph_name)))
        for triple in triples:
            ctx.remove(triple)

    def get(self) -> Graph:
        result = Graph()
        for s, p, o in self._ds.triples((None, None, None)):
            result.add((s, p, o))
        return result

    def handle_view_event(self, view, event, triple) -> None:
        return None

    def query(self, query: str) -> rdflib.query.Result:
        return self._ds.query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.query(query)

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        result = Graph()
        if graph_name == "*":
            for s, p, o in self._ds.triples((subject, None, None)):
                result.add((s, p, o))
        else:
            ctx = self._ds.graph(URIRef(str(graph_name)))
            for s, p, o in ctx.triples((subject, None, None)):
                result.add((s, p, o))
        if len(result) == 0:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")
        return result

    def create_graph(self, graph_name: URIRef) -> None:
        key = str(graph_name)
        if key in self._known_graphs:
            raise Exceptions.GraphAlreadyExistsError(
                f"Graph {graph_name} already exists"
            )
        self._known_graphs.add(key)
        self._ds.graph(URIRef(key))

    def clear_graph(self, graph_name: URIRef) -> None:
        key = str(graph_name)
        if key not in self._known_graphs:
            raise Exceptions.GraphNotFoundError(f"Graph {graph_name} not found")
        ctx = self._ds.graph(URIRef(key))
        ctx.remove((None, None, None))

    def drop_graph(self, graph_name: URIRef) -> None:
        key = str(graph_name)
        if key not in self._known_graphs:
            raise Exceptions.GraphNotFoundError(f"Graph {graph_name} not found")
        self._ds.remove_graph(URIRef(key))
        self._known_graphs.discard(key)

    def list_graphs(self) -> list[URIRef]:
        return [URIRef(k) for k in sorted(self._known_graphs)]


class _PrimaryAdapterServer:
    """Runs TripleStorePrimaryAdapterNATS on its own background event loop
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
        self._primary: TripleStorePrimaryAdapterNATS | None = None

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
            target=_run, daemon=True, name="triple-store-nats-primary-test-loop"
        )
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = TripleStorePrimaryAdapterNATS(
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
class TestTripleStoreSecondaryAdapterNATSClient(GenericTripleStoreSecondaryAdapterTest):
    """Round-trips the shared adapter contract through a real primary adapter
    (wrapping a real in-memory ITripleStorePort) and the real client, over a
    live NATS server."""

    @pytest.fixture
    def adapter(self, nats_url):
        wrapped = _InMemoryTripleStorePort()
        server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
        server.start()

        client = TripleStoreSecondaryAdapterNATSClient(
            nats_url=nats_url,
            jwt_secret=JWT_SECRET,
            service_identity="api",
            timeout_seconds=10.0,
        )
        yield client
        client.close()
        server.stop()

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return True

    @pytest.fixture
    def supports_graph_management(self) -> bool:
        return True


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url):
    wrapped = _InMemoryTripleStorePort()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = TripleStoreSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.create_graph(URIRef("http://test.example.org/g"))
    finally:
        client.close()
        server.stop()


@pytest.mark.integration
def test_handle_view_event_round_trips_over_the_wire(nats_url):
    wrapped = _InMemoryTripleStorePort()
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = TripleStoreSecondaryAdapterNATSClient(
        nats_url=nats_url, jwt_secret=JWT_SECRET, service_identity="api"
    )
    try:
        # No assertion beyond "does not raise": _InMemoryTripleStorePort's
        # handle_view_event is a no-op, matching every other secondary
        # adapter's (this method has no real caller anywhere in the repo --
        # see the primary adapter's module docstring).
        client.handle_view_event(
            (None, None, None), OntologyEvent.INSERT, (None, None, None)
        )
    finally:
        client.close()
        server.stop()
