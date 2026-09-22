"""Tests for shared X orchestration helpers."""

from unittest.mock import patch

from naas_abi_marketplace.applications.x.orchestrations.utils import (
    search_envelope_fully_projected,
    search_envelope_in_dataset,
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
    def __init__(self, triple_store, *, dataset_rows: list[dict] | None = None):
        self.triple_store = triple_store
        self._dataset_rows = dataset_rows or []
        self.dataset = _FakeDataset(self._dataset_rows)

    def dataset_available(self) -> bool:
        return True


class _FakeEngine:
    def __init__(self, triple_store, *, dataset_rows: list[dict] | None = None):
        self.services = _FakeServices(triple_store, dataset_rows=dataset_rows)


class _FakeConfig:
    graph_name = _GRAPH
    ontology_namespace = _NS


class _FakeModule:
    def __init__(self, triple_store, *, dataset_rows: list[dict] | None = None):
        self.engine = _FakeEngine(triple_store, dataset_rows=dataset_rows)
        self.configuration = _FakeConfig()


class _FakeDataset:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def query(self, sql: str, *, namespace: str):  # noqa: ARG002
        class _Result:
            def __init__(self, rows):
                self.rows = rows

        if "envelopes_v1" in sql and "WHERE envelope_path =" in sql:
            path = sql.split("WHERE envelope_path = '", 1)[-1].split("'", 1)[0]
            path = path.replace("''", "'")
            matched = [r for r in self._rows if r.get("envelope_path") == path]
            return _Result(matched[:1])
        return _Result([])


def _module_with_result_set(file_path: str) -> _FakeModule:
    dataset = Dataset()
    graph = dataset.graph(URIRef(_GRAPH))
    rs = URIRef(f"{_NS}SearchResultSet/abc")
    graph.add((rs, RDF.type, URIRef(f"{_NS}SearchResultSet")))
    graph.add((rs, URIRef(f"{_NS}file_path"), Literal(file_path)))
    return _FakeModule(_FakeTripleStore(dataset))


def test_search_envelope_ingested_true_when_file_path_present():
    path = "x/search_recent_tweets/example_feed/2026-07-24T12:00:00_example.json"
    module = _module_with_result_set(path)
    assert search_envelope_ingested(module, path) is True


def test_search_envelope_ingested_false_for_unknown_file():
    module = _module_with_result_set("x/search_recent_tweets/a/known.json")
    assert (
        search_envelope_ingested(module, "x/search_recent_tweets/a/other.json") is False
    )


def test_search_envelope_ingested_false_on_empty_graph():
    module = _FakeModule(_FakeTripleStore(Dataset()))
    assert search_envelope_ingested(module, "x/anything.json") is False


@patch(
    "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store.ensure_x_datasets",
    lambda _dataset: None,
)
def test_search_envelope_fully_projected_false_when_graph_only():
    path = "x/search_recent_tweets/example_feed/2026-07-24T12:00:00_example.json"
    module = _module_with_result_set(path)
    assert search_envelope_in_dataset(module, path) is False
    assert search_envelope_fully_projected(module, path) is False


@patch(
    "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store.ensure_x_datasets",
    lambda _dataset: None,
)
def test_search_envelope_fully_projected_true_when_graph_and_dataset():
    path = "x/search_recent_tweets/example_feed/2026-07-24T12:00:00_example.json"
    module = _module_with_result_set(path)
    module.engine.services.dataset = _FakeDataset([{"envelope_path": path}])
    assert search_envelope_fully_projected(module, path) is True
