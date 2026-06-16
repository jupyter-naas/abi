"""Tests for the spec-validation guards (AUDIT §7b.6 §2.1)."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.guards import (
    QueryGuards,
    clamp_limit,
    validate_spec,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    ClassAnchor,
    Column,
    FilterColumnTarget,
    FilterCondition,
    FilterGroup,
    FilterNot,
    ListSpec,
    PropertySource,
)

DOC = "http://ontology.naas.ai/documents#"
G = "http://ontology.naas.ai/graph/ws"


def _list(filters=None, graphs=(G,)) -> ListSpec:
    return ListSpec(
        graph_uris=graphs,
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("text", "string", PropertySource(DOC + "extracted_text")),),
        filters=filters,
    )


def test_valid_spec_passes() -> None:
    validate_spec(_list(filters=FilterCondition(FilterColumnTarget("text"), "eq", "x")))


def test_too_many_graphs_rejected() -> None:
    with pytest.raises(GraphQuerySpecError):
        validate_spec(_list(graphs=tuple(f"{G}{i}" for i in range(QueryGuards.MAX_GRAPHS + 1))))


def test_empty_graphs_rejected() -> None:
    with pytest.raises(GraphQuerySpecError):
        validate_spec(_list(graphs=()))


def test_deeply_nested_filter_rejected() -> None:
    node = FilterCondition(FilterColumnTarget("text"), "eq", "x")
    for _ in range(QueryGuards.MAX_FILTER_DEPTH + 2):
        node = FilterNot(node)
    with pytest.raises(GraphQuerySpecError):
        validate_spec(_list(filters=node))


def test_oversized_in_set_rejected() -> None:
    big = tuple(str(i) for i in range(QueryGuards.MAX_IN_SET + 1))
    with pytest.raises(GraphQuerySpecError):
        validate_spec(_list(filters=FilterCondition(FilterColumnTarget("text"), "in", big)))


def test_wide_filter_tree_rejected() -> None:
    children = tuple(FilterCondition(FilterColumnTarget("text"), "eq", str(i)) for i in range(QueryGuards.MAX_FILTER_NODES + 1))
    with pytest.raises(GraphQuerySpecError):
        validate_spec(_list(filters=FilterGroup("and", children)))


def test_clamp_limit() -> None:
    assert clamp_limit(None) == QueryGuards.DEFAULT_PAGE_LIMIT
    assert clamp_limit(250) == 250
    with pytest.raises(GraphQuerySpecError):
        clamp_limit(0)
    with pytest.raises(GraphQuerySpecError):
        clamp_limit(QueryGuards.MAX_PAGE_LIMIT + 1)
