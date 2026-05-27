# mypy: disable-error-code="arg-type,misc"
"""Event-emission tests for TripleStoreService."""

from __future__ import annotations

from typing import Tuple

import pytest
import rdflib
from rdflib import ConjunctiveGraph, Graph, Literal, URIRef

from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    OntologyEvent,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.triple_store.ontologies.modules.TripleStoreEventOntology import (
    GraphCleared,
    GraphCreated,
    GraphDropped,
    SchemaLoaded,
    SchemaRemoved,
    TripleStoreError,
    TriplesInserted,
    TriplesRemoved,
)


SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")


class _InMemoryAdapter(ITripleStorePort):
    def __init__(self) -> None:
        self.graph = ConjunctiveGraph()
        self.create_graph_calls: list[URIRef] = []
        self.clear_graph_calls: list[URIRef] = []
        self.drop_graph_calls: list[URIRef] = []

    def _named_graph(self, graph_name: URIRef | None) -> Graph:
        if graph_name is None:
            return self.graph.default_context
        return self.graph.get_context(graph_name)

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        target = self._named_graph(graph_name)
        for triple in triples:
            target.add(triple)

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
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
        self.clear_graph_calls.append(graph_name)  # type: ignore[arg-type]

    def drop_graph(self, graph_name: URIRef):
        self.drop_graph_calls.append(graph_name)

    def list_graphs(self) -> list[URIRef]:
        return []


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _NoopBus:
    def publish(self, *_args, **_kwargs) -> None:
        return None

    def subscribe(self, *_args, **_kwargs) -> None:
        return None


class _FakeServices:
    def __init__(self, events: _FakeEventService | None = None) -> None:
        self._events = events
        self.bus = _NoopBus()

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self) -> _FakeEventService:
        assert self._events is not None
        return self._events


def _make_service(events: _FakeEventService | None = None):
    adapter = _InMemoryAdapter()
    service = TripleStoreService(adapter)
    if events is not None:
        service.set_services(_FakeServices(events))
    return service, adapter


def _filter_events(events: _FakeEventService, cls):
    return [e for e in events.published if isinstance(e, cls)]


def _one_triple_graph() -> Graph:
    g = Graph()
    g.add(
        (
            URIRef("http://example.org/s"),
            URIRef("http://example.org/p"),
            Literal("o"),
        )
    )
    return g


# ---------------------------------------------------------------------------
# Wiring / availability
# ---------------------------------------------------------------------------


def test_no_events_when_unwired() -> None:
    service, _ = _make_service()
    service.insert(_one_triple_graph(), graph_name=URIRef("http://example.org/g"))
    # No raise — and there's no event service to inspect.


def test_no_events_when_events_unavailable() -> None:
    service, _ = _make_service()
    service.set_services(_FakeServices(events=None))
    service.insert(_one_triple_graph(), graph_name=URIRef("http://example.org/g"))
    # Must not raise.


# ---------------------------------------------------------------------------
# Triple-level mutations
# ---------------------------------------------------------------------------


def test_insert_emits_triples_inserted() -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)
    events.published.clear()  # ignore constructor schema insert

    graph_name = URIRef("http://example.org/g/foo")
    triples = Graph()
    triples.add((URIRef("http://example.org/s1"), URIRef("http://example.org/p"), Literal("o1")))
    triples.add((URIRef("http://example.org/s2"), URIRef("http://example.org/p"), Literal("o2")))

    service.insert(triples, graph_name=graph_name)

    inserted = _filter_events(events, TriplesInserted)
    assert len(inserted) == 1
    evt = inserted[0]
    assert evt.graph_name == str(graph_name)
    assert evt.triple_count == 2


def test_remove_emits_triples_removed() -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)

    graph_name = URIRef("http://example.org/g/bar")
    triples = _one_triple_graph()
    service.insert(triples, graph_name=graph_name)
    events.published.clear()

    service.remove(triples, graph_name=graph_name)

    removed = _filter_events(events, TriplesRemoved)
    assert len(removed) == 1
    assert removed[0].graph_name == str(graph_name)
    assert removed[0].triple_count == 1


# ---------------------------------------------------------------------------
# Graph management
# ---------------------------------------------------------------------------


def test_create_graph_emits_graph_created() -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)
    events.published.clear()

    graph_name = URIRef("http://example.org/g/new")
    service.create_graph(graph_name)

    created = _filter_events(events, GraphCreated)
    assert len(created) == 1
    assert created[0].graph_name == str(graph_name)


def test_clear_graph_emits_graph_cleared() -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)
    events.published.clear()

    graph_name = URIRef("http://example.org/g/clr")
    service.clear_graph(graph_name)

    cleared = _filter_events(events, GraphCleared)
    assert len(cleared) == 1
    assert cleared[0].graph_name == str(graph_name)


def test_drop_graph_emits_graph_dropped() -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)
    events.published.clear()

    graph_name = URIRef("http://example.org/g/drop")
    service.drop_graph(graph_name)

    dropped = _filter_events(events, GraphDropped)
    assert len(dropped) == 1
    assert dropped[0].graph_name == str(graph_name)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _write_schema(tmp_path, name: str, ns_seed: int) -> str:
    path = tmp_path / name
    path.write_text(
        f"""@prefix ex: <http://example.org/{ns_seed}/> .

ex:Thing{ns_seed} a ex:Class .
""",
        encoding="utf-8",
    )
    return str(path)


def test_load_schema_emits_schema_loaded(tmp_path) -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)

    filepath = _write_schema(tmp_path, "schema.ttl", 1)
    events.published.clear()

    service.load_schema(filepath)

    loaded = _filter_events(events, SchemaLoaded)
    assert len(loaded) == 1
    assert loaded[0].filepath == filepath


def test_load_schemas_emits_one_schema_loaded_per_file(tmp_path) -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)

    filepaths = [_write_schema(tmp_path, f"s{i}.ttl", i) for i in range(4)]
    events.published.clear()

    service.load_schemas(filepaths)

    loaded = _filter_events(events, SchemaLoaded)
    assert len(loaded) == len(filepaths)
    assert {e.filepath for e in loaded} == set(filepaths)


def test_remove_schema_emits_schema_removed(tmp_path) -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)

    filepath = _write_schema(tmp_path, "schema.ttl", 2)
    service.load_schema(filepath)
    events.published.clear()

    service.remove_schema(filepath)

    removed = _filter_events(events, SchemaRemoved)
    assert len(removed) == 1
    assert removed[0].filepath == filepath


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class _FailingAdapter(_InMemoryAdapter):
    def create_graph(self, graph_name: URIRef):
        raise RuntimeError("backend offline")


def test_adapter_error_emits_triple_store_error_and_reraises() -> None:
    events = _FakeEventService()
    adapter = _FailingAdapter()
    service = TripleStoreService(adapter)
    service.set_services(_FakeServices(events))
    events.published.clear()

    graph_name = URIRef("http://example.org/g/fail")
    with pytest.raises(RuntimeError):
        service.create_graph(graph_name)

    errors = _filter_events(events, TripleStoreError)
    assert len(errors) == 1
    err = errors[0]
    assert err.operation == "create_graph"
    assert err.graph_name == str(graph_name)
    assert "backend offline" in (err.message or "")


def test_load_schema_error_emits_triple_store_error_and_reraises(
    tmp_path, monkeypatch
) -> None:
    events = _FakeEventService()
    service, _ = _make_service(events)

    filepath = _write_schema(tmp_path, "broken.ttl", 9)

    def _boom(_filepath, _entries):
        raise RuntimeError("schema parse failed")

    monkeypatch.setattr(service, "_apply_schema_for_file", _boom)
    events.published.clear()

    with pytest.raises(RuntimeError):
        service.load_schema(filepath)

    errors = _filter_events(events, TripleStoreError)
    assert len(errors) == 1
    assert errors[0].operation == "load_schema"
    assert errors[0].filepath == filepath
    assert "schema parse failed" in (errors[0].message or "")
    # SchemaLoaded must NOT be emitted on failure
    assert _filter_events(events, SchemaLoaded) == []


def test_publisher_exception_does_not_break_mutation() -> None:
    class _ExplodingEvents:
        def publish(self, event):
            raise RuntimeError("event bus down")

    adapter = _InMemoryAdapter()
    service = TripleStoreService(adapter)
    service.set_services(_FakeServices(_ExplodingEvents()))  # type: ignore[arg-type]

    # Must not raise even though the publisher blows up.
    service.insert(
        _one_triple_graph(), graph_name=URIRef("http://example.org/g/explode")
    )
