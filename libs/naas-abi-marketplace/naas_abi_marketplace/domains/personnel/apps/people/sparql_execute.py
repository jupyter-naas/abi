"""Run profile competency queries against the demo personnel graph."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from naas_abi_marketplace.domains.personnel.apps.people import sparql_queries as sq
from naas_abi_marketplace.domains.personnel.apps.people.profile_sparql import (
    SECTION_QUERY_NAMES,
)
from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE
from rdflib import Graph

PROFILE_QUERY_NAMES = frozenset(
    name for names in SECTION_QUERY_NAMES.values() for name in names
)
DEFAULT_MAX_ROWS = 50


class SparqlExecutionError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def personnel_graph() -> Graph:
    if not DEMO_GRAPH_FILE.is_file():
        raise SparqlExecutionError(f"Graph file not found: {DEMO_GRAPH_FILE}")
    graph = Graph()
    graph.parse(DEMO_GRAPH_FILE, format="turtle")
    return graph


def execute_profile_query(
    query_name: str,
    slug: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Run one allowed competency query and return tabular results."""
    if query_name not in PROFILE_QUERY_NAMES:
        raise KeyError(f"Query {query_name!r} is not exposed on profile pages")
    if max_rows < 1:
        raise ValueError("max_rows must be positive")

    sparql = sq.render_query_raw(query_name, slug=slug)
    graph = personnel_graph()

    columns: list[str] = []
    rows: list[list[str | None]] = []
    truncated = False
    try:
        for index, row in enumerate(graph.query(sparql)):
            if index >= max_rows:
                truncated = True
                break
            values = row.asdict()
            if not columns:
                columns = list(values.keys())
            rows.append(
                [
                    None if values.get(column) is None else str(values[column])
                    for column in columns
                ]
            )
    except Exception as exc:  # noqa: BLE001 - surface parse/runtime errors to API
        raise SparqlExecutionError(str(exc)) from exc

    return {
        "query_name": query_name,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
