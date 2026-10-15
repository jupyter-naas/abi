"""Dataset tables as a tree: namespaces are containers, tables are items (``ns/name``).

Wraps the engine's ``DatasetService`` (sync, so calls run in a worker thread)
through its public API: ``list`` (namespaces come from the tables listed),
``describe``, ``query``, ``create``, ``write`` and ``drop``. A read shows the
schema and row count as ``#`` comment lines, then the first rows as CSV; a
download exports every row as CSV.

Writing CSV (header row first; leading ``#`` lines are skipped, so an edited
preview can be saved back):
- to an existing table, replaces all its rows (``mode="replace"``). Header
  columns must exist in the table; cells are converted to the column types and
  an empty cell is NULL.
- to a new ``ns/name``, creates the table with one ``string`` column per header
  column, then appends the rows.

Listings filter names on the server (``query``). Namespaces carry their table
count and names; tables carry their schema facts (columns, primary key,
partitions, column names) from the catalog listing, plus row counts from one
``UNION ALL`` count query per listed page (omitted when it fails). A read also
returns a ``table`` view: typed columns, the first rows, the total, the
primary key and partitions.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    paginate,
    text_preview,
)
from naas_abi_core import logger
from naas_abi_core.services.dataset.DatasetPort import (
    IDENTIFIER_PATTERN,
    ColumnSpec,
    DatasetInfo,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSpec,
)

SERVICE = "dataset"
TABLE_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
PREVIEW_ROWS = 50
SUMMARY_NAMES = 6
SUMMARY_COLUMNS = 8
WRITE_FORMAT = "CSV with a header row. Writing to an existing table replaces every row."
IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
TRUE = {"true", "t", "yes", "y", "1"}
FALSE = {"false", "f", "no", "n", "0"}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _split(resource_id: str) -> tuple[str, str] | None:
    """(namespace, table) when ``resource_id`` names a table, else None."""
    parts = resource_id.split("/")
    if len(parts) == 2 and all(IDENTIFIER.fullmatch(p) for p in parts):
        return parts[0], parts[1]
    return None


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _json_cell(value: Any) -> Any:
    """A cell the web can render as JSON (query results are mostly already)."""
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode()
    return str(value)


def _names(names: list[str], limit: int) -> str:
    shown = ", ".join(names[:limit])
    return shown + (f", +{len(names) - limit} more" if len(names) > limit else "")


def _partition(column: str, transform: str) -> str:
    return column if transform == "identity" else f"{column} ({transform})"


def _to_csv(columns: list[str], rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_cell(row.get(c)) for c in columns])
    return out.getvalue()


def _parse_csv(content: bytes) -> tuple[list[str], list[list[str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidResource(SERVICE, "CSV must be UTF-8 text") from exc
    lines = text.splitlines(keepends=True)
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    try:
        records = list(csv.reader(io.StringIO("".join(lines))))
    except csv.Error as exc:
        raise InvalidResource(SERVICE, f"invalid CSV: {exc}") from exc
    if not records or not any(h.strip() for h in records[0]):
        raise InvalidResource(SERVICE, "CSV needs a header row")
    header = [h.strip() for h in records[0]]
    if len(set(header)) != len(header):
        raise InvalidResource(SERVICE, "duplicate CSV columns")
    body = [r for r in records[1:] if r]
    for number, record in enumerate(body, start=2):
        if len(record) != len(header):
            raise InvalidResource(
                SERVICE, f"line {number} has {len(record)} cells for {len(header)} columns"
            )
    return header, body


def _convert(cell: str, column: ColumnSpec, line: int) -> Any:
    if cell == "":
        return None
    try:
        if column.type in ("integer", "bigint"):
            return int(cell)
        if column.type == "double":
            return float(cell)
        if column.type == "boolean":
            lowered = cell.strip().lower()
            if lowered in TRUE:
                return True
            if lowered in FALSE:
                return False
            raise ValueError(cell)
        if column.type == "json":
            json.loads(cell)  # the adapter parses it again; fail here with the line
    except ValueError as exc:
        raise InvalidResource(
            SERVICE, f"line {line}: {cell!r} is not a valid {column.type} for {column.name!r}"
        ) from exc
    return cell


class DatasetResources:
    service = SERVICE
    capabilities = ResourceCapabilities(
        browse=True, create=True, write_format=WRITE_FORMAT, search=True
    )

    def __init__(self, datasets: Any, *, preview_rows: int = PREVIEW_ROWS) -> None:
        self._datasets = datasets
        self._preview_rows = preview_rows

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _infos(self, namespace: str | None = None) -> list[DatasetInfo]:
        return list(self._datasets.list(namespace=namespace))

    def _describe(self, resource_id: str) -> DatasetInfo:
        parts = _split(resource_id)
        if parts is None:
            raise ResourceNotFound(SERVICE, resource_id)
        namespace, name = parts
        try:
            return self._datasets.describe(name, namespace=namespace)
        except DatasetNotFoundError as exc:
            raise ResourceNotFound(SERVICE, resource_id) from exc

    def _count(self, info: DatasetInfo) -> int:
        result = self._datasets.query(
            f"SELECT COUNT(*) AS n FROM {_quote(info.name)}",  # nosec B608 - identifier quoted
            namespace=info.namespace,
        )
        return int(result.rows[0]["n"]) if result.rows else 0

    @staticmethod
    def _table_entry(info: DatasetInfo, attributes: dict[str, str] | None = None) -> ResourceEntry:
        facts = {"columns": str(len(info.columns))}
        if info.primary_key:
            facts["primary_key"] = ", ".join(info.primary_key)
        if info.partitions:
            facts["partitions"] = ", ".join(
                _partition(p.column, p.transform) for p in info.partitions
            )
        facts["summary"] = _names([c.name for c in info.columns], SUMMARY_COLUMNS)
        return ResourceEntry(
            f"{info.namespace}/{info.name}",
            info.name,
            "item",
            TABLE_ACTIONS,
            attributes={**facts, **(attributes or {})},
        )

    def _page_counts(self, namespace: str, infos: list[DatasetInfo]) -> dict[str, int] | None:
        """Rows per table of one page in a single query, or None when it fails."""
        if not infos:
            return {}
        sql = " UNION ALL ".join(
            "SELECT '{}' AS t, COUNT(*) AS n FROM {}".format(  # nosec B608 - identifiers
                i.name.replace("'", "''"), _quote(i.name)
            )
            for i in infos
        )
        try:
            result = self._datasets.query(sql, namespace=namespace)
        except Exception as exc:  # noqa: BLE001 - counts are a nicety; the list still works
            logger.debug(f"sysadmin dataset: no row counts ({type(exc).__name__})")
            return None
        return {str(row["t"]): int(row["n"]) for row in result.rows}

    def _stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        if "/" not in resource_id:
            if IDENTIFIER.fullmatch(resource_id) and self._infos(resource_id):
                return ResourceEntry(resource_id, resource_id, "container")
            raise ResourceNotFound(SERVICE, resource_id)
        info = self._describe(resource_id)
        return self._table_entry(info, {"rows": str(self._count(info)), "media_type": "text/csv"})

    def _list(self, parent: str, cursor: str | None, limit: int, query: str | None) -> ResourcePage:
        needle = (query or "").lower()
        if parent == "":
            tables: dict[str, list[str]] = {}
            for info in self._infos():
                tables.setdefault(info.namespace, []).append(info.name)
            entries = [
                ResourceEntry(
                    ns,
                    ns,
                    "container",
                    attributes={
                        "tables": str(len(tables[ns])),
                        "summary": _names(sorted(tables[ns]), SUMMARY_NAMES),
                    },
                )
                for ns in sorted(tables)
                if needle in ns.lower()
            ]
            return paginate("", entries, cursor, limit)
        if "/" in parent:
            self._describe(parent)  # ResourceNotFound unless it is a table
            raise InvalidResource(SERVICE, f"{parent!r} is a table, not a namespace")
        infos = self._infos(parent) if IDENTIFIER.fullmatch(parent) else []
        if not infos:
            raise ResourceNotFound(SERVICE, parent)
        by_name = {i.name: i for i in infos if needle in i.name.lower()}
        stubs = [ResourceEntry(f"{parent}/{n}", n, "item") for n in sorted(by_name)]
        page = paginate(parent, stubs, cursor, limit)
        shown = [by_name[e.name] for e in page.entries]
        counts = self._page_counts(parent, shown)
        tables_shown = tuple(
            self._table_entry(
                i, {"rows": str(counts.get(i.name, 0))} if counts is not None else None
            )
            for i in shown
        )
        return replace(page, entries=tables_shown)

    def _rows(self, info: DatasetInfo, limit: int | None) -> tuple[list[str], list[dict[str, Any]]]:
        sql = f"SELECT * FROM {_quote(info.name)}"  # nosec B608 - identifier quoted
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        result = self._datasets.query(sql, namespace=info.namespace)
        return list(result.columns), list(result.rows)

    def _read(self, resource_id: str) -> ResourceDetail:
        entry = self._stat(resource_id)
        if entry.kind != "item":
            raise InvalidResource(SERVICE, f"{resource_id!r} is a namespace")
        info = self._describe(resource_id)
        total = int(entry.attributes["rows"])
        columns, rows = self._rows(info, self._preview_rows)
        header = [
            "# columns: " + ", ".join(f"{c.name} {c.type}" for c in info.columns),
            "# partitions: "
            + (", ".join(f"{p.column} {p.transform}" for p in info.partitions) or "none"),
            "# primary key: " + (", ".join(info.primary_key) or "none"),
            f"# rows: {total}",
        ]
        text = "\n".join(header) + "\n" + _to_csv(columns, rows)
        content = text_preview(text.encode())
        if total > len(rows):
            content = replace(content, truncated=True)
        view = {
            "type": "table",
            "columns": [{"name": c.name, "type": c.type} for c in info.columns],
            "rows": [[_json_cell(row.get(c.name)) for c in info.columns] for row in rows],
            "total": total,
            "primary_key": list(info.primary_key),
            "partitions": [{"column": p.column, "transform": p.transform} for p in info.partitions],
        }
        return ResourceDetail(entry, content, view)

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        info = self._describe(resource_id)
        total = self._count(info)
        if total > max_bytes:  # every CSV row takes at least one byte
            raise ResourceTooLarge(SERVICE, resource_id, total, max_bytes)
        columns, rows = self._rows(info, None)
        data = _to_csv(columns, rows).encode()
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        parts = _split(resource_id)
        if parts is None:
            raise InvalidResource(
                SERVICE, f"a table id is namespace/name with identifiers: {resource_id!r}"
            )
        namespace, name = parts
        header, body = _parse_csv(content)
        try:
            info: DatasetInfo | None = self._datasets.describe(name, namespace=namespace)
        except DatasetNotFoundError:
            info = None
        try:
            if info is None:
                self._create(namespace, name, header, body)
            else:
                columns = {c.name: c for c in info.columns}
                unknown = [h for h in header if h not in columns]
                if unknown:
                    raise InvalidResource(SERVICE, f"unknown columns: {', '.join(unknown)}")
                rows = [
                    {
                        h: _convert(cell, columns[h], line)
                        for h, cell in zip(header, record, strict=True)
                    }
                    for line, record in enumerate(body, start=2)
                ]
                self._datasets.write(name, rows, namespace=namespace, mode="replace")
        except (DatasetSchemaError, ValueError) as exc:  # pydantic errors are ValueErrors
            raise InvalidResource(SERVICE, str(exc)) from exc
        return self._stat(resource_id)

    def _create(self, namespace: str, name: str, header: list[str], body: list[list[str]]) -> None:
        spec = DatasetSpec(
            name=name,
            namespace=namespace,
            columns=tuple(ColumnSpec(name=h, type="string") for h in header),
        )
        self._datasets.create(spec)
        rows = [dict(zip(header, (c or None for c in record), strict=True)) for record in body]
        if not rows:
            return
        try:
            self._datasets.write(name, rows, namespace=namespace, mode="append")
        except Exception:
            # No half-made table: the create and its first rows succeed together.
            self._datasets.drop(name, namespace=namespace)
            raise

    def _delete(self, resource_id: str) -> None:
        info = self._describe(resource_id)
        try:
            self._datasets.drop(info.name, namespace=info.namespace)
        except DatasetNotFoundError as exc:
            raise ResourceNotFound(SERVICE, resource_id) from exc

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit, options.get("query"))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await asyncio.to_thread(self._write, resource_id, content)

    async def delete(self, resource_id: str) -> None:
        await asyncio.to_thread(self._delete, resource_id)
