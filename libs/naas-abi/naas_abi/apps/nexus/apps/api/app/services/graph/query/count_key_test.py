"""Tests for the COUNT cache key (AUDIT §7b.6)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.query.count_key import count_cache_key
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    ClassAnchor,
    Column,
    FilterColumnTarget,
    FilterCondition,
    ListSpec,
    PropertySource,
    SortKey,
)

DOC = "http://ontology.naas.ai/documents#"
G = "http://ontology.naas.ai/graph/ws"


def _spec(*, sort: bool = False, filter_value: str = "x", graph: str = G) -> ListSpec:
    return ListSpec(
        graph_uris=(graph,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("text", "string", PropertySource(DOC + "extracted_text")),),
        filters=FilterCondition(FilterColumnTarget("text"), "contains", filter_value),
        sort=(SortKey("text", "asc"),) if sort else (),
    )


def test_same_spec_same_key() -> None:
    assert count_cache_key(_spec(), workspace_id="ws1") == count_cache_key(_spec(), workspace_id="ws1")


def test_sort_does_not_change_the_key() -> None:
    # COUNT is sort-invariant.
    assert count_cache_key(_spec(sort=False), workspace_id="ws1") == count_cache_key(_spec(sort=True), workspace_id="ws1")


def test_workspace_namespacing_prevents_collision() -> None:
    assert count_cache_key(_spec(), workspace_id="ws1") != count_cache_key(_spec(), workspace_id="ws2")


def test_filter_value_changes_the_key() -> None:
    assert count_cache_key(_spec(filter_value="a"), workspace_id="ws1") != count_cache_key(_spec(filter_value="b"), workspace_id="ws1")


def test_graph_changes_the_key() -> None:
    assert count_cache_key(_spec(graph=G), workspace_id="ws1") != count_cache_key(_spec(graph=G + "2"), workspace_id="ws1")


def test_key_is_namespaced() -> None:
    assert count_cache_key(_spec(), workspace_id="ws1").startswith("view_count_")
