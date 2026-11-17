"""Fakes of the engine services the X app code reaches, for its tests.

``FakeDataset`` is the SDK dataset service (blocking, as ``SyncModule`` gives
it) over an in-memory DuckDB: the X code's SQL really runs. Every query first
passes the check the engine's dataset service makes for a module's account
(core ``services/dataset/sql_references.py``, rewritten here: the modules
cannot import core): a single ``SELECT``, no table function but ``range``,
``generate_series`` and ``unnest``, no three-part or system-schema name, and
every name it reads a dataset of the catalog. What the engine would refuse
raises the ``ServiceError`` a remote module gets (``INVALID_ARGUMENT``,
``DATASET_NOT_FOUND``).

``MemoryObjectStorage`` is the blocking object storage, and ``ThreadedSync`` a
``SyncModule`` whose ``call`` / ``threaded`` run on ``x-sync`` threads as the
real one (``on_sync_thread`` tells them apart). Import this module from
tests only: it needs ``duckdb`` (the ``dev`` dependency group).
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import duckdb
from naas_abi_sdk.services.errors import ObjectNotFound, ServiceError
from naas_abi_sdk.services.models import DatasetInfo, DatasetSpec, QueryResult

_SAFE_TABLE_FUNCTIONS = frozenset({"range", "generate_series", "unnest"})
_PLAIN = frozenset({"BASE_TABLE", "JOIN", "SUBQUERY", "EXPRESSION_LIST", "EMPTY_FROM"})
_TABLE_REFS = _PLAIN | frozenset(
    {"TABLE_FUNCTION", "PIVOT", "SHOW_REF", "COLUMN_DATA", "DELIM_GET", "INVALID"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SYSTEM_SCHEMAS = frozenset(
    {"main", "system", "temp", "memory", "information_schema", "pg_catalog"}
)
_TYPES = {
    "string": "VARCHAR",
    "integer": "BIGINT",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "json": "JSON",
}


def _refused(message: str) -> ServiceError:
    return ServiceError("INVALID_ARGUMENT", message)


def referenced_datasets(sql: str, namespace: str) -> list[tuple[str, str]]:
    """``(namespace, name)`` of every dataset ``sql`` reads; raises as the
    engine's check refuses (core ``sql_references.referenced_datasets``)."""
    connection = duckdb.connect()
    try:
        raw = connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()
    finally:
        connection.close()
    tree = json.loads(raw[0]) if raw else {}
    if tree.get("error"):
        raise _refused(f"Only a single SELECT can be authorized: {tree}")
    statements = tree.get("statements") or []
    if len(statements) != 1:
        raise _refused("Exactly one SELECT statement is allowed")
    found: list[tuple[str, str]] = []
    for ref, ctes in _table_refs(statements[0], frozenset()):
        kind = ref["type"]
        if kind == "TABLE_FUNCTION":
            name = str((ref.get("function") or {}).get("function_name", "")).lower()
            if name not in _SAFE_TABLE_FUNCTIONS:
                raise _refused(f"Table function {name or '?'} is not allowed")
            continue
        if kind not in _PLAIN:
            raise _refused(f"{kind} is not allowed in a dataset query")
        if kind != "BASE_TABLE":
            continue
        catalog = ref.get("catalog_name") or ""
        schema = ref.get("schema_name") or ""
        table = ref.get("table_name") or ""
        if catalog:
            raise _refused("Name the dataset as <namespace>.<name>")
        if not schema and table.lower() in ctes:
            continue
        for part in (schema, table) if schema else (table,):
            if not _IDENTIFIER.fullmatch(part):
                raise _refused(f"{part!r} is not a dataset or namespace name")
        if schema.lower() in _SYSTEM_SCHEMAS:
            raise _refused(f"Schema {schema} is not a dataset namespace")
        resolved = (schema or namespace, table)
        if resolved not in found:
            found.append(resolved)
    return found


def _table_refs(
    value: Any, ctes: frozenset[str]
) -> Iterator[tuple[dict[str, Any], frozenset[str]]]:
    if isinstance(value, list):
        for child in value:
            yield from _table_refs(child, ctes)
        return
    if not isinstance(value, dict):
        return
    cte_map = value.get("cte_map")
    if isinstance(cte_map, dict):
        scope = set(ctes)
        for entry in cte_map.get("map") or []:
            if not isinstance(entry, dict):
                continue
            yield from _table_refs(entry.get("value"), frozenset(scope))
            scope.add(str(entry.get("key") or "").lower())
        for key, child in value.items():
            if key != "cte_map":
                yield from _table_refs(child, frozenset(scope))
        return
    kind = value.get("type")
    if isinstance(kind, str) and kind in _TABLE_REFS and "alias" in value:
        yield value, ctes
    for child in value.values():
        yield from _table_refs(child, ctes)


def _timestamp(value: Any) -> Any:
    """A timestamp as the dataset stores it: UTC, without offset."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def _value(value: Any) -> Any:
    """A cell as the dataset service returns it: dates and times ISO-8601."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


class FakeDataset:
    """The SDK dataset service, blocking, over one in-memory DuckDB."""

    def __init__(self) -> None:
        self.connection = duckdb.connect()
        self.specs: dict[tuple[str, str], DatasetSpec] = {}
        self.queries: list[str] = []
        self.writes: list[tuple[str, str, int]] = []
        self.maintenance: list[tuple[str, str]] = []

    @staticmethod
    def _schema(namespace: str) -> str:
        return f'"ns_{namespace}"'

    def _info(self, spec: DatasetSpec) -> DatasetInfo:
        return DatasetInfo(
            name=spec.name,
            namespace=spec.namespace,
            columns=list(spec.columns),
            partitions=list(spec.partitions),
            primary_key=list(spec.primary_key),
        )

    def _spec(self, name: str, namespace: str) -> DatasetSpec:
        spec = self.specs.get((namespace, name.lower()))
        if spec is None:
            raise ServiceError("DATASET_NOT_FOUND", f"{namespace}/{name}")
        return spec

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        key = (spec.namespace, spec.name.lower())
        if key in self.specs:
            raise ServiceError("DATASET_ALREADY_EXISTS", f"{key}")
        schema = self._schema(spec.namespace)
        columns = ", ".join(
            f'"{column.name}" {_TYPES[column.type]}' for column in spec.columns
        )
        self.connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.connection.execute(f'CREATE TABLE {schema}."{spec.name}" ({columns})')
        self.specs[key] = replace(spec)
        return self._info(spec)

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        return self._info(self._spec(name, namespace))

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        return [
            self._info(spec)
            for (ns, _), spec in sorted(self.specs.items())
            if namespace is None or ns == namespace
        ]

    def write(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: str = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        spec = self._spec(name, namespace)
        table = f'{self._schema(namespace)}."{spec.name}"'
        names = [column.name for column in spec.columns]
        for row in rows:
            unknown = set(row) - set(names)
            if unknown:
                raise ServiceError("INVALID_ARGUMENT", f"unknown columns {unknown}")
        if mode == "replace":
            self.connection.execute(f"DELETE FROM {table}")
        elif mode == "upsert":
            keys = list(spec.primary_key)
            seen = [tuple(row.get(k) for k in keys) for row in rows]
            if len(set(seen)) != len(seen):
                raise ServiceError("INVALID_ARGUMENT", "duplicate upsert keys")
            for key in seen:
                where = " AND ".join(f'"{k}" = ?' for k in keys)
                self.connection.execute(f"DELETE FROM {table} WHERE {where}", key)
        placeholders = ", ".join("?" for _ in names)
        quoted = ", ".join(f'"{n}"' for n in names)
        for row in rows:
            values = [
                json.dumps(row.get(n))
                if column.type == "json"
                else _timestamp(row.get(n))
                if column.type == "timestamp"
                else row.get(n)
                for n, column in zip(names, spec.columns, strict=True)
            ]
            self.connection.execute(
                f"INSERT INTO {table} ({quoted}) VALUES ({placeholders})", values
            )
        self.writes.append((namespace, name, len(rows)))
        return self._info(spec)

    def query(
        self, sql: str, *, namespace: str = "default", snapshot_id: int | None = None
    ) -> QueryResult:
        self.queries.append(sql)
        for ns, name in referenced_datasets(sql, namespace):
            self._spec(name, ns)
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"USE {self._schema(namespace)}")
            result = cursor.execute(sql)
            columns = [str(column[0]) for column in result.description or []]
            json_columns = {
                index
                for index, column in enumerate(result.description or [])
                if str(column[1]).upper() == "JSON"
            }
            rows = [
                {
                    column: (
                        json.loads(cell)
                        if index in json_columns and cell is not None
                        else _value(cell)
                    )
                    for index, (column, cell) in enumerate(
                        zip(columns, raw, strict=True)
                    )
                }
                for raw in result.fetchall()
            ]
        finally:
            cursor.close()
        return QueryResult(columns=columns, rows=rows)

    def compact(self, name: str, *, namespace: str = "default") -> QueryResult:
        self._spec(name, namespace)
        self.maintenance.append(("compact", name))
        return QueryResult(columns=["step"], rows=[{"step": "merge"}])

    def flush(self, name: str, *, namespace: str = "default") -> QueryResult:
        self._spec(name, namespace)
        self.maintenance.append(("flush", name))
        return QueryResult(columns=[], rows=[])

    def drop(self, name: str, *, namespace: str = "default") -> None:
        spec = self._spec(name, namespace)
        self.connection.execute(f'DROP TABLE {self._schema(namespace)}."{spec.name}"')
        del self.specs[(namespace, name.lower())]


class MemoryObjectStorage:
    """The SDK object storage, blocking, in memory."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def get_object(self, prefix: str, key: str) -> bytes:
        try:
            return self.objects[(prefix.strip("/"), key)]
        except KeyError:
            raise ObjectNotFound("OBJECT_NOT_FOUND", f"{prefix}/{key}") from None

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix.strip("/"), key)] = bytes(content)

    def put_object_stream(self, prefix: str, key: str, stream: Any) -> None:
        data = stream.read()
        self.put_object(prefix, key, data)

    def delete_object(self, prefix: str, key: str) -> None:
        self.objects.pop((prefix.strip("/"), key), None)

    def list_objects(self, prefix: str = "") -> list[str]:
        """Direct children of ``prefix``; sub-folders end with ``/``."""
        root = prefix.strip("/")
        found: set[str] = set()
        for folder, key in self.objects:
            full = f"{folder}/{key}" if folder else key
            if root and not full.startswith(f"{root}/"):
                continue
            rest = full[len(root) + 1 :] if root else full
            head, sep, _ = rest.partition("/")
            base = f"{root}/{head}" if root else head
            found.add(f"{base}/" if sep else base)
        return sorted(found)


# --- the module's threads ------------------------------------------------------------

# ``SyncModule.executor``'s thread name prefix: a test tells a body that ran on
# the module's threads from one on the loop's default executor (``asyncio_<n>``)
# or on the loop itself.
SYNC_THREAD_PREFIX = "x-sync"
_SYNC_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix=SYNC_THREAD_PREFIX)
# Called in the worker thread before each body (``FakeFlowContext`` sets it to
# record where a step body ran).
ON_SYNC_THREAD: contextvars.ContextVar[Callable[[], None] | None] = (
    contextvars.ContextVar("on_sync_thread", default=None)
)


def on_sync_thread() -> bool:
    """Whether the caller runs on one of the module's ``x-sync`` threads."""
    return threading.current_thread().name.startswith(f"{SYNC_THREAD_PREFIX}_")


class ThreadedSync(SimpleNamespace):
    """A ``SyncModule`` stand-in: the attributes given (``configuration``,
    ``engine``, ``run``, ...) and ``call`` / ``threaded``, whose bodies run on
    ``x-sync`` threads in a copy of the caller's context, as the real ones."""

    async def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        def body() -> Any:
            hook = ON_SYNC_THREAD.get()
            if hook is not None:
                hook()
            return fn(*args, **kwargs)

        context = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_SYNC_POOL, context.run, body)

    def threaded(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        async def on_threads(*args: Any, **kwargs: Any) -> Any:
            return await self.call(fn, *args, **kwargs)

        on_threads.__name__ = getattr(fn, "__name__", "body")
        return on_threads
