from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__triplestore import (  # noqa: E501
    IdentityGraphStoreSecondaryAdapterTripleStore,
)
from rdflib import RDF, Graph, URIRef

GRAPH = URIRef("http://ontology.naas.ai/graph/nexus-identity")


class _RecordingTripleStore:
    def __init__(self, graphs: list[URIRef]) -> None:
        self.graphs = list(graphs)
        self.calls: list[tuple[str, URIRef]] = []
        self.inserted: list[Graph] = []

    def list_graphs(self) -> list[URIRef]:
        return list(self.graphs)

    def create_graph(self, graph_name: URIRef) -> None:
        self.calls.append(("create", graph_name))
        self.graphs.append(graph_name)

    def clear_graph(self, graph_name: URIRef) -> None:
        self.calls.append(("clear", graph_name))

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        self.calls.append(("insert", graph_name))
        self.inserted.append(triples)


def _graph() -> Graph:
    graph = Graph()
    graph.add((URIRef("http://ex.org/a"), RDF.type, URIRef("http://ex.org/A")))
    return graph


def test_first_sync_creates_the_graph_then_inserts() -> None:
    store = _RecordingTripleStore(graphs=[])

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store).replace_graph(GRAPH, _graph())

    assert store.calls == [("create", GRAPH), ("insert", GRAPH)]


def test_later_syncs_clear_before_inserting_so_deleted_users_disappear() -> None:
    store = _RecordingTripleStore(graphs=[GRAPH])

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store).replace_graph(GRAPH, _graph())

    assert store.calls == [("clear", GRAPH), ("insert", GRAPH)]


def test_an_empty_snapshot_still_clears_but_inserts_nothing() -> None:
    store = _RecordingTripleStore(graphs=[GRAPH])

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store).replace_graph(GRAPH, Graph())

    assert store.calls == [("clear", GRAPH)]
