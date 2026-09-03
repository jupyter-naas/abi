"""DuckLake adapter for versioned, SQL-queryable datasets."""

from __future__ import annotations

import builtins
import json
import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from naas_abi_core.services.dataset.DatasetPort import (
    DatasetAlreadyExistsError,
    DatasetInfo,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSnapshotConflictError,
    DatasetSnapshotInfo,
    DatasetSnapshotNotFoundError,
    DatasetSpec,
    IDatasetPort,
    QueryResult,
    WriteMode,
)

CATALOG_ALIAS = "abi_datasets"
S3_SECRET_NAME = "abi_datasets_store"
SPEC_COMMENT_PREFIX = "abi.dataset-spec:"
S3_DATA_PATH_SCHEMES = (
    "s3://",
    "s3a://",
)

DUCKDB_TYPES = {
    "string": "VARCHAR",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "json": "JSON",
}

_T = TypeVar("_T")
logger = logging.getLogger(__name__)


def _is_s3_data_path(path: str) -> bool:
    return path.lower().startswith(S3_DATA_PATH_SCHEMES)


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


@dataclass(frozen=True)
class _S3Settings:
    """Credentials and endpoint for the object store behind ``data_path``.

    MinIO and other S3-compatible stores need the endpoint, path-style URLs and
    plain HTTP; none of those are DuckDB defaults, so each is explicit here.
    """

    endpoint: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    region: str = ""
    url_style: str = ""
    use_ssl: bool | None = None

    def __post_init__(self) -> None:
        endpoint = self.endpoint.strip().lower()
        has_http_scheme = endpoint.startswith(("http://", "https://"))
        if "://" in endpoint and not has_http_scheme:
            raise ValueError("s3_endpoint scheme must be http:// or https://")
        if endpoint and not has_http_scheme and self.use_ssl is None:
            raise ValueError(
                "s3_endpoint must include an http:// or https:// scheme or set "
                "s3_use_ssl explicitly"
            )

    @property
    def configured(self) -> bool:
        return bool(self.endpoint or self.access_key_id or self.secret_access_key)

    def sql(self) -> str:
        parts = ["TYPE s3"]
        if self.access_key_id:
            parts.append(f"KEY_ID {_sql_literal(self.access_key_id)}")
        if self.secret_access_key:
            parts.append(f"SECRET {_sql_literal(self.secret_access_key)}")
        if self.endpoint:
            endpoint = self.endpoint.strip()
            use_ssl = self.use_ssl
            for scheme, ssl in (("https://", True), ("http://", False)):
                if endpoint.lower().startswith(scheme):
                    endpoint = endpoint[len(scheme) :]
                    use_ssl = ssl if use_ssl is None else use_ssl
                    break
            parts.append(f"ENDPOINT {_sql_literal(endpoint.rstrip('/'))}")
            # A custom endpoint is almost never virtual-hosted; MinIO is not.
            parts.append(f"URL_STYLE {_sql_literal(self.url_style or 'path')}")
            parts.append(f"USE_SSL {'true' if (use_ssl is not False) else 'false'}")
        elif self.url_style:
            parts.append(f"URL_STYLE {_sql_literal(self.url_style)}")
        parts.append(f"REGION {_sql_literal(self.region or 'us-east-1')}")
        return ", ".join(parts)


class DatasetSecondaryAdapterDuckLake(IDatasetPort):
    """Store datasets in one DuckLake catalog and data warehouse.

    A fresh DuckDB connection is used for every operation. Retriable catalog
    conflicts replay the complete transaction against fresh state using bounded
    exponential backoff with jitter.
    """

    def __init__(
        self,
        catalog: str,
        data_path: str,
        *,
        max_retries: int = 10,
        retry_base_delay_seconds: float = 0.05,
        retry_max_delay_seconds: float = 1.0,
        s3_endpoint: str = "",
        s3_access_key_id: str = "",
        s3_secret_access_key: str = "",
        s3_region: str = "",
        s3_url_style: str = "",
        s3_use_ssl: bool | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to zero")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be non-negative")
        if retry_max_delay_seconds < retry_base_delay_seconds:
            raise ValueError(
                "retry_max_delay_seconds must be greater than or equal to "
                "retry_base_delay_seconds"
            )

        self._catalog = catalog
        self._data_path = data_path.rstrip("/") + "/"
        if "://" in self._data_path and not _is_s3_data_path(self._data_path):
            scheme = self._data_path.split("://", 1)[0]
            raise ValueError(
                f"Unsupported dataset data_path scheme {scheme!r}; "
                "supported object-store schemes are s3:// and s3a://"
            )
        self._s3 = _S3Settings(
            endpoint=s3_endpoint,
            access_key_id=s3_access_key_id,
            secret_access_key=s3_secret_access_key,
            region=s3_region,
            url_style=s3_url_style,
            use_ssl=s3_use_ssl,
        )
        if self._s3.configured and not _is_s3_data_path(self._data_path):
            raise ValueError(
                "S3 settings were given for a data_path that is not an object store URI: "
                f"{self._data_path!r}"
            )
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._sqlite_write_lock = (
            threading.RLock() if self._catalog.startswith("sqlite:") else None
        )
        self._prepare_local_paths()

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        def operation(con: Any) -> DatasetSpec:
            if self._table_exists(con, spec.namespace, spec.name):
                raise DatasetAlreadyExistsError(spec.name, spec.namespace)

            con.execute(
                f"CREATE SCHEMA IF NOT EXISTS {self._qualified_schema(spec.namespace)}"
            )
            fields = ", ".join(
                f"{self._ident(column.name)} {DUCKDB_TYPES[column.type]}"
                for column in spec.columns
            )
            con.execute(
                f"CREATE TABLE {self._qualified_table(spec.namespace, spec.name)} "
                f"({fields})"
            )
            if spec.partitions:
                expressions = ", ".join(
                    self._partition_expression(partition.column, partition.transform)
                    for partition in spec.partitions
                )
                con.execute(
                    f"ALTER TABLE {self._qualified_table(spec.namespace, spec.name)} "
                    f"SET PARTITIONED BY ({expressions})"
                )
            comment = SPEC_COMMENT_PREFIX + json.dumps(
                spec.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            con.execute(
                f"COMMENT ON TABLE {self._qualified_table(spec.namespace, spec.name)} "
                f"IS {self._sql_string(comment)}"
            )
            return spec

        try:
            created, snapshot_id = self._write_transaction(operation)
        except DatasetAlreadyExistsError:
            raise
        except Exception as exc:
            if "already exists" in str(exc).lower():
                raise DatasetAlreadyExistsError(spec.name, spec.namespace) from exc
            raise
        return self._to_info(created, snapshot_id)

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        con = self._connect()
        try:
            snapshot_id = self._current_snapshot(con)
            spec = self._load_spec(con, namespace, name)
            return self._to_info(spec, snapshot_id)
        finally:
            con.close()

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        con = self._connect()
        try:
            snapshot_id = self._current_snapshot(con)
            sql = (
                "SELECT schema_name, table_name, comment FROM duckdb_tables() "
                "WHERE database_name = ? AND comment LIKE ?"
            )
            parameters: list[Any] = [CATALOG_ALIAS, SPEC_COMMENT_PREFIX + "%"]
            if namespace is not None:
                sql += " AND schema_name = ?"
                parameters.append(namespace)
            sql += " ORDER BY schema_name, table_name"
            return [
                self._to_info(self._spec_from_comment(comment), snapshot_id)
                for _, _, comment in con.execute(sql, parameters).fetchall()
            ]
        finally:
            con.close()

    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        def operation(con: Any) -> DatasetSpec:
            current_snapshot = self._current_snapshot(con)
            if snapshot_id is not None and snapshot_id != current_snapshot:
                raise DatasetSnapshotConflictError(snapshot_id, current_snapshot)

            spec = self._load_spec(con, namespace, name)
            normalized_rows = self._normalize_rows(spec, rows)
            if mode == "upsert":
                self._validate_upsert_keys(spec, normalized_rows)
            if not normalized_rows:
                if mode == "replace":
                    target = self._qualified_table(namespace, name)
                    con.execute(f"DELETE FROM {target}")  # nosec B608
                elif mode not in ("append", "upsert"):
                    raise ValueError(f"Unknown dataset write mode: {mode}")
                return spec

            self._create_incoming_table(con, spec)
            self._insert_incoming_rows(con, spec, normalized_rows)
            target = self._qualified_table(namespace, name)
            columns = ", ".join(self._ident(column.name) for column in spec.columns)

            if mode == "replace":
                con.execute(f"DELETE FROM {target}")  # nosec B608
                con.execute(
                    f"INSERT INTO {target} ({columns}) "  # nosec B608
                    f"SELECT {columns} FROM incoming"
                )
            elif mode == "append":
                con.execute(
                    f"INSERT INTO {target} ({columns}) "  # nosec B608
                    f"SELECT {columns} FROM incoming"
                )
            elif mode == "upsert":
                self._merge_rows(con, spec)
            else:  # pragma: no cover - WriteMode validation protects typed callers
                raise ValueError(f"Unknown dataset write mode: {mode}")
            return spec

        spec, committed_snapshot = self._write_transaction(operation)
        return self._to_info(spec, committed_snapshot)

    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: int | None = None,
    ) -> QueryResult:
        if snapshot_id is not None and not self._snapshot_exists(snapshot_id):
            raise DatasetSnapshotNotFoundError(snapshot_id)

        try:
            con = self._connect(snapshot_id=snapshot_id)
        except Exception as exc:
            if snapshot_id is not None:
                raise DatasetSnapshotNotFoundError(snapshot_id) from exc
            raise
        try:
            con.execute(f"USE {self._qualified_schema(namespace)}")
            result = con.execute(sql)
            description = result.description or []
            columns = [str(column[0]) for column in description]
            json_columns = {
                index
                for index, column in enumerate(description)
                if str(column[1]).upper() == "JSON"
            }
            rows = [
                {
                    column: self._cell(value, index in json_columns)
                    for index, (column, value) in enumerate(zip(columns, raw))
                }
                for raw in result.fetchall()
            ]
            return QueryResult(columns=columns, rows=rows)
        finally:
            con.close()

    def list_snapshots(self) -> builtins.list[DatasetSnapshotInfo]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT snapshot_id, snapshot_time "
                "FROM abi_datasets.snapshots() "
                "ORDER BY snapshot_id"
            ).fetchall()
            return [
                DatasetSnapshotInfo(snapshot_id=int(snapshot_id), created_at=created_at)
                for snapshot_id, created_at in rows
            ]
        finally:
            con.close()

    def drop(self, name: str, *, namespace: str = "default") -> None:
        def operation(con: Any) -> None:
            if not self._table_exists(con, namespace, name):
                raise DatasetNotFoundError(name, namespace)
            con.execute(f"DROP TABLE {self._qualified_table(namespace, name)}")

        self._write_transaction(operation)

    def _connect(self, *, snapshot_id: int | None = None) -> Any:
        import duckdb

        con = duckdb.connect()
        try:
            try:
                con.execute("LOAD ducklake")
            except duckdb.Error:
                con.execute("INSTALL ducklake")
                con.execute("LOAD ducklake")
            con.execute("SET ducklake_max_retry_count = 0")
            self._configure_object_store(con)
            options = [
                "AUTOMATIC_MIGRATION",
                f"DATA_PATH {self._sql_string(self._data_path)}",
            ]
            if snapshot_id is not None:
                options.append(f"SNAPSHOT_VERSION {int(snapshot_id)}")
            attach_target = "ducklake:" + self._catalog
            con.execute(
                f"ATTACH {self._sql_string(attach_target)} "
                f"AS {self._ident(CATALOG_ALIAS)} ({', '.join(options)})"
            )
            return con
        except Exception:
            con.close()
            raise

    def _write_transaction(self, operation: Callable[[Any], _T]) -> tuple[_T, int]:
        if self._sqlite_write_lock is not None:
            with self._sqlite_write_lock:
                return self._retry_write_transaction(operation)
        return self._retry_write_transaction(operation)

    def _retry_write_transaction(
        self, operation: Callable[[Any], _T]
    ) -> tuple[_T, int]:
        import duckdb

        for attempt in range(self._max_retries + 1):
            con = None
            try:
                con = self._connect()
                con.execute("BEGIN")
                value = operation(con)
                con.execute("COMMIT")
                committed_snapshot = self._last_committed_snapshot(con)
                if committed_snapshot is None:
                    # Read-only/no-op transactions do not create a DuckLake snapshot.
                    committed_snapshot = self._current_snapshot(con)
                return value, committed_snapshot
            except Exception as exc:
                if con is not None:
                    try:
                        con.execute("ROLLBACK")
                    except duckdb.Error:
                        logger.debug(
                            "Rollback after a failed DuckLake transaction also failed",
                            exc_info=True,
                        )
                if attempt >= self._max_retries or not self._is_retriable(exc):
                    raise
                delay = min(
                    self._retry_base_delay_seconds * (2**attempt),
                    self._retry_max_delay_seconds,
                )
                time.sleep(delay * random.uniform(0.75, 1.25))  # nosec B311
            finally:
                if con is not None:
                    con.close()
        raise AssertionError("unreachable")

    def _load_spec(self, con: Any, namespace: str, name: str) -> DatasetSpec:
        row = con.execute(
            "SELECT comment FROM duckdb_tables() "
            "WHERE database_name = ? AND schema_name = ? AND table_name = ?",
            [CATALOG_ALIAS, namespace, name],
        ).fetchone()
        if row is None or not str(row[0] or "").startswith(SPEC_COMMENT_PREFIX):
            raise DatasetNotFoundError(name, namespace)
        return self._spec_from_comment(row[0])

    @staticmethod
    def _spec_from_comment(comment: str) -> DatasetSpec:
        return DatasetSpec.model_validate_json(comment[len(SPEC_COMMENT_PREFIX) :])

    def _table_exists(self, con: Any, namespace: str, name: str) -> bool:
        return (
            con.execute(
                "SELECT 1 FROM duckdb_tables() "
                "WHERE database_name = ? AND schema_name = ? AND table_name = ?",
                [CATALOG_ALIAS, namespace, name],
            ).fetchone()
            is not None
        )

    def _current_snapshot(self, con: Any) -> int:
        row = con.execute(
            f"FROM {self._ident(CATALOG_ALIAS)}.current_snapshot()"
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckLake catalog did not report a current snapshot")
        return int(row[0])

    def _last_committed_snapshot(self, con: Any) -> int | None:
        row = con.execute(
            f"FROM {self._ident(CATALOG_ALIAS)}.last_committed_snapshot()"
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    def _snapshot_exists(self, snapshot_id: int) -> bool:
        con = self._connect()
        try:
            return (
                con.execute(
                    "SELECT 1 FROM abi_datasets.snapshots() WHERE snapshot_id = ?",
                    [snapshot_id],
                ).fetchone()
                is not None
            )
        finally:
            con.close()

    def _to_info(self, spec: DatasetSpec, snapshot_id: int) -> DatasetInfo:
        return DatasetInfo(
            name=spec.name,
            namespace=spec.namespace,
            columns=spec.columns,
            partitions=spec.partitions,
            primary_key=spec.primary_key,
            snapshot_id=snapshot_id,
            location=f"{self._data_path}{spec.namespace}/{spec.name}",
        )

    def _normalize_rows(
        self, spec: DatasetSpec, rows: builtins.list[dict[str, Any]]
    ) -> builtins.list[dict[str, Any]]:
        expected = {column.name for column in spec.columns}
        normalized: builtins.list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            missing = expected - set(row)
            extra = set(row) - expected
            if missing:
                raise DatasetSchemaError(
                    f"Row {index} is missing columns: {', '.join(sorted(missing))}"
                )
            if extra:
                raise DatasetSchemaError(
                    f"Row {index} has unknown columns: {', '.join(sorted(extra))}"
                )
            values = dict(row)
            for column in spec.columns:
                if column.type == "json" and values[column.name] is not None:
                    values[column.name] = self._normalize_json(
                        values[column.name], column.name, index
                    )
            normalized.append(values)
        return normalized

    @staticmethod
    def _normalize_json(value: Any, column: str, row_index: int) -> str:
        try:
            decoded = json.loads(value) if isinstance(value, str) else value
            return json.dumps(
                decoded,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DatasetSchemaError(
                f"Row {row_index} column {column!r} is not valid JSON"
            ) from exc

    @staticmethod
    def _validate_upsert_keys(
        spec: DatasetSpec, rows: builtins.list[dict[str, Any]]
    ) -> None:
        if not spec.primary_key:
            raise DatasetSchemaError(
                f"Dataset {spec.namespace}.{spec.name} has no primary key for upsert"
            )
        seen: set[tuple[Any, ...]] = set()
        for index, row in enumerate(rows):
            key = tuple(row[column] for column in spec.primary_key)
            if any(value is None for value in key):
                raise DatasetSchemaError(
                    f"Row {index} has a null primary key value for "
                    f"{', '.join(spec.primary_key)}"
                )
            if key in seen:
                raise DatasetSchemaError(
                    f"Incoming upsert contains duplicate primary key {key!r}"
                )
            seen.add(key)

    def _create_incoming_table(self, con: Any, spec: DatasetSpec) -> None:
        fields = ", ".join(
            f"{self._ident(column.name)} {DUCKDB_TYPES[column.type]}"
            for column in spec.columns
        )
        con.execute(f"CREATE TEMP TABLE incoming ({fields})")

    def _insert_incoming_rows(
        self,
        con: Any,
        spec: DatasetSpec,
        rows: builtins.list[dict[str, Any]],
    ) -> None:
        placeholders = ", ".join("?" for _ in spec.columns)
        sql = f"INSERT INTO incoming VALUES ({placeholders})"  # nosec B608
        con.executemany(
            sql,
            [[row[column.name] for column in spec.columns] for row in rows],
        )

    def _merge_rows(self, con: Any, spec: DatasetSpec) -> None:
        target = self._qualified_table(spec.namespace, spec.name)
        conditions = " AND ".join(
            f"target.{self._ident(column)} = source.{self._ident(column)}"
            for column in spec.primary_key
        )
        assignments = ", ".join(
            f"{self._ident(column.name)} = source.{self._ident(column.name)}"
            for column in spec.columns
        )
        columns = ", ".join(self._ident(column.name) for column in spec.columns)
        values = ", ".join(
            f"source.{self._ident(column.name)}" for column in spec.columns
        )
        con.execute(
            f"MERGE INTO {target} AS target "  # nosec B608
            f"USING incoming AS source ON ({conditions}) "
            f"WHEN MATCHED THEN UPDATE SET {assignments} "
            f"WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values})"
        )

    @staticmethod
    def _partition_expression(column: str, transform: str) -> str:
        identifier = DatasetSecondaryAdapterDuckLake._ident(column)
        if transform == "identity":
            return identifier
        return f"{transform}({identifier})"

    def _qualified_schema(self, namespace: str) -> str:
        return f"{self._ident(CATALOG_ALIAS)}.{self._ident(namespace)}"

    def _qualified_table(self, namespace: str, name: str) -> str:
        return f"{self._qualified_schema(namespace)}.{self._ident(name)}"

    def _configure_object_store(self, con: Any) -> None:
        """Teach the connection to reach the object store holding ``data_path``.

        DuckLake writes Parquet straight to ``data_path``. Without this the write
        either fails with HTTP 403 or, for a batch small enough to be inlined in
        the catalog, appears to succeed while never reaching the store at all.
        """
        import duckdb

        if not self._s3.configured:
            return
        try:
            con.execute("LOAD httpfs")
        except duckdb.Error:
            con.execute("INSTALL httpfs")
            con.execute("LOAD httpfs")
        con.execute(
            f"CREATE OR REPLACE SECRET {self._ident(S3_SECRET_NAME)} ({self._s3.sql()})"
        )

    def _prepare_local_paths(self) -> None:
        if self._catalog.startswith("sqlite:"):
            catalog_path = Path(self._catalog.removeprefix("sqlite:"))
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
        if not _is_s3_data_path(self._data_path):
            Path(self._data_path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_retriable(exc: Exception) -> bool:
        import duckdb

        if isinstance(exc, duckdb.TransactionException):
            return True
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "database is locked",
                "transaction conflict",
                "serialization conflict",
                "failed to commit",
            )
        )

    @staticmethod
    def _ident(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    @staticmethod
    def _sql_string(value: Any) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def _cell(value: Any, is_json: bool) -> Any:
        if value is None:
            return None
        if is_json and isinstance(value, str):
            return json.loads(value)
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
