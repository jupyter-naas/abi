"""In-memory people tables built from SPARQL export rows."""

from __future__ import annotations

import re
from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    export_people_from_graph as export,
)
from rdflib import Graph

_SLUG_EQ = re.compile(r"^slug\s*=\s*(?P<lit>'(?:''|[^'])*')\s*$", re.I)
_FACET_NE = re.compile(
    r"^(?P<field>[a-z_]+)\s*=\s*(?P<lit>'(?:''|[^'])*')\s*AND\s*slug\s*<>\s*(?P<slug>'(?:''|[^'])*')\s*$",
    re.I,
)
_SEARCH_LIKE_GROUP = re.compile(
    r"\(\s*search_text\s+LIKE\s+'(?P<p1>(?:''|[^'])*)'\s+OR\s+search_text\s+LIKE\s+'(?P<p2>(?:''|[^'])*)'\s*\)",
    re.I,
)


def _unquote_sql_literal(literal: str) -> str:
    text = literal.strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


class MemoryPeopleStore:
    """In-memory people tables built from SPARQL over a graph."""

    def __init__(
        self, tables: dict[str, list[dict[str, Any]]], config: dict[str, Any]
    ) -> None:
        self._tables = tables
        self._table_by_logical = dict(config["data"]["tables"])
        self._logical_by_physical = {
            physical: logical for logical, physical in self._table_by_logical.items()
        }

    @classmethod
    def from_graph(cls, graph: Graph, config: dict[str, Any]) -> MemoryPeopleStore:
        tables = export.build_rows(graph, config)
        export.gate_rows(tables, config)
        return cls(tables, config)

    def _people_rows(self) -> list[dict[str, Any]]:
        return list(self._tables.get("people", []))

    def _match_like_literals(self, row: dict[str, Any], p1: str, p2: str) -> bool:
        text = str(row.get("search_text") or "")
        prefix = p1.rstrip("%")
        infix = p2.strip("%").lstrip()
        return text.startswith(prefix) or f" {infix}" in text

    def _filter_people(self, where: str) -> list[dict[str, Any]]:
        clause = (where or "").strip()
        rows = self._people_rows()
        if not clause:
            return rows
        slug_match = _SLUG_EQ.match(clause)
        if slug_match:
            slug = _unquote_sql_literal(slug_match.group("lit"))
            return [row for row in rows if row.get("slug") == slug]
        facet_match = _FACET_NE.match(clause)
        if facet_match:
            field = facet_match.group("field")
            value = _unquote_sql_literal(facet_match.group("lit"))
            slug = _unquote_sql_literal(facet_match.group("slug"))
            return [
                row
                for row in rows
                if row.get(field) == value and row.get("slug") != slug
            ]
        groups = _SEARCH_LIKE_GROUP.findall(clause)
        if groups:
            hits: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                slug = str(row.get("slug") or "")
                if slug in seen:
                    continue
                if any(
                    self._match_like_literals(row, p1, p2) for p1, p2 in groups
                ):
                    hits.append(row)
                    seen.add(slug)
            return hits
        return rows

    def fetch_people(
        self,
        *,
        namespace: str,
        table: str,
        where: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        del namespace, table
        rows = sorted(
            self._filter_people(where), key=lambda row: str(row.get("full_name") or "")
        )
        if limit is not None:
            rows = rows[: int(limit)]
        return rows

    def fetch_children(
        self,
        *,
        namespace: str,
        table: str,
        slugs: list[str],
        order_by: str = "seq",
    ) -> dict[str, list[dict[str, Any]]]:
        del namespace
        logical = self._logical_by_physical.get(table, table)
        rows = self._tables.get(logical, [])
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            slug = row.get("slug")
            if slug not in slugs:
                continue
            grouped.setdefault(str(slug), []).append(dict(row))
        for slug, items in grouped.items():
            if order_by == "skill_name":
                items.sort(key=lambda item: str(item.get("skill_name") or ""))
            else:
                items.sort(
                    key=lambda item: (
                        int(item.get("seq") or 0),
                        str(item.get("skill_name") or ""),
                    )
                )
            grouped[slug] = items
        return grouped


PeopleStore = DatasetService | MemoryPeopleStore
