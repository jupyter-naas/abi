from concurrent.futures import ThreadPoolExecutor

import pytest
from rdflib import Graph, Literal, URIRef

from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
)
from naas_abi_core.services.triple_store.tests.triple_store__secondary_adapter__generic_test import (
    GenericTripleStoreSecondaryAdapterTest,
)


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
