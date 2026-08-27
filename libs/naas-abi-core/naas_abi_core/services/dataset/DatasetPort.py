"""Port for named, partitioned, SQL-queryable datasets.

The graph catalogs what a dataset *is*. This port stores and queries the table.
Snapshot / branch arguments default to current so a later Iceberg/Nessie catalog
can fill them in without changing callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ColumnType = Literal[
    "string",
    "integer",
    "bigint",
    "double",
    "boolean",
    "date",
    "timestamp",
]
PartitionTransform = Literal["identity", "year", "month", "day"]
WriteMode = Literal["append", "replace"]

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
    def __init__(self, snapshot_id: str) -> None:
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

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        return _require_identifier(value, "dataset name")

    @field_validator("namespace")
    @classmethod
    def _valid_namespace(cls, value: str) -> str:
        return _require_identifier(value, "namespace")


class DatasetInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    namespace: str
    columns: tuple[ColumnSpec, ...]
    partitions: tuple[PartitionSpec, ...]
    snapshot_id: str
    location: str


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
        rows: list[dict[str, Any]],
        *,
        namespace: str = "default",
        mode: WriteMode = "append",
        snapshot_id: str | None = None,
    ) -> DatasetInfo:
        """Append or replace rows. ``snapshot_id`` defaults to current (only current is stored)."""

    @abstractmethod
    def query(
        self,
        sql: str,
        *,
        namespace: str = "default",
        snapshot_id: str | None = None,
    ) -> QueryResult:
        """Run SQL against datasets in ``namespace``. Tables are registered by dataset name."""

    @abstractmethod
    def drop(self, name: str, *, namespace: str = "default") -> None:
        """Delete the table and its files. Raises DatasetNotFoundError."""


def _require_identifier(value: str, label: str) -> str:
    import re

    text = str(value).strip()
    if not re.fullmatch(IDENTIFIER_PATTERN, text):
        raise ValueError(
            f"{label} {value!r} must match {IDENTIFIER_PATTERN} "
            "(letter, then letters, digits, or underscore)"
        )
    return text


def hive_partition_column(partition: PartitionSpec) -> str:
    """Physical Hive-folder column for a partition spec."""
    if partition.transform == "identity":
        return partition.column
    return f"{partition.column}_{partition.transform}"
