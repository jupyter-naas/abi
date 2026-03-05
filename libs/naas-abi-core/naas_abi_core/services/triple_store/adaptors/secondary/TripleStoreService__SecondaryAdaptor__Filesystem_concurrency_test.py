from concurrent.futures import ThreadPoolExecutor

from rdflib import Graph, Literal, URIRef

from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)


def _build_graph(subject: URIRef, index: int) -> Graph:
    graph = Graph()
    graph.add((subject, URIRef("http://example.org/p"), Literal(f"v-{index}")))
    return graph


def test_filesystem_adapter_persistence_across_restart(tmp_path):
    adapter = TripleStoreService__SecondaryAdaptor__Filesystem(
        store_path=str(tmp_path / "triplestore"),
        triples_path="triples",
    )
    subject = URIRef("http://example.org/s1")
    adapter.insert(_build_graph(subject, 1))

    restarted = TripleStoreService__SecondaryAdaptor__Filesystem(
        store_path=str(tmp_path / "triplestore"),
        triples_path="triples",
    )
    subject_graph = restarted.get_subject_graph(subject, "default")
    assert len(list(subject_graph.triples((subject, None, None)))) == 1


def test_filesystem_adapter_concurrent_insert(tmp_path):
    adapter = TripleStoreService__SecondaryAdaptor__Filesystem(
        store_path=str(tmp_path / "triplestore"),
        triples_path="triples",
    )
    subject = URIRef("http://example.org/shared")

    def _insert(i: int) -> None:
        adapter.insert(_build_graph(subject, i))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_insert, range(20)))

    subject_graph = adapter.get_subject_graph(subject, "default")
    assert len(list(subject_graph.triples((subject, None, None)))) == 20
