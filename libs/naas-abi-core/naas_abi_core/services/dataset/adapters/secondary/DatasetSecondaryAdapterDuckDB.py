"""DuckDB adapter: Hive-partitioned Parquet on a local warehouse path.

MinIO/S3/R2 are the same idea once the warehouse sits on an object-storage
filesystem or mount. Iceberg/Nessie can replace the catalog file later; the
port already talks in snapshot ids.
"""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetInfo,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSnapshotNotFoundError,
    DatasetSpec,
    IDatasetPort,
    PartitionSpec,
    QueryResult,
    WriteMode,
    hive_partition_column,
)

CATALOG_NAME = "_dataset.json"
DATA_DIR = "data"

DUCKDB_TYPES = {
    "string": "VARCHAR",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
}

MONTH_SQL = {
    "year": "strftime({col}::TIMESTAMP, '%Y')",
    "month": "strftime({col}::TIMESTAMP, '%Y-%m')",
    "day": "strftime({col}::TIMESTAMP, '%Y-%m-%d')",
}


class DatasetSecondaryAdapterDuckDB(IDatasetPort):
    def __init__(self, base_path: str):
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(self, spec: DatasetSpec) -> DatasetInfo:
        self._validate_partitions(spec)
        root = self._dataset_root(spec.namespace, spec.name)
        with self._lock:
            if (root / CATALOG_NAME).exists():
                raise DatasetAlreadyExistsError(spec.name, spec.namespace)
            root.mkdir(parents=True, exist_ok=True)
            (root / DATA_DIR).mkdir(exist_ok=True)
            info = DatasetInfo(
                name=spec.name,
                namespace=spec.namespace,
                columns=spec.columns,
                partitions=spec.partitions,
                snapshot_id=str(uuid.uuid4()),
                location=str(root),
            )
            self._write_catalog(root, info)
            return info

    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        return self._load_catalog(namespace, name)

    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        found: list[DatasetInfo] = []
        namespaces = [namespace] if namespace else self._namespaces()
        for ns in namespaces:
            ns_dir = self._base / ns
            if not ns_dir.is_dir():
                continue
            for child in sorted(ns_dir.iterdir()):
                if (child / CATALOG_NAME).is_file():
                    found.append(self._load_catalog(ns, child.name))
        return found

    def write(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: str | None = None,
    ) -> DatasetInfo:
        with self._lock:
            info = self._load_catalog(namespace, name)
            self._assert_snapshot(info, snapshot_id)
            root = Path(info.location)
            data_dir = root / DATA_DIR
            if mode == "replace" and data_dir.exists():
                shutil.rmtree(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            if rows:
                self._copy_rows(info, rows, data_dir)
            next_info = info.model_copy(update={"snapshot_id": str(uuid.uuid4())})
            self._write_catalog(root, next_info)
            return next_info

    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: str | None = None,
    ) -> QueryResult:
        import duckdb

        datasets = self.list(namespace=namespace)
        if snapshot_id is not None:
            for info in datasets:
                self._assert_snapshot(info, snapshot_id)
        con = duckdb.connect()
        try:
            for info in datasets:
                self._register_table(con, info)
            result = con.execute(sql)
            columns = [str(col[0]) for col in result.description or []]
            rows = []
            for raw in result.fetchall():
                rows.append(dict(zip(columns, (self._cell(value) for value in raw))))
            return QueryResult(columns=columns, rows=rows)
        finally:
            con.close()

    def drop(self, name: str, *, namespace: str = "default") -> None:
        with self._lock:
            info = self._load_catalog(namespace, name)
            shutil.rmtree(info.location, ignore_errors=True)

    def _dataset_root(self, namespace: str, name: str) -> Path:
        return self._base / namespace / name

    def _namespaces(self) -> list[str]:
        if not self._base.is_dir():
            return []
        return sorted(
            child.name for child in self._base.iterdir() if child.is_dir()
        )

    def _load_catalog(self, namespace: str, name: str) -> DatasetInfo:
        path = self._dataset_root(namespace, name) / CATALOG_NAME
        if not path.is_file():
            raise DatasetNotFoundError(name, namespace)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return DatasetInfo(
            name=payload["name"],
            namespace=payload["namespace"],
            columns=tuple(ColumnSpec(**col) for col in payload["columns"]),
            partitions=tuple(
                PartitionSpec(**part) for part in payload.get("partitions") or []
            ),
            snapshot_id=payload["snapshot_id"],
            location=payload["location"],
        )

    def _write_catalog(self, root: Path, info: DatasetInfo) -> None:
        payload = {
            "name": info.name,
            "namespace": info.namespace,
            "columns": [col.model_dump() for col in info.columns],
            "partitions": [part.model_dump() for part in info.partitions],
            "snapshot_id": info.snapshot_id,
            "location": str(root),
        }
        (root / CATALOG_NAME).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def _validate_partitions(self, spec: DatasetSpec) -> None:
        names = {col.name for col in spec.columns}
        for part in spec.partitions:
            if part.column not in names:
                raise DatasetSchemaError(
                    f"Partition column {part.column!r} is not in the dataset schema"
                )

    def _assert_snapshot(self, info: DatasetInfo, snapshot_id: str | None) -> None:
        if snapshot_id is None or snapshot_id == info.snapshot_id:
            return
        raise DatasetSnapshotNotFoundError(snapshot_id)

    def _copy_rows(
        self, info: DatasetInfo, rows: list[dict[str, Any]], data_dir: Path
    ) -> None:
        import duckdb

        missing = [
            col.name
            for col in info.columns
            if any(col.name not in row for row in rows)
        ]
        if missing:
            raise DatasetSchemaError(
                f"Rows missing columns: {', '.join(sorted(set(missing)))}"
            )
        con = duckdb.connect()
        try:
            con.execute(self._create_incoming_sql(info))
            for row in rows:
                con.execute(
                    f'INSERT INTO "incoming" VALUES ({", ".join("?" for _ in info.columns)})',
                    [row.get(col.name) for col in info.columns],
                )
            select_sql, partition_by = self._select_and_partitions(info)
            target = str(data_dir)
            if partition_by:
                con.execute(
                    f"COPY ({select_sql}) TO ? (FORMAT PARQUET, PARTITION_BY {partition_by})",
                    [target],
                )
            else:
                part = data_dir / f"part-{uuid.uuid4()}.parquet"
                con.execute(f"COPY ({select_sql}) TO ?", [str(part)])
        finally:
            con.close()

    def _create_incoming_sql(self, info: DatasetInfo) -> str:
        fields = ", ".join(
            f"{self._ident(col.name)} {DUCKDB_TYPES[col.type]}"
            for col in info.columns
        )
        return f'CREATE TABLE "incoming" ({fields})'

    def _select_and_partitions(self, info: DatasetInfo) -> tuple[str, str]:
        extras: list[str] = []
        hive_cols: list[str] = []
        for part in info.partitions:
            hive = hive_partition_column(part)
            hive_cols.append(hive)
            if part.transform == "identity":
                continue
            template = MONTH_SQL[part.transform]
            extras.append(
                f"{template.format(col=self._ident(part.column))} AS {self._ident(hive)}"
            )
        select_list = ", ".join(
            [self._ident(col.name) for col in info.columns] + extras
        )
        select_sql = f'SELECT {select_list} FROM "incoming"'
        if not hive_cols:
            return select_sql, ""
        return select_sql, "(" + ", ".join(self._ident(col) for col in hive_cols) + ")"

    def _register_table(self, con: Any, info: DatasetInfo) -> None:
        glob = str(Path(info.location) / DATA_DIR / "**" / "*.parquet")
        has_files = any(Path(info.location).joinpath(DATA_DIR).rglob("*.parquet"))
        if has_files:
            con.execute(
                "CREATE VIEW "
                f"{self._ident(info.name)} AS SELECT * FROM read_parquet("
                f"{self._sql_string(glob)}, hive_partitioning=true)"
            )
            return
        nulls = ", ".join(
            f"NULL::{DUCKDB_TYPES[col.type]} AS {self._ident(col.name)}"
            for col in info.columns
        )
        for part in info.partitions:
            hive = hive_partition_column(part)
            if hive not in {col.name for col in info.columns}:
                nulls += f", NULL::VARCHAR AS {self._ident(hive)}"
        con.execute(
            f"CREATE VIEW {self._ident(info.name)} AS SELECT * FROM (SELECT {nulls}) WHERE 1=0"
        )

    @staticmethod
    def _ident(name: str) -> str:
        return '"' + name.replace('"', '""') + '"'

    @staticmethod
    def _sql_string(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _cell(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value
