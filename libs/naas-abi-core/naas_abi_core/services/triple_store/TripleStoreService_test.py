import base64
import hashlib
import os
from types import SimpleNamespace
from typing import Any, Callable, Tuple, cast

import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    OntologyEvent,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import ConjunctiveGraph, Graph, Literal, RDF, URIRef


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []
        self.consumed: list[tuple[str, str, Callable[[bytes], None]]] = []

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.published.append((topic, routing_key, payload))

    def subscribe(
        self,
        topic: str,
        routing_key: str,
        callback: Callable[[bytes], None],
    ) -> None:
        self.consumed.append((topic, routing_key, callback))

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        pass

    def dequeue(
        self,
        topic: str,
        routing_key: str,
        callback: Callable[[bytes], None],
    ) -> None:
        pass


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

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
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


class _InMemoryTripleStoreAdapter(ITripleStorePort):
    def __init__(self) -> None:
        # ConjunctiveGraph supports named graphs and the SPARQL `GRAPH <...>`
        # syntax that the service uses for schema metadata storage.
        self.graph = ConjunctiveGraph()
        self.insert_calls: list[tuple[Graph, URIRef | None]] = []
        self.remove_calls: list[tuple[Graph, URIRef | None]] = []

    def _named_graph(self, graph_name: URIRef | None) -> Graph:
        if graph_name is None:
            return self.graph.default_context
        return self.graph.get_context(graph_name)

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        self.insert_calls.append((triples, graph_name))
        target = self._named_graph(graph_name)
        for triple in triples:
            target.add(triple)

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        self.remove_calls.append((triples, graph_name))
        target = self._named_graph(graph_name)
        for triple in triples:
            target.remove(triple)

    def get(self) -> Graph:
        return self.graph

    def query(self, query: str) -> rdflib.query.Result:
        return self.graph.query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.graph.query(query)

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        subject_graph = Graph()
        for s, p, o in self.graph.triples((subject, None, None)):
            subject_graph.add((s, p, o))
        return subject_graph

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        return None

    def create_graph(self, graph_name: URIRef):
        raise NotImplementedError

    def clear_graph(self, graph_name: URIRef | None = None):
        raise NotImplementedError

    def drop_graph(self, graph_name: URIRef):
        raise NotImplementedError

    def list_graphs(self) -> list[URIRef]:
        raise NotImplementedError


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


def test_load_schema_does_not_reload_when_schema_is_unchanged(tmp_path):
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)

    # Ignore constructor bootstrapping insert of SCHEMA_TTL.
    adapter.insert_calls.clear()

    schema_file = tmp_path / "schema.ttl"
    schema_file.write_text(
        """@prefix ex: <http://example.org/> .

ex:Thing a ex:Class .
""",
        encoding="utf-8",
    )

    service.load_schema(str(schema_file))
    first_insert_count = len(adapter.insert_calls)

    service.load_schema(str(schema_file))

    assert len(adapter.insert_calls) == first_insert_count


def test_load_schema_cleans_duplicate_metadata_entries_for_same_filepath(tmp_path):
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)

    # Ignore constructor bootstrapping insert of SCHEMA_TTL.
    adapter.insert_calls.clear()
    adapter.remove_calls.clear()

    schema_file = tmp_path / "duplicate-schema.ttl"
    schema_content = """@prefix ex: <http://example.org/> .

ex:Thing a ex:Class .
"""
    schema_file.write_text(schema_content, encoding="utf-8")

    service.load_schema(str(schema_file))

    content_hash = hashlib.sha256(schema_content.encode("utf-8")).hexdigest()
    base64_content = base64.b64encode(schema_content.encode("utf-8")).decode("utf-8")
    file_last_update_time = os.path.getmtime(schema_file)

    duplicate_subject = URIRef("http://triple-store.internal/duplicate-schema-entry")
    duplicate_metadata = Graph().parse(
        data=f'''@prefix internal: <http://triple-store.internal#> .

<{duplicate_subject}> a internal:Schema ;
    internal:hash "{content_hash}" ;
    internal:filePath "{schema_file}" ;
    internal:fileLastUpdateTime "{file_last_update_time}" ;
    internal:content "{base64_content}" .
''',
        format="turtle",
    )
    service.insert(
        duplicate_metadata,
        graph_name=URIRef("http://ontology.naas.ai/graph/schema"),
    )

    before_rows = list(
        service.query(
            f'''PREFIX internal: <http://triple-store.internal#>
SELECT ?s WHERE {{
    ?s a internal:Schema ;
       internal:filePath "{schema_file}" .
}}'''
        )
    )
    assert len(before_rows) == 2

    insert_count_before_reload = len(adapter.insert_calls)

    service.load_schema(str(schema_file))

    after_rows = list(
        service.query(
            f'''PREFIX internal: <http://triple-store.internal#>
SELECT ?s WHERE {{
    ?s a internal:Schema ;
       internal:filePath "{schema_file}" .
}}'''
        )
    )
    assert len(after_rows) == 1
    assert len(adapter.insert_calls) == insert_count_before_reload
    assert len(adapter.remove_calls) >= 1


def test_load_schemas_indexes_each_file_exactly_once(tmp_path):
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)

    filepaths: list[str] = []
    for i in range(16):
        path = tmp_path / f"schema-{i}.ttl"
        path.write_text(
            f"""@prefix ex: <http://example.org/{i}/> .

ex:Thing{i} a ex:Class .
""",
            encoding="utf-8",
        )
        filepaths.append(str(path))

    service.load_schemas(filepaths)

    # Each file should be tracked by exactly one Schema entry.
    rows = list(
        service.query(
            """PREFIX internal: <http://triple-store.internal#>
SELECT ?filePath (COUNT(?s) AS ?n) WHERE {
    GRAPH <http://ontology.naas.ai/graph/schema> {
        ?s a internal:Schema ; internal:filePath ?filePath .
    }
} GROUP BY ?filePath"""
        )
    )
    counts = {str(filePath): int(n) for filePath, n in rows}
    for filepath in filepaths:
        assert counts.get(filepath) == 1, f"missing or duplicated: {filepath}"

    # A second pass over unchanged files should be a no-op (cache hit).
    inserts_before = len(adapter.insert_calls)
    removes_before = len(adapter.remove_calls)
    service.load_schemas(filepaths)
    assert len(adapter.insert_calls) == inserts_before
    assert len(adapter.remove_calls) == removes_before
