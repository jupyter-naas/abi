import base64
import hashlib
import os
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest
import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import RDF, ConjunctiveGraph, Graph, Literal, URIRef


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []
        self.consumed: list[tuple[str, str, Callable[[bytes], None]]] = []

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.published.append((topic, routing_key, payload))

    def publish_many(self, topic: str, messages) -> None:
        for routing_key, payload in messages:
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
        self.schema_graph_present = False

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        self.insert_calls.append((triples, graph_name))
        if graph_name == URIRef("http://ontology.naas.ai/graph/schema"):
            self.schema_graph_present = True

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        self.remove_calls.append((triples, graph_name))

    def get(self) -> Graph:
        return Graph()

    def query(self, query: str) -> rdflib.query.Result:
        if "ASK" in query.upper() and "triple-store.internal#Schema" in query:
            result = rdflib.query.Result("ASK")
            result.askAnswer = self.schema_graph_present
            return result
        return rdflib.query.Result("SELECT")

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return rdflib.query.Result("SELECT")

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        return Graph()

    def handle_view_event(
        self,
        view: tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: tuple[URIRef | None, URIRef | None, URIRef | None],
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
        view: tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: tuple[URIRef | None, URIRef | None, URIRef | None],
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
    """The service's routing key token: a sha256 cut to 32 hex digits."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:32]


def _build_service() -> tuple[TripleStoreService, _FakeTripleStoreAdapter, _FakeBus]:
    adapter = _FakeTripleStoreAdapter()
    service = TripleStoreService(adapter)

    # Ignore constructor bootstrapping insert of SCHEMA_TTL.
    adapter.insert_calls.clear()

    bus = _FakeBus()
    service.set_services(cast(Any, SimpleNamespace(bus=bus)))
    return service, adapter, bus


def test_constructor_skips_schema_insert_when_schema_graph_already_present():
    adapter = _InMemoryTripleStoreAdapter()

    TripleStoreService(adapter)
    schema_inserts = [
        call
        for call in adapter.insert_calls
        if call[1] == URIRef("http://ontology.naas.ai/graph/schema")
    ]
    assert len(schema_inserts) == 1

    adapter.insert_calls.clear()
    TripleStoreService(adapter)

    assert adapter.insert_calls == []


def test_insert_publishes_one_routing_key_per_triple():
    service, adapter, bus = _build_service()

    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            Literal("o"),
        )
    )
    graph_name = URIRef("http://example.org/graphs/g")

    service.insert(graph, graph_name)

    assert [name for _, name in adapter.insert_calls] == [graph_name]
    assert len(bus.published) == 1
    topic, routing_key, payload = bus.published[0]
    assert topic == "triple_store"
    assert routing_key == (
        f"ts.insert.g.{_sha(graph_name)}"
        f".s.{_sha(URIRef('http://example.org/s'))}"
        f".p.{_sha(URIRef('http://example.org/p'))}"
        f".o.{_sha(Literal('o'))}"
    )
    assert payload == b'<http://example.org/s> <http://example.org/p> "o" .\n'


def test_writes_require_a_graph_name():
    service, adapter, bus = _build_service()

    for write in (service.insert, service.remove):
        with pytest.raises(AssertionError):
            write(Graph(), None)  # type: ignore[arg-type]

    assert adapter.insert_calls == adapter.remove_calls == []
    assert bus.published == []


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


def test_subscribe_with_any_and_named_graph_builds_expected_routing_key():
    service, _, bus = _build_service()

    def callback(_: bytes) -> None:
        return None

    service.subscribe(
        (None, RDF.type, None),
        callback,
        event_type=OntologyEvent.INSERT,
    )
    service.subscribe(
        (None, RDF.type, None),
        callback,
        event_type=OntologyEvent.DELETE,
        graph_name=URIRef("http://example.org/graphs/g1"),
    )

    assert len(bus.consumed) == 2

    _, any_graph_routing_key, _ = bus.consumed[0]
    assert any_graph_routing_key == f"ts.insert.g.*.s.*.p.{_sha(RDF.type)}.o.*"

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
    service.drop_graph(other_graph)

    listed = service.list_graphs()

    assert adapter.create_graph_calls == [graph_name]
    assert adapter.clear_graph_calls == [graph_name]
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


_SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")
_EX = "http://example.org/"
_SOURCE = "module/foo/modules/FooOntology.ttl"
_FOO_V1 = """@prefix ex: <http://example.org/> .

ex:Thing a ex:Class .
"""
_FOO_V2 = """@prefix ex: <http://example.org/> .

ex:Other a ex:Class .
"""


def _schema_entries(service: TripleStoreService, source: str) -> list:
    return list(
        service.query(
            f"""PREFIX internal: <http://triple-store.internal#>
SELECT ?s ?hash WHERE {{
    GRAPH <{_SCHEMA_GRAPH}> {{
        ?s a internal:Schema ; internal:filePath "{source}" ; internal:hash ?hash .
    }}
}}"""
        )
    )


def _in_schema(adapter: _InMemoryTripleStoreAdapter, name: str) -> bool:
    return (
        URIRef(_EX + name),
        RDF.type,
        URIRef(_EX + "Class"),
    ) in adapter.graph.get_context(_SCHEMA_GRAPH)


def test_load_schema_content_adds_a_new_source():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)

    assert service.load_schema_content(_SOURCE, _FOO_V1, 1700000000.0) is True

    assert _in_schema(adapter, "Thing")
    [(subject, content_hash)] = _schema_entries(service, _SOURCE)
    assert str(content_hash) == hashlib.sha256(_FOO_V1.encode()).hexdigest()
    stored = service._fetch_schema_content(cast(URIRef, subject))
    assert stored is not None
    assert base64.b64decode(stored).decode() == _FOO_V1
    assert (
        subject,
        URIRef("http://triple-store.internal#fileLastUpdateTime"),
        Literal("1700000000.0"),
    ) in adapter.graph.get_context(_SCHEMA_GRAPH)


def test_load_schema_content_writes_nothing_for_unchanged_content():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content(_SOURCE, _FOO_V1)
    inserts, removes = len(adapter.insert_calls), len(adapter.remove_calls)

    assert service.load_schema_content(_SOURCE, _FOO_V1) is False

    assert (len(adapter.insert_calls), len(adapter.remove_calls)) == (inserts, removes)
    assert len(_schema_entries(service, _SOURCE)) == 1


def test_load_schema_content_parses_unchanged_content_never_and_new_content_once(
    monkeypatch,
):
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    parsed: list[str] = []
    parse = TripleStoreService._parse_schema

    def counting(content, rdf_format, base):
        parsed.append(content)
        return parse(content, rdf_format, base)

    monkeypatch.setattr(TripleStoreService, "_parse_schema", staticmethod(counting))

    service.load_schema_content(_SOURCE, _FOO_V1)
    assert parsed == [_FOO_V1]  # a new source: once, checks included

    service.load_schema_content(_SOURCE, _FOO_V1)
    assert parsed == [_FOO_V1]  # unchanged: the hash answers, nothing is parsed

    service.load_schema_content(_SOURCE, _FOO_V2)
    # changed: the new content once, the stored one for the diff
    assert parsed == [_FOO_V1, _FOO_V2, _FOO_V1]


def test_load_schema_content_applies_the_diff_for_changed_content():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content(_SOURCE, _FOO_V1)

    assert service.load_schema_content(_SOURCE, _FOO_V2) is True

    assert _in_schema(adapter, "Other")
    assert not _in_schema(adapter, "Thing")
    [(_, content_hash)] = _schema_entries(service, _SOURCE)
    assert str(content_hash) == hashlib.sha256(_FOO_V2.encode()).hexdigest()
    assert service.load_schema_content(_SOURCE, _FOO_V2) is False


def test_load_schema_content_refuses_invalid_turtle_and_writes_nothing():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content(_SOURCE, _FOO_V1)
    inserts, removes = len(adapter.insert_calls), len(adapter.remove_calls)

    with pytest.raises(Exceptions.InvalidSchemaError):
        service.load_schema_content(_SOURCE, "ex:Thing a ex:Class")
    with pytest.raises(Exceptions.InvalidSchemaError):
        service.load_schema_content("module/foo/new.ttl", "this is not turtle")

    assert (len(adapter.insert_calls), len(adapter.remove_calls)) == (inserts, removes)
    assert _schema_entries(service, "module/foo/new.ttl") == []
    assert _in_schema(adapter, "Thing")


def test_load_schema_content_refuses_the_services_own_vocabulary():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content(_SOURCE, _FOO_V1)
    forged = """@prefix internal: <http://triple-store.internal#> .

<http://example.org/forged> a internal:Schema ;
    internal:filePath "module/foo/modules/FooOntology.ttl" ;
    internal:hash "x" .
"""

    with pytest.raises(Exceptions.InvalidSchemaError):
        service.load_schema_content("module/bar/Forged.ttl", forged)

    assert len(_schema_entries(service, _SOURCE)) == 1
    assert _schema_entries(service, "module/bar/Forged.ttl") == []


def test_load_schema_content_resolves_relative_iris_independently_of_the_cwd(
    tmp_path, monkeypatch
):
    relative = "<thing> a <http://example.org/Class> .\n"
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    subjects = []
    for cwd in (first, second):
        monkeypatch.chdir(cwd)
        adapter = _InMemoryTripleStoreAdapter()
        TripleStoreService(adapter).load_schema_content(_SOURCE, relative)
        subjects.append(
            {
                str(s)
                for s, _, o in adapter.graph.get_context(_SCHEMA_GRAPH)
                if o == URIRef(_EX + "Class")
            }
        )

    assert subjects[0] == subjects[1]
    assert all(s.startswith("http://ontology.naas.ai/module/foo/") for s in subjects[0])


def test_load_schema_content_publishes_loaded_and_error_events():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    events = []
    service.set_services(
        cast(
            Any,
            SimpleNamespace(
                bus=_FakeBus(),
                events_available=lambda: True,
                events=SimpleNamespace(emit=events.append),
            ),
        )
    )

    service.load_schema_content(_SOURCE, _FOO_V1)
    with pytest.raises(Exceptions.InvalidSchemaError):
        service.load_schema_content(_SOURCE, "nope")

    names = [type(event).__name__ for event in events]
    assert [n for n in names if n in ("SchemaLoaded", "TripleStoreError")] == [
        "SchemaLoaded",
        "TripleStoreError",
    ]


def test_load_schema_file_and_content_share_one_implementation(tmp_path):
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    schema_file = tmp_path / "schema.ttl"
    schema_file.write_text(_FOO_V1, encoding="utf-8")
    service.load_schema(str(schema_file))

    # The same key and content as the file: nothing to write.
    assert service.load_schema_content(str(schema_file), _FOO_V1) is False
    # Changed content under the file's key applies the diff, as a changed file would.
    assert service.load_schema_content(str(schema_file), _FOO_V2) is True
    assert _in_schema(adapter, "Other") and not _in_schema(adapter, "Thing")


def test_a_write_deadline_reaches_only_an_adapter_that_takes_one():
    class _RemoteAdapter(_FakeTripleStoreAdapter):
        """Calls another process, so a caller's deadline matters (NATS client)."""

        def __init__(self) -> None:
            super().__init__()
            self.deadlines: list[float | None] = []

        def insert(self, triples, graph_name=None, *, timeout_seconds=None):
            self.deadlines.append(timeout_seconds)
            super().insert(triples, graph_name)

        def remove(self, triples, graph_name=None, *, timeout_seconds=None):
            self.deadlines.append(timeout_seconds)
            super().remove(triples, graph_name)

        def create_graph(self, graph_name, *, timeout_seconds=None):
            self.deadlines.append(timeout_seconds)
            super().create_graph(graph_name)

        def clear_graph(self, graph_name=None, *, timeout_seconds=None):
            self.deadlines.append(timeout_seconds)
            super().clear_graph(graph_name)

        def drop_graph(self, graph_name, *, timeout_seconds=None):
            self.deadlines.append(timeout_seconds)
            super().drop_graph(graph_name)

    graph_name = URIRef("http://example.org/graph/billing")
    triples = Graph()
    triples.add(
        (URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/C"))
    )

    remote = _RemoteAdapter()
    remote.schema_graph_present = True
    service = TripleStoreService(remote)
    service.insert(triples, graph_name, timeout_seconds=900.0)
    service.remove(triples, graph_name, timeout_seconds=900.0)
    service.insert(triples, graph_name)
    for operation in ("create_graph", "clear_graph", "drop_graph"):
        getattr(service, operation)(graph_name, timeout_seconds=900.0)
    assert remote.deadlines == [900.0, 900.0, None, 900.0, 900.0, 900.0]

    # An in-process store runs to completion: its adapter never sees one.
    local = _FakeTripleStoreAdapter()
    local.schema_graph_present = True
    service = TripleStoreService(local)
    service.insert(triples, graph_name, timeout_seconds=900.0)
    service.remove(triples, graph_name, timeout_seconds=900.0)
    assert [name for _, name in local.insert_calls] == [graph_name]
    assert [name for _, name in local.remove_calls] == [graph_name]
    service.clear_graph(graph_name, timeout_seconds=900.0)
    assert local.clear_graph_calls == [graph_name]


_SHARED = f"""@prefix ex: <{_EX}> .
ex:Shared a ex:Class .
ex:Own a ex:Class .
"""
_SHARED_DROPPED = f"""@prefix ex: <{_EX}> .
ex:Own a ex:Class .
"""


def test_a_triple_another_source_asserts_stays_when_one_source_drops_it():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content("module/core.like/base.ttl", _SHARED)
    service.load_schema_content("module/evil/repeat.ttl", _SHARED)

    # The second source drops the shared class: the first one still asserts it.
    assert service.load_schema_content("module/evil/repeat.ttl", _SHARED_DROPPED)

    assert _in_schema(adapter, "Shared") and _in_schema(adapter, "Own")


def test_a_triple_no_other_source_asserts_is_removed_with_its_source():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content("module/a/one.ttl", _SHARED)
    service.load_schema_content("module/b/two.ttl", _SHARED_DROPPED)

    service.load_schema_content("module/a/one.ttl", _SHARED_DROPPED)

    assert not _in_schema(adapter, "Shared") and _in_schema(adapter, "Own")


def test_removing_a_schema_keeps_the_triples_another_source_asserts():
    adapter = _InMemoryTripleStoreAdapter()
    service = TripleStoreService(adapter)
    service.load_schema_content("module/a/one.ttl", _SHARED)
    service.load_schema_content("module/b/two.ttl", _SHARED_DROPPED)

    service.remove_schema("module/a/one.ttl")

    assert not _in_schema(adapter, "Shared") and _in_schema(adapter, "Own")
    assert _schema_entries(service, "module/a/one.ttl") == []
