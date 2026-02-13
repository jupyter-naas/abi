import hashlib
from types import SimpleNamespace
from typing import Any, Callable, Tuple, cast

import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    OntologyEvent,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import Graph, Literal, RDF, URIRef


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []
        self.consumed: list[tuple[str, str, Callable[[bytes], None]]] = []

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.published.append((topic, routing_key, payload))

    def topic_consume(
        self,
        topic: str,
        routing_key: str,
        callback: Callable[[bytes], None],
    ) -> None:
        self.consumed.append((topic, routing_key, callback))


class _FakeTripleStoreAdapter(ITripleStorePort):
    def __init__(self) -> None:
        self.insert_calls: list[tuple[Graph, URIRef | None]] = []
        self.remove_calls: list[tuple[Graph, URIRef | None]] = []
        self.create_graph_calls: list[URIRef] = []
        self.clear_graph_calls: list[URIRef | None] = []
        self.drop_graph_calls: list[URIRef] = []
        self.graphs_to_return: list[URIRef] = []

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        self.insert_calls.append((triples, graph_name))

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        self.remove_calls.append((triples, graph_name))

    def get(self) -> Graph:
        return Graph()

    def query(self, query: str) -> rdflib.query.Result:
        return rdflib.query.Result("SELECT")

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return rdflib.query.Result("SELECT")

    def get_subject_graph(self, subject: URIRef) -> Graph:
        return Graph()

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        return None

    def create_graph(self, graph_name: URIRef):
        self.create_graph_calls.append(graph_name)

    def clear_graph(self, graph_name: URIRef | None = None):
        self.clear_graph_calls.append(graph_name)

    def drop_graph(self, graph_name: URIRef):
        self.drop_graph_calls.append(graph_name)

    def list_graphs(self) -> list[URIRef]:
        return self.graphs_to_return


def _sha(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _build_service() -> tuple[TripleStoreService, _FakeTripleStoreAdapter, _FakeBus]:
    adapter = _FakeTripleStoreAdapter()
    service = TripleStoreService(adapter)

    # Ignore constructor bootstrapping insert of SCHEMA_TTL.
    adapter.insert_calls.clear()

    bus = _FakeBus()
    service.set_services(cast(Any, SimpleNamespace(bus=bus)))
    return service, adapter, bus


def test_insert_default_graph_publishes_default_topic_and_passes_none_graph():
    service, adapter, bus = _build_service()

    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            Literal("o"),
        )
    )

    service.insert(graph)

    assert len(adapter.insert_calls) == 1
    _, graph_name = adapter.insert_calls[0]
    assert graph_name is None

    assert len(bus.published) == 1
    topic, routing_key, payload = bus.published[0]
    assert topic == "triple_store"
    assert routing_key == (
        f"ts.insert.g.default"
        f".s.{_sha(URIRef('http://example.org/s'))}"
        f".p.{_sha(URIRef('http://example.org/p'))}"
        f".o.{_sha(Literal('o'))}"
    )
    assert payload == b'<http://example.org/s> <http://example.org/p> "o" .\n'


def test_insert_named_graph_publishes_graph_hash_topic_and_passes_graph_name():
    service, adapter, bus = _build_service()

    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/s"),
            RDF.type,
            URIRef("http://example.org/Entity"),
        )
    )

    graph_name = URIRef("http://example.org/graphs/entities")
    service.insert(graph, graph_name=graph_name)

    assert len(adapter.insert_calls) == 1
    _, called_graph_name = adapter.insert_calls[0]
    assert called_graph_name == graph_name

    assert len(bus.published) == 1
    _, routing_key, _ = bus.published[0]
    assert routing_key.startswith(f"ts.insert.g.{_sha(graph_name)}")


def test_remove_named_graph_publishes_delete_topic_with_graph_hash():
    service, adapter, bus = _build_service()

    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            URIRef("http://example.org/o"),
        )
    )

    graph_name = URIRef("http://example.org/graphs/remove")
    service.remove(graph, graph_name=graph_name)

    assert len(adapter.remove_calls) == 1
    _, called_graph_name = adapter.remove_calls[0]
    assert called_graph_name == graph_name

    assert len(bus.published) == 1
    _, routing_key, _ = bus.published[0]
    assert routing_key.startswith(f"ts.delete.g.{_sha(graph_name)}")


def test_subscribe_with_default_and_named_graph_builds_expected_routing_key():
    service, _, bus = _build_service()

    def callback(_: bytes) -> None:
        return None

    service.subscribe(
        (None, RDF.type, None),
        callback,
        event_type=OntologyEvent.INSERT,
        graph_name=None,
    )
    service.subscribe(
        (None, RDF.type, None),
        callback,
        event_type=OntologyEvent.DELETE,
        graph_name=URIRef("http://example.org/graphs/g1"),
    )

    assert len(bus.consumed) == 2

    _, default_routing_key, _ = bus.consumed[0]
    assert default_routing_key == f"ts.insert.g.default.s.*.p.{_sha(RDF.type)}.o.*"

    _, named_routing_key, _ = bus.consumed[1]
    assert named_routing_key == (
        f"ts.delete.g.{_sha(URIRef('http://example.org/graphs/g1'))}"
        f".s.*.p.{_sha(RDF.type)}.o.*"
    )


def test_subscribe_with_wildcard_graph_uses_wildcard_graph_token():
    service, _, bus = _build_service()

    def callback(_: bytes) -> None:
        return None

    service.subscribe(
        (None, RDF.type, None),
        callback,
        event_type=None,
        graph_name="*",
    )

    assert len(bus.consumed) == 1
    _, routing_key, _ = bus.consumed[0]
    assert routing_key == f"ts.*.g.*.s.*.p.{_sha(RDF.type)}.o.*"


def test_named_graph_management_methods_delegate_to_adapter():
    service, adapter, _ = _build_service()

    graph_name = URIRef("http://example.org/graphs/entities")
    other_graph = URIRef("http://example.org/graphs/other")
    adapter.graphs_to_return = [graph_name, other_graph]

    service.create_graph(graph_name)
    service.clear_graph(graph_name)
    service.clear_graph()
    service.drop_graph(other_graph)

    listed = service.list_graphs()

    assert adapter.create_graph_calls == [graph_name]
    assert adapter.clear_graph_calls == [graph_name, None]
    assert adapter.drop_graph_calls == [other_graph]
    assert listed == [graph_name, other_graph]
