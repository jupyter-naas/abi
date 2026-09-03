"""Port for named, partitioned, versioned, SQL-queryable datasets."""

from __future__ import annotations

# ``list`` is a port method name, so it shadows the builtin for annotations
# evaluated in the class bodies below; use ``builtins.list`` there.
import builtins
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ColumnType = Literal[
    "string",
    "integer",
    "bigint",
    "double",
    "boolean",
    "date",
    "timestamp",
    "json",
]
PartitionTransform = Literal["identity", "year", "month", "day"]
WriteMode = Literal["append", "replace", "upsert"]

IDENTIFIER_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*$"


class DatasetNotFoundError(Exception):
    def __init__(self, name: str, namespace: str) -> None:
        self.name = name
        self.namespace = namespace
        super().__init__(f"Dataset {namespace}.{name} not found")


class DatasetAlreadyExistsError(Exception):
    def __init__(self, name: str, namespace: str) -> None:
        self.name = name
        self.namespace = namespace
        super().__init__(f"Dataset {namespace}.{name} already exists")


class DatasetSchemaError(Exception):
    pass


class DatasetSnapshotNotFoundError(Exception):
    def __init__(self, snapshot_id: int) -> None:
        self.snapshot_id = snapshot_id
        super().__init__(f"Dataset snapshot {snapshot_id!r} not found")


class ColumnSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    type: ColumnType

    @field_validator("name")
    @classmethod
    def _valid_identifier(cls, value: str) -> str:
        return _require_identifier(value, "column name")


class PartitionSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    column: str
    transform: PartitionTransform = "identity"

    @field_validator("column")
    @classmethod
    def _valid_identifier(cls, value: str) -> str:
        return _require_identifier(value, "partition column")


class DatasetSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    namespace: str = "default"
    columns: tuple[ColumnSpec, ...]
    partitions: tuple[PartitionSpec, ...] = ()
    primary_key: tuple[str, ...] = ()

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        return _require_identifier(value, "dataset name")

    @field_validator("namespace")
    @classmethod
    def _valid_namespace(cls, value: str) -> str:
        return _require_identifier(value, "namespace")

    @field_validator("primary_key")
    @classmethod
    def _valid_primary_key(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_identifier(item, "primary key column") for item in value)

    @model_validator(mode="after")
    def _validate_schema_references(self) -> DatasetSpec:
        column_names = [column.name for column in self.columns]
        duplicates = sorted(
            name for name in set(column_names) if column_names.count(name) > 1
        )
        if duplicates:
            raise ValueError(f"Duplicate dataset columns: {', '.join(duplicates)}")

        known = set(column_names)
        missing_partitions = sorted(
            {partition.column for partition in self.partitions} - known
        )
        if missing_partitions:
            raise ValueError(
                "Partition columns are not in the dataset schema: "
                + ", ".join(missing_partitions)
            )

        duplicate_keys = sorted(
            name for name in set(self.primary_key) if self.primary_key.count(name) > 1
        )
        if duplicate_keys:
            raise ValueError(
                f"Duplicate primary key columns: {', '.join(duplicate_keys)}"
            )
        missing_keys = sorted(set(self.primary_key) - known)
        if missing_keys:
            raise ValueError(
                "Primary key columns are not in the dataset schema: "
                + ", ".join(missing_keys)
            )
        return self


class DatasetInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    namespace: str
    columns: tuple[ColumnSpec, ...]
    partitions: tuple[PartitionSpec, ...]
    primary_key: tuple[str, ...]
    snapshot_id: int
    location: str


class DatasetSnapshotInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: int
    created_at: datetime


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)


class IDatasetPort(ABC):
    @abstractmethod
    def create(self, spec: DatasetSpec) -> DatasetInfo:
        """Register a table. Raises DatasetAlreadyExistsError if it exists."""

    @abstractmethod
    def describe(self, name: str, *, namespace: str = "default") -> DatasetInfo:
        """Return catalog metadata. Raises DatasetNotFoundError."""

    @abstractmethod
    def list(self, *, namespace: str | None = None) -> list[DatasetInfo]:
        """List datasets, optionally in one namespace."""

    @abstractmethod
    def write(
        self,
        name: str,
        rows: builtins.list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: int | None = None,
    ) -> DatasetInfo:
        """Append, replace, or upsert rows against the current catalog snapshot."""

    @abstractmethod
    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: int | None = None,
    ) -> QueryResult:
        """Run SQL against datasets in ``namespace``. Tables are registered by dataset name."""

    @abstractmethod
    def list_snapshots(self) -> builtins.list[DatasetSnapshotInfo]:
        """List the coherent, catalog-level snapshots available for time travel."""

    @abstractmethod
    def drop(self, name: str, *, namespace: str = "default") -> None:
        """Drop the current table. Historical snapshots retain data until expiry."""


def _require_identifier(value: str, label: str) -> str:
    import re

    text = str(value).strip()
    if not re.fullmatch(IDENTIFIER_PATTERN, text):
        raise ValueError(
            f"{label} {value!r} must match {IDENTIFIER_PATTERN} "
            "(letter, then letters, digits, or underscore)"
        )
    return text
