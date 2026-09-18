"""Unit tests for TripleStorePrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called out
for this adapter (see ``object_storage__primary_adapter__NATS_test.py``, the
same pattern).
"""

import asyncio

import pytest
import rdflib
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.triple_store.v1 import triple_store_pb2
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    AUTH_HEADER,
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.triple_store.v1.insert",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubPort(ITripleStorePort):
    """Minimal in-memory ITripleStorePort for driving the handlers, backed by
    a real rdflib.Dataset so SPARQL queries (including ``GRAPH <uri> {...}``)
    behave like a real backend, with real N-Triples round-tripping through
    the adapter's wire encoding."""

    def __init__(self) -> None:
        self._ds = rdflib.Dataset(default_union=True)
        self._known_graphs: set[str] = set()
        self.view_events: list[tuple] = []

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

    def handle_view_event(
        self,
        view: tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: tuple[URIRef | None, URIRef | None, URIRef | None],
    ) -> None:
        self.view_events.append((view, event, triple))

    def query(self, query: str) -> rdflib.query.Result:
        return self._ds.query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.query(query)

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        result = Graph()
        if graph_name == "*":
            assert graph_name.__class__ is str, "wildcard must arrive as a plain str"
            for s, p, o in self._ds.triples((subject, None, None)):
                result.add((s, p, o))
        else:
            assert isinstance(graph_name, URIRef), (
                "a non-wildcard graph_name must be reconstructed as a URIRef"
            )
            ctx = self._ds.graph(URIRef(str(graph_name)))
            for s, p, o in ctx.triples((subject, None, None)):
                result.add((s, p, o))
        if len(result) == 0:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")
        return result

    def create_graph(self, graph_name: URIRef) -> None:
        key = str(graph_name)
        if key in self._known_graphs:
            raise Exceptions.GraphAlreadyExistsError(f"Graph {graph_name} already exists")
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


class _DomainOnlyStub:
    """Structurally shaped like ``ITripleStoreService``: the same 10 methods
    as ``_StubPort`` minus ``handle_view_event`` -- exercises the
    ``NOT_SUPPORTED`` path documented on ``TripleStorePrimaryAdapterNATS``
    for when it wraps the real domain service rather than a raw adapter."""

    def __init__(self) -> None:
        self._inner = _StubPort()

    def insert(self, triples, graph_name):
        return self._inner.insert(triples, graph_name)

    def remove(self, triples, graph_name):
        return self._inner.remove(triples, graph_name)

    def get(self):
        return self._inner.get()

    def query(self, query):
        return self._inner.query(query)

    def query_view(self, view, query):
        return self._inner.query_view(view, query)

    def get_subject_graph(self, subject, graph_name):
        return self._inner.get_subject_graph(subject, graph_name)

    def create_graph(self, graph_name):
        return self._inner.create_graph(graph_name)

    def clear_graph(self, graph_name):
        return self._inner.clear_graph(graph_name)

    def drop_graph(self, graph_name):
        return self._inner.drop_graph(graph_name)

    def list_graphs(self):
        return self._inner.list_graphs()


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _insert_request(
    triples: Graph | None = None, graph_name: str = "http://test.example.org/g"
) -> bytes:
    triples = triples if triples is not None else Graph()
    return triple_store_pb2.InsertRequest(
        triples_nt=triples.serialize(format="nt", encoding="utf-8"),
        graph_name=graph_name,
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    request = _FakeRequest(data=_insert_request(), headers=None)

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    request = _FakeRequest(data=_insert_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    request = _FakeRequest(data=_insert_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_insert_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path: real n-triples round-tripping through every endpoint.
# ---------------------------------------------------------------------------


def test_insert_then_get_round_trips_triples():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    subject = URIRef("http://test.example.org/s")
    predicate = URIRef("http://test.example.org/p")
    obj = Literal("hello")
    g = Graph()
    g.add((subject, predicate, obj))

    request = _FakeRequest(
        data=_insert_request(g, "http://test.example.org/g"),
        headers={AUTH_HEADER: _valid_token()},
    )
    asyncio.run(adapter._handle_insert(request))
    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")

    get_request = _FakeRequest(
        data=triple_store_pb2.GetRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.get",
    )
    asyncio.run(adapter._handle_get(get_request))
    get_response = triple_store_pb2.GetResponse()
    get_response.ParseFromString(get_request.responses[0])
    assert not get_response.HasField("error")
    round_tripped = Graph().parse(data=get_response.triples_nt, format="nt")
    assert (subject, predicate, obj) in round_tripped


def test_remove_deletes_previously_inserted_triples():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    subject = URIRef("http://test.example.org/s2")
    predicate = URIRef("http://test.example.org/p")
    obj = Literal("bye")
    g = Graph()
    g.add((subject, predicate, obj))
    stub.insert(g, URIRef("http://test.example.org/g2"))

    remove_request = _FakeRequest(
        data=triple_store_pb2.RemoveRequest(
            triples_nt=g.serialize(format="nt", encoding="utf-8"),
            graph_name="http://test.example.org/g2",
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.remove",
    )
    asyncio.run(adapter._handle_remove(remove_request))
    response = triple_store_pb2.RemoveResponse()
    response.ParseFromString(remove_request.responses[0])
    assert not response.HasField("error")
    remaining = stub.get()
    assert (subject, predicate, obj) not in remaining


def test_create_clear_drop_list_graphs_roundtrip():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    graph_name = "http://test.example.org/managed"

    create_request = _FakeRequest(
        data=triple_store_pb2.CreateGraphRequest(graph_name=graph_name).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.create_graph",
    )
    asyncio.run(adapter._handle_create_graph(create_request))
    create_response = triple_store_pb2.CreateGraphResponse()
    create_response.ParseFromString(create_request.responses[0])
    assert not create_response.HasField("error")

    list_request = _FakeRequest(
        data=triple_store_pb2.ListGraphsRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.list_graphs",
    )
    asyncio.run(adapter._handle_list_graphs(list_request))
    list_response = triple_store_pb2.ListGraphsResponse()
    list_response.ParseFromString(list_request.responses[0])
    assert graph_name in list_response.graph_names.graph_names

    subject = URIRef("http://test.example.org/managed-subject")
    g = Graph()
    g.add((subject, URIRef("http://test.example.org/p"), Literal("x")))
    stub.insert(g, URIRef(graph_name))

    clear_request = _FakeRequest(
        data=triple_store_pb2.ClearGraphRequest(graph_name=graph_name).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.clear_graph",
    )
    asyncio.run(adapter._handle_clear_graph(clear_request))
    clear_response = triple_store_pb2.ClearGraphResponse()
    clear_response.ParseFromString(clear_request.responses[0])
    assert not clear_response.HasField("error")
    assert len(stub.get()) == 0

    drop_request = _FakeRequest(
        data=triple_store_pb2.DropGraphRequest(graph_name=graph_name).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.drop_graph",
    )
    asyncio.run(adapter._handle_drop_graph(drop_request))
    drop_response = triple_store_pb2.DropGraphResponse()
    drop_response.ParseFromString(drop_request.responses[0])
    assert not drop_response.HasField("error")

    list_request_2 = _FakeRequest(
        data=triple_store_pb2.ListGraphsRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.list_graphs",
    )
    asyncio.run(adapter._handle_list_graphs(list_request_2))
    list_response_2 = triple_store_pb2.ListGraphsResponse()
    list_response_2.ParseFromString(list_request_2.responses[0])
    assert graph_name not in list_response_2.graph_names.graph_names


def test_get_subject_graph_round_trips_and_supports_wildcard():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    subject = URIRef("http://test.example.org/subj")
    predicate = URIRef("http://test.example.org/p")
    obj = Literal("v")
    g = Graph()
    g.add((subject, predicate, obj))
    stub.insert(g, URIRef("http://test.example.org/named"))

    named_request = _FakeRequest(
        data=triple_store_pb2.GetSubjectGraphRequest(
            subject=str(subject), graph_name="http://test.example.org/named"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.get_subject_graph",
    )
    asyncio.run(adapter._handle_get_subject_graph(named_request))
    named_response = triple_store_pb2.GetSubjectGraphResponse()
    named_response.ParseFromString(named_request.responses[0])
    assert not named_response.HasField("error")
    named_graph = Graph().parse(data=named_response.triples_nt, format="nt")
    assert (subject, predicate, obj) in named_graph

    wildcard_request = _FakeRequest(
        data=triple_store_pb2.GetSubjectGraphRequest(
            subject=str(subject), graph_name="*"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.get_subject_graph",
    )
    asyncio.run(adapter._handle_get_subject_graph(wildcard_request))
    wildcard_response = triple_store_pb2.GetSubjectGraphResponse()
    wildcard_response.ParseFromString(wildcard_request.responses[0])
    assert not wildcard_response.HasField("error")
    wildcard_graph = Graph().parse(data=wildcard_response.triples_nt, format="nt")
    assert (subject, predicate, obj) in wildcard_graph


def test_handle_view_event_dispatches_on_a_raw_port():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.HandleViewEventRequest(
            view=triple_store_pb2.TriplePattern(
                predicate="http://test.example.org/p"
            ),
            event=triple_store_pb2.ONTOLOGY_EVENT_TYPE_INSERT,
            triple=triple_store_pb2.TriplePattern(
                subject="http://test.example.org/s",
                predicate="http://test.example.org/p",
                object="http://test.example.org/o",
            ),
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.handle_view_event",
    )

    asyncio.run(adapter._handle_handle_view_event(request))

    response = triple_store_pb2.HandleViewEventResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(stub.view_events) == 1
    view, event, triple = stub.view_events[0]
    assert view == (None, URIRef("http://test.example.org/p"), None)
    assert event == OntologyEvent.INSERT
    assert triple == (
        URIRef("http://test.example.org/s"),
        URIRef("http://test.example.org/p"),
        URIRef("http://test.example.org/o"),
    )


def test_handle_view_event_over_domain_service_returns_not_supported():
    adapter = TripleStorePrimaryAdapterNATS(_DomainOnlyStub(), SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.HandleViewEventRequest(
            event=triple_store_pb2.ONTOLOGY_EVENT_TYPE_DELETE,
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.handle_view_event",
    )

    asyncio.run(adapter._handle_handle_view_event(request))

    response = triple_store_pb2.HandleViewEventResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "NOT_SUPPORTED"
    assert response.error.retryable is False


# ---------------------------------------------------------------------------
# query/query_view: SELECT/ASK/CONSTRUCT all normalized into QueryResult.
# ---------------------------------------------------------------------------


def test_query_select_encodes_typed_bindings_as_n3():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    subject = URIRef("http://test.example.org/select-s")
    g = Graph()
    g.add((subject, URIRef("http://test.example.org/p"), Literal("v", lang="fr")))
    g.add(
        (
            subject,
            URIRef("http://test.example.org/count"),
            Literal(42, datatype=XSD.integer),
        )
    )
    stub.insert(g, URIRef("http://test.example.org/select-g"))

    request = _FakeRequest(
        data=triple_store_pb2.QueryRequest(
            query=f"""
            SELECT ?p ?o WHERE {{ <{subject}> ?p ?o }}
            """
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = triple_store_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.success.result_type == "SELECT"
    assert set(response.success.select.vars) == {"p", "o"}

    decoded = {}
    for row in response.success.select.rows:
        decoded[rdflib.util.from_n3(row.bindings["p"])] = rdflib.util.from_n3(
            row.bindings["o"]
        )
    assert decoded[URIRef("http://test.example.org/p")] == Literal("v", lang="fr")
    assert decoded[URIRef("http://test.example.org/count")] == Literal(
        42, datatype=XSD.integer
    )


def test_query_ask_encodes_boolean():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.QueryRequest(query="ASK { ?s ?p ?o }").SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = triple_store_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.success.result_type == "ASK"
    assert response.success.ask_answer is False


def test_query_construct_encodes_triples_nt():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    subject = URIRef("http://test.example.org/construct-s")
    predicate = URIRef("http://test.example.org/p")
    obj = Literal("v")
    g = Graph()
    g.add((subject, predicate, obj))
    stub.insert(g, URIRef("http://test.example.org/construct-g"))

    request = _FakeRequest(
        data=triple_store_pb2.QueryRequest(
            query=f"CONSTRUCT {{ <{subject}> <{predicate}> ?o }} WHERE {{ <{subject}> <{predicate}> ?o }}"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.query",
    )

    asyncio.run(adapter._handle_query(request))

    response = triple_store_pb2.QueryResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.success.result_type in ("CONSTRUCT", "DESCRIBE")
    constructed = Graph().parse(data=response.success.construct_triples_nt, format="nt")
    assert (subject, predicate, obj) in constructed


def test_query_view_delegates_like_query():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.QueryViewRequest(
            view="some-view", query="ASK { ?s ?p ?o }"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.query_view",
    )

    asyncio.run(adapter._handle_query_view(request))

    response = triple_store_pb2.QueryViewResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.success.result_type == "ASK"


# ---------------------------------------------------------------------------
# Business error mapping.
# ---------------------------------------------------------------------------


def test_subject_not_found_maps_to_call_error():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.GetSubjectGraphRequest(
            subject="http://test.example.org/missing", graph_name="*"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.get_subject_graph",
    )

    asyncio.run(adapter._handle_get_subject_graph(request))

    response = triple_store_pb2.GetSubjectGraphResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "SUBJECT_NOT_FOUND"
    assert response.error.retryable is False


def test_graph_not_found_maps_to_call_error():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.ClearGraphRequest(
            graph_name="http://test.example.org/no-such-graph"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.clear_graph",
    )

    asyncio.run(adapter._handle_clear_graph(request))

    response = triple_store_pb2.ClearGraphResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "GRAPH_NOT_FOUND"
    assert response.error.retryable is False


def test_graph_already_exists_maps_to_call_error():
    stub = _StubPort()
    adapter = TripleStorePrimaryAdapterNATS(stub, SECRET)
    stub.create_graph(URIRef("http://test.example.org/dup"))
    request = _FakeRequest(
        data=triple_store_pb2.CreateGraphRequest(
            graph_name="http://test.example.org/dup"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.create_graph",
    )

    asyncio.run(adapter._handle_create_graph(request))

    response = triple_store_pb2.CreateGraphResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "GRAPH_ALREADY_EXISTS"
    assert response.error.retryable is False


def test_view_not_found_maps_to_call_error():
    class _ViewMissingStub(_StubPort):
        def query_view(self, view, query):
            raise Exceptions.ViewNotFoundError(f"View {view} not found")

    adapter = TripleStorePrimaryAdapterNATS(_ViewMissingStub(), SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.QueryViewRequest(
            view="missing-view", query="ASK { ?s ?p ?o }"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.query_view",
    )

    asyncio.run(adapter._handle_query_view(request))

    response = triple_store_pb2.QueryViewResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "VIEW_NOT_FOUND"
    assert response.error.retryable is False


def test_subscription_not_found_maps_to_call_error_defensively():
    # SubscriptionNotFoundError can't actually cross ITripleStorePort in real
    # usage (it belongs to a `subscribe`/`unsubscribe` pair that isn't part
    # of this port), but the mapping exists defensively per the wire
    # contract's design -- exercised here via a deliberately-misbehaving stub.
    class _MisbehavingStub(_StubPort):
        def list_graphs(self):
            raise Exceptions.SubscriptionNotFoundError("sub-123 not found")

    adapter = TripleStorePrimaryAdapterNATS(_MisbehavingStub(), SECRET)
    request = _FakeRequest(
        data=triple_store_pb2.ListGraphsRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.triple_store.v1.list_graphs",
    )

    asyncio.run(adapter._handle_list_graphs(request))

    response = triple_store_pb2.ListGraphsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "SUBSCRIPTION_NOT_FOUND"
    assert response.error.retryable is False


def test_request_error_maps_to_call_error_with_full_detail():
    class _FlakyStub(_StubPort):
        def insert(self, triples, graph_name):
            raise Exceptions.RequestError(
                operation="insert",
                message="Fuseki returned a 503",
                status_code=503,
                response_body="upstream overloaded",
                endpoint="http://fuseki.internal/ds/update",
                attempts=3,
            )

    adapter = TripleStorePrimaryAdapterNATS(_FlakyStub(), SECRET)
    request = _FakeRequest(
        data=_insert_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "REQUEST_ERROR"
    assert response.error.retryable is True
    assert response.error.status == 503
    assert response.HasField("error_detail")
    assert response.error_detail.operation == "insert"
    assert response.error_detail.status_code == 503
    assert response.error_detail.response_body == "upstream overloaded"
    assert response.error_detail.endpoint == "http://fuseki.internal/ds/update"
    assert response.error_detail.attempts == 3


def test_request_error_without_status_code_leaves_status_unset():
    class _FlakyStub(_StubPort):
        def insert(self, triples, graph_name):
            raise Exceptions.RequestError(operation="insert", message="boom")

    adapter = TripleStorePrimaryAdapterNATS(_FlakyStub(), SECRET)
    request = _FakeRequest(
        data=_insert_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "REQUEST_ERROR"
    assert not response.error.HasField("status")
    assert not response.error_detail.HasField("status_code")


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomStub(_StubPort):
        def insert(self, triples, graph_name):
            raise RuntimeError("some sensitive internal detail")

    adapter = TripleStorePrimaryAdapterNATS(_BoomStub(), SECRET)
    request = _FakeRequest(
        data=_insert_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_insert(request))

    response = triple_store_pb2.InsertResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


def test_start_is_idempotent(monkeypatch):
    import naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS as primary_module

    calls = []

    class _FakeService:
        async def add_endpoint(self, **kwargs):
            calls.append(kwargs["name"])

        async def stop(self):
            pass

    async def _fake_add_service(nc, **kwargs):
        return _FakeService()

    monkeypatch.setattr(primary_module.nats.micro, "add_service", _fake_add_service)

    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    asyncio.run(adapter.start(object()))
    first_call_count = len(calls)
    asyncio.run(adapter.start(object()))  # second call must be a no-op
    assert len(calls) == first_call_count
    assert first_call_count == 11  # one endpoint per ITripleStorePort method


@pytest.mark.parametrize(
    "endpoint_name",
    [
        "insert",
        "remove",
        "get",
        "handle_view_event",
        "query",
        "query_view",
        "get_subject_graph",
        "create_graph",
        "clear_graph",
        "drop_graph",
        "list_graphs",
    ],
)
def test_every_port_method_has_a_handler(endpoint_name):
    adapter = TripleStorePrimaryAdapterNATS(_StubPort(), SECRET)
    assert hasattr(adapter, f"_handle_{endpoint_name}")
