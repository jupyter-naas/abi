"""Tests for the per-graph people datasets (the workspace_dataset read model).

Against a real DuckLake warehouse in a temporary directory, as in datasets_test:
the namespaces, the writes and the snapshot versions are what is under test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    graph_datasets as gd,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    search_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    DEMO_GRAPH_FILE,
)
from rdflib import Graph

WS_PEOPLE = "http://ontology.naas.ai/graph/ws-1fe2cd925ef1/people"
OTHER_PEOPLE = "http://ontology.naas.ai/graph/ws-other/people"


@pytest.fixture
def warehouse(tmp_path: Path) -> DatasetService:
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )


@pytest.fixture
def config() -> dict[str, Any]:
    return load_config()


@pytest.fixture(scope="module")
def demo_graph() -> Graph:
    graph = Graph()
    graph.parse(DEMO_GRAPH_FILE, format="turtle")
    return graph


def test_namespace_is_named_after_the_graph(config: dict[str, Any]) -> None:
    assert gd.graph_namespace(config, WS_PEOPLE) == "people__ws_1fe2cd925ef1_people"


def test_namespace_of_an_iri_without_graph_segment(config: dict[str, Any]) -> None:
    assert gd.graph_namespace(config, "urn:x:People") == "people__urn_x_people"


def test_materialize_then_load_serves_search(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    result = gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)

    assert result["people"] > 0
    store = gd.load_store(warehouse, config, [result["namespace"]])
    payload = search_payload.search(store, config, query="", facet="", page=1)
    assert payload["total"] == result["people"]


def test_empty_graph_is_an_empty_directory_not_a_missing_one(
    warehouse: DatasetService, config: dict[str, Any]
) -> None:
    result = gd.materialize_graph(warehouse, config, WS_PEOPLE, Graph())

    assert result["people"] == 0
    assert gd.dataset_version(warehouse, config, result["namespace"]) is not None
    store = gd.load_store(warehouse, config, [result["namespace"]])
    assert (
        search_payload.search(store, config, query="", facet="", page=1)["total"] == 0
    )


def test_never_materialized_names_the_sync_job(
    warehouse: DatasetService, config: dict[str, Any]
) -> None:
    with pytest.raises(ds.DatasetsMissingError) as raised:
        gd.load_store(warehouse, config, [gd.graph_namespace(config, WS_PEOPLE)])
    assert "people_intelligence_sync_workspace_people_job" in raised.value.command


def test_unsynced_graphs_are_skipped_when_another_is_there(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    written = gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)
    missing = gd.graph_namespace(config, OTHER_PEOPLE)

    store = gd.load_store(warehouse, config, [missing, written["namespace"]])

    payload = search_payload.search(store, config, query="", facet="", page=1)
    assert payload["total"] == written["people"]


def test_a_person_in_two_graphs_is_listed_once(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    first = gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)
    second = gd.materialize_graph(warehouse, config, OTHER_PEOPLE, demo_graph)

    store = gd.load_store(warehouse, config, [first["namespace"], second["namespace"]])

    payload = search_payload.search(store, config, query="", facet="", page=1)
    assert payload["total"] == first["people"]


def test_rematerializing_moves_the_snapshot(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    namespace = gd.materialize_graph(warehouse, config, WS_PEOPLE, Graph())["namespace"]
    before = gd.dataset_version(warehouse, config, namespace)

    gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)

    assert gd.dataset_version(warehouse, config, namespace) != before


def test_writing_another_graph_leaves_the_version_alone(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    namespace = gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)[
        "namespace"
    ]
    before = gd.dataset_version(warehouse, config, namespace)

    gd.materialize_graph(warehouse, config, OTHER_PEOPLE, Graph())

    assert gd.dataset_version(warehouse, config, namespace) == before


def test_a_section_table_a_sync_left_unwritten_reads_as_empty(
    warehouse: DatasetService, config: dict[str, Any], demo_graph: Graph
) -> None:
    written = gd.materialize_graph(warehouse, config, WS_PEOPLE, demo_graph)
    warehouse.drop(
        config["data"]["tables"]["education"], namespace=written["namespace"]
    )

    tables = gd.read_namespace(warehouse, config, written["namespace"])

    assert tables is not None
    assert tables["education"] == []
    assert len(tables["people"]) == written["people"]
