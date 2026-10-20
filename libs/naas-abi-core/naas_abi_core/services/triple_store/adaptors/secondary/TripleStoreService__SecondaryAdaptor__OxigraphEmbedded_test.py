from concurrent.futures import ThreadPoolExecutor

import pytest
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)
from rdflib import Graph, Literal, URIRef


def _build_graph(subject: URIRef, index: int) -> Graph:
    graph = Graph()
    graph.add((subject, URIRef("http://example.org/p"), Literal(f"v-{index}")))
    return graph


class TestTripleStoreServiceSecondaryAdaptorOxigraphEmbedded(
    GenericTripleStoreSecondaryAdapterTest
):
    @pytest.fixture
    def adapter(self, tmp_path):
        pytest.importorskip("pyoxigraph")
        return TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(
            store_path=str(tmp_path / "oxigraph"),
        )

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return True

    @pytest.fixture
    def supports_graph_management(self) -> bool:
        return True


def test_oxigraph_embedded_persistence_across_restart(tmp_path):
    pytest.importorskip("pyoxigraph")

    path = str(tmp_path / "oxigraph")
    subject = URIRef("http://example.org/persist/s1")
    graph_name = URIRef("http://example.org/graph/persist")

    adapter = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(path)
    adapter.insert(_build_graph(subject, 1), graph_name)

    restarted = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(path)
    subject_graph = restarted.get_subject_graph(subject, graph_name)
    assert len(list(subject_graph.triples((subject, None, None)))) == 1


def test_oxigraph_embedded_concurrent_insert(tmp_path):
    pytest.importorskip("pyoxigraph")

    adapter = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(
        store_path=str(tmp_path / "oxigraph"),
    )
    subject = URIRef("http://example.org/shared")
    graph_name = URIRef("http://example.org/graph/concurrency")

    def _insert(i: int) -> None:
        adapter.insert(_build_graph(subject, i), graph_name)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_insert, range(20)))

    subject_graph = adapter.get_subject_graph(subject, graph_name)
    assert len(list(subject_graph.triples((subject, None, None)))) == 20


def test_oxigraph_embedded_creates_missing_parent_directories(tmp_path):
    pytest.importorskip("pyoxigraph")

    store_path = tmp_path / "missing" / "nested" / "oxigraph"
    adapter = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(
        store_path=str(store_path),
    )

    adapter.insert(
        _build_graph(URIRef("http://example.org/bootstrap"), 1),
        URIRef("http://example.org/graph/bootstrap"),
    )

    assert store_path.exists()


def test_streams_iterate_pyoxigraph_results_lazily(tmp_path, monkeypatch):
    from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
        TripleStoreService__SecondaryAdaptor__OxigraphEmbedded as Embedded,
    )
    from rdflib import BNode, Graph, Literal, URIRef
    from rdflib.namespace import XSD

    adapter = Embedded(str(tmp_path / "store"))
    graph_name = URIRef("http://test.example.org/stream/embedded")
    ex = "http://test.example.org/"
    g = Graph()
    g.add((URIRef(ex + "a"), URIRef(ex + "label"), Literal("plain")))
    g.add((URIRef(ex + "a"), URIRef(ex + "label"), Literal("anglais", lang="en")))
    g.add(
        (
            URIRef(ex + "a"),
            URIRef(ex + "when"),
            Literal("2026-10-03", datatype=XSD.date),
        )
    )
    adapter.insert(g, graph_name)
    monkeypatch.setattr(
        adapter,
        "query",
        lambda *a: (_ for _ in ()).throw(AssertionError("materialized")),
    )

    with adapter.query_stream(
        f"SELECT ?o ?missing WHERE {{ GRAPH <{graph_name}> {{ ?s ?p ?o }} }}"
    ) as result:
        assert result.vars == ["o", "missing"]
        assert {row["o"] for row in result.rows} == set(g.objects())
    with adapter.export(graph_name) as triples:
        assert set(triples) == set(g)
    with adapter.query_stream(
        f"ASK {{ GRAPH <{graph_name}> {{ ?s ?p 'plain' }} }}"
    ) as asked:
        assert asked.ask_answer is True
    with adapter.query_stream(
        "CONSTRUCT { _:b <http://test.example.org/p> 1 } WHERE {}"
    ) as built:
        ((subject, _, value),) = list(built.triples)
        assert isinstance(subject, BNode) and value == Literal(1)
