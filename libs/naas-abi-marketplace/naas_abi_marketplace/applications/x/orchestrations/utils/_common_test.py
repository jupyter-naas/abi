"""Tests for shared X orchestration helpers."""

from naas_abi_marketplace.applications.x.orchestrations.utils import (
    search_envelope_ingested,
)
from rdflib import RDF, Dataset, Literal, URIRef

_NS = "http://ontology.naas.ai/x/"
_GRAPH = "http://ontology.naas.ai/graph/x"


class _FakeTripleStore:
    def __init__(self, dataset: Dataset):
        self._dataset = dataset

    def query(self, sparql: str):
        return self._dataset.query(sparql)


class _FakeServices:
    def __init__(self, triple_store):
        self.triple_store = triple_store


class _FakeEngine:
    def __init__(self, triple_store):
        self.services = _FakeServices(triple_store)


class _FakeConfig:
    graph_name = _GRAPH
    ontology_namespace = _NS


class _FakeModule:
    def __init__(self, triple_store):
        self.engine = _FakeEngine(triple_store)
        self.configuration = _FakeConfig()


def _module_with_result_set(file_path: str) -> _FakeModule:
    dataset = Dataset()
    graph = dataset.graph(URIRef(_GRAPH))
    rs = URIRef(f"{_NS}SearchResultSet/abc")
    graph.add((rs, RDF.type, URIRef(f"{_NS}SearchResultSet")))
    graph.add((rs, URIRef(f"{_NS}file_path"), Literal(file_path)))
    return _FakeModule(_FakeTripleStore(dataset))


def test_search_envelope_ingested_true_when_file_path_present():
    path = "x/search_recent_tweets/drones_and_uas/2026-07-24T12:00:00_drones.json"
    module = _module_with_result_set(path)
    assert search_envelope_ingested(module, path) is True


def test_search_envelope_ingested_false_for_unknown_file():
    module = _module_with_result_set("x/search_recent_tweets/a/known.json")
    assert search_envelope_ingested(module, "x/search_recent_tweets/a/other.json") is False


def test_search_envelope_ingested_false_on_empty_graph():
    module = _FakeModule(_FakeTripleStore(Dataset()))
    assert search_envelope_ingested(module, "x/anything.json") is False
