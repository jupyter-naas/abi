"""The datasets a SQL query reads, from DuckDB's parser.

``dataset:Query`` needs ``Query`` on every dataset the SQL references. A
reference is resolved against the query's namespace: ``orders`` is
``<namespace>/orders`` and ``sales.orders`` is ``sales/orders``. Anything the
check cannot vouch for is refused with ``DatasetRequestRefused`` (``INVALID_ARGUMENT``):

* a statement other than ``SELECT`` (``ATTACH``, ``COPY``, ``PIVOT``, DDL, ...);
* more than one statement;
* a table function that reads files or catalogs (``read_csv``,
  ``duckdb_tables``, ``query``, ...), or a ``SHOW``;
* a three-part or system-schema name;
* a name that is not a dataset identifier (``DatasetPort.IDENTIFIER_PATTERN``):
  DuckDB reads ``FROM '/path/x.csv'`` as a file (a replacement scan).

A CTE hides a dataset of its name only in its own query and the queries nested
in it, as DuckDB resolves it; a CTE's name may be any name. A recursive CTE's
anchor does not see the CTE itself, so a table of its name there is a dataset.
Names are compared without case, as DuckDB does. ``DatasetService`` then
refuses any name the catalog does not hold (a DuckDB view, the lake's own
metadata tables) and maps the others to the catalog's own spelling.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator, Iterator
from typing import Any

from naas_abi_core.services.dataset.DatasetPort import (
    IDENTIFIER_PATTERN,
    DatasetRequestRefused,
)

# Table functions that read nothing but their arguments.
SAFE_TABLE_FUNCTIONS = frozenset({"range", "generate_series", "unnest"})
# Table references a plain read is made of; any other kind is refused.
_PLAIN = frozenset({"BASE_TABLE", "JOIN", "SUBQUERY", "EXPRESSION_LIST", "EMPTY_FROM"})
_TABLE_REFS = _PLAIN | frozenset(
    {"TABLE_FUNCTION", "PIVOT", "SHOW_REF", "COLUMN_DATA", "DELIM_GET", "INVALID"}
)
# What a dataset or namespace name can be (``DatasetSpec``); anything else may
# be a file path DuckDB would scan.
_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_SYSTEM_SCHEMAS = frozenset(
    {"main", "system", "temp", "memory", "information_schema", "pg_catalog"}
)


def referenced_datasets(sql: str, namespace: str) -> list[tuple[str, str]]:
    """``(namespace, name)`` of every dataset ``sql`` reads, in order, once each."""
    import duckdb

    connection = duckdb.connect()
    try:
        raw = connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()
    finally:
        connection.close()
    tree = json.loads(raw[0]) if raw else {}
    if tree.get("error"):
        raise DatasetRequestRefused(
            "Only a single SELECT can be authorized: "
            f"{tree.get('error_message') or 'unparsable query'}"
        )
    statements = tree.get("statements") or []
    if len(statements) != 1:
        raise DatasetRequestRefused("Exactly one SELECT statement is allowed")
    references: list[tuple[str, str]] = []
    for ref, ctes in _table_refs(statements[0], frozenset()):
        kind = ref["type"]
        if kind == "TABLE_FUNCTION":
            function = ref.get("function") or {}
            name = str(function.get("function_name", "")).lower()
            if name not in SAFE_TABLE_FUNCTIONS:
                raise DatasetRequestRefused(
                    f"Table function {name or '?'} is not allowed"
                )
            continue
        if kind not in _PLAIN:
            raise DatasetRequestRefused(f"{kind} is not allowed in a dataset query")
        if kind != "BASE_TABLE":
            continue
        catalog = ref.get("catalog_name") or ""
        schema = ref.get("schema_name") or ""
        table = ref.get("table_name") or ""
        if catalog:
            raise DatasetRequestRefused(
                f"Name the dataset as <namespace>.<name>, not {catalog}.…"
            )
        if not schema and table.lower() in ctes:
            continue
        for part in (schema, table) if schema else (table,):
            if not _IDENTIFIER.fullmatch(part):
                raise DatasetRequestRefused(
                    f"{part!r} is not a dataset or namespace name"
                )
        if not schema:
            resolved = (namespace, table)
        elif schema.lower() in _SYSTEM_SCHEMAS:
            raise DatasetRequestRefused(f"Schema {schema} is not a dataset namespace")
        else:
            resolved = (schema, table)
        if resolved not in references:
            references.append(resolved)
    return references


def _nodes(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _table_refs(
    value: Any, ctes: frozenset[str]
) -> Iterator[tuple[dict[str, Any], frozenset[str]]]:
    """Every table reference, with the CTE names in scope where it sits.

    A query node's CTEs cover its own body and the queries nested in it; a
    CTE's body sees the CTEs defined before it, and itself when recursive, in
    its recursive part only: the anchor runs before the CTE exists.
    """
    if isinstance(value, list):
        for child in value:
            yield from _table_refs(child, ctes)
        return
    if not isinstance(value, dict):
        return
    cte_map = value.get("cte_map")
    if isinstance(cte_map, dict):
        scope = yield from _cte_refs(cte_map, ctes)
        for key, child in value.items():
            if key != "cte_map":
                yield from _table_refs(child, scope)
        return
    kind = value.get("type")
    if isinstance(kind, str) and kind in _TABLE_REFS and "alias" in value:
        yield value, ctes
    for child in value.values():
        yield from _table_refs(child, ctes)


def _cte_refs(
    cte_map: dict[str, Any], ctes: frozenset[str]
) -> Generator[tuple[dict[str, Any], frozenset[str]], None, frozenset[str]]:
    """The references in a ``WITH``'s CTE bodies; returns the scope the
    ``WITH`` gives its query: ``ctes`` and each of its names."""
    inner = set(ctes)
    for entry in cte_map.get("map") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("key") or "").lower()
        body = entry.get("value")
        outer = frozenset(inner)
        node = _recursive_node(body)
        if node is None:
            yield from _table_refs(body, outer)
        else:
            # A WITH inside the recursive CTE belongs to its node: both parts
            # see it; only the recursive part sees the CTE itself.
            own = node.get("cte_map")
            local = (
                (yield from _cte_refs(own, outer)) if isinstance(own, dict) else outer
            )
            yield from _table_refs(node.get("left"), local)
            yield from _table_refs(
                {k: v for k, v in node.items() if k not in ("left", "cte_map")},
                local | {name},
            )
        inner.add(name)
    return frozenset(inner)


def _recursive_node(body: Any) -> dict[str, Any] | None:
    """A recursive CTE's node (``left`` is its anchor), else None."""
    query = body.get("query") if isinstance(body, dict) else None
    node = query.get("node") if isinstance(query, dict) else None
    if isinstance(node, dict) and node.get("type") == "RECURSIVE_CTE_NODE":
        return node
    return None
