"""Spec-validation guards (AUDIT §7b.6 §2.1).

Structural caps that reject a pathological spec **before** any SPARQL is emitted, raising
``GraphQuerySpecError`` (→ HTTP 400). Defense-in-depth alongside the compiler's own
reference checks: these bound the boolean-tree size, path depth, fan-out, and graph union
that the structural limits in the compiler don't fully cover.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    AggregateSpec,
    FilterCondition,
    FilterGroup,
    FilterNode,
    FilterNot,
    ListSpec,
)


class QueryGuards:
    MAX_GRAPHS = 25
    MAX_COLUMNS = 60
    MAX_FILTER_NODES = 100
    MAX_FILTER_DEPTH = 8
    MAX_PATH_HOPS = 8
    MAX_IN_SET = 1000
    MAX_PAGE_LIMIT = 5000
    DEFAULT_PAGE_LIMIT = 100
    MAX_FACET_CARDINALITY = 200


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return QueryGuards.DEFAULT_PAGE_LIMIT
    if limit < 1:
        raise GraphQuerySpecError("page limit must be >= 1")
    if limit > QueryGuards.MAX_PAGE_LIMIT:
        raise GraphQuerySpecError(f"page limit {limit} exceeds max {QueryGuards.MAX_PAGE_LIMIT}")
    return limit


def _walk_filter(node: FilterNode, depth: int) -> int:
    """Validate depth/fan-out and return the node count of this subtree."""
    if depth > QueryGuards.MAX_FILTER_DEPTH:
        raise GraphQuerySpecError(f"filter tree too deep (> {QueryGuards.MAX_FILTER_DEPTH})")
    if isinstance(node, FilterCondition):
        value = node.value
        if node.operator in ("in", "notIn") and isinstance(value, (list, tuple)):
            if len(value) > QueryGuards.MAX_IN_SET:
                raise GraphQuerySpecError(f"`{node.operator}` set exceeds {QueryGuards.MAX_IN_SET} values")
        return 1
    if isinstance(node, FilterGroup):
        return 1 + sum(_walk_filter(c, depth + 1) for c in node.children)
    if isinstance(node, FilterNot):
        return 1 + _walk_filter(node.child, depth + 1)
    raise GraphQuerySpecError("unknown filter node")


def validate_spec(spec: ListSpec | AggregateSpec) -> None:
    if len(spec.graph_uris) > QueryGuards.MAX_GRAPHS:
        raise GraphQuerySpecError(f"too many graphs ({len(spec.graph_uris)} > {QueryGuards.MAX_GRAPHS})")
    if not spec.graph_uris:
        raise GraphQuerySpecError("at least one graph_uri is required")

    if isinstance(spec, ListSpec):
        n_columns = len(spec.columns)
    else:
        n_columns = len(spec.group_by) + len(spec.measures)
    if n_columns > QueryGuards.MAX_COLUMNS:
        raise GraphQuerySpecError(f"too many columns ({n_columns} > {QueryGuards.MAX_COLUMNS})")

    if spec.filters is not None:
        total = _walk_filter(spec.filters, depth=1)
        if total > QueryGuards.MAX_FILTER_NODES:
            raise GraphQuerySpecError(f"filter tree too large ({total} > {QueryGuards.MAX_FILTER_NODES})")
