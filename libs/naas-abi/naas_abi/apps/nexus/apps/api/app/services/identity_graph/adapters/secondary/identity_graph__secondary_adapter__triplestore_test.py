from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__triplestore import (  # noqa: E501
    IdentityGraphStoreSecondaryAdapterTripleStore,
)
from rdflib import RDF, Graph, URIRef

GRAPH = URIRef("http://ontology.naas.ai/graph/nexus-identity")


class _RecordingTripleStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.inserted: list[Graph] = []

    def query(self, sparql: str) -> None:
        self.calls.append(("query", sparql))

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        self.calls.append(("insert", graph_name))
        self.inserted.append(triples)


def _graph() -> Graph:
    graph = Graph()
    graph.add((URIRef("http://ex.org/a"), RDF.type, URIRef("http://ex.org/A")))
    return graph


def test_replace_drops_the_named_graph_then_inserts() -> None:
    store = _RecordingTripleStore()

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store).replace_graph(GRAPH, _graph())

    assert store.calls == [
        ("query", f"DROP SILENT GRAPH <{GRAPH}>"),
        ("insert", GRAPH),
    ]


def test_an_empty_snapshot_drops_the_graph_and_inserts_nothing() -> None:
    store = _RecordingTripleStore()

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store).replace_graph(GRAPH, Graph())

    assert store.calls == [("query", f"DROP SILENT GRAPH <{GRAPH}>")]


def _graph_of(n: int) -> Graph:
    graph = Graph()
    for i in range(n):
        graph.add((URIRef(f"http://ex.org/s{i}"), RDF.type, URIRef("http://ex.org/A")))
    return graph


def test_a_large_snapshot_is_inserted_in_batches_that_add_up_to_it() -> None:
    store = _RecordingTripleStore()
    snapshot = _graph_of(5)

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store, batch_size=2).replace_graph(
        GRAPH, snapshot
    )

    assert store.calls[0] == ("query", f"DROP SILENT GRAPH <{GRAPH}>")
    assert [len(batch) for batch in store.inserted] == [2, 2, 1]
    union = Graph()
    for batch in store.inserted:
        union += batch
    assert set(union) == set(snapshot)


def test_a_snapshot_within_one_batch_is_one_insert() -> None:
    store = _RecordingTripleStore()

    IdentityGraphStoreSecondaryAdapterTripleStore(lambda: store, batch_size=10).replace_graph(
        GRAPH, _graph_of(10)
    )

    assert [len(batch) for batch in store.inserted] == [10]
