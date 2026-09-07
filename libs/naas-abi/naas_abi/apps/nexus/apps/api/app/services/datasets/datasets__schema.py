from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from naas_abi_core.services.dataset.DatasetPort import IDENTIFIER_PATTERN


class DatasetsDomainError(Exception):
    pass


class DatasetQueryError(DatasetsDomainError):
    pass


class DatasetQueryTimeoutError(DatasetsDomainError):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Query timed out after {timeout_seconds:.0f}s")


class DatasetServiceUnavailableError(DatasetsDomainError):
    def __init__(self) -> None:
        super().__init__("Dataset service is not initialized")


class InvalidDatasetIdentifierError(DatasetsDomainError):
    def __init__(self, label: str, value: str) -> None:
        self.label = label
        self.value = value
        super().__init__(
            f"{label} {value!r} must match {IDENTIFIER_PATTERN} "
            "(letter, then letters, digits, or underscore)"
        )


@dataclass(frozen=True)
class DatasetColumnData:
    name: str
    type: str


@dataclass(frozen=True)
class DatasetPartitionData:
    column: str
    transform: str


@dataclass(frozen=True)
class DatasetInfoData:
    name: str
    namespace: str
    columns: tuple[DatasetColumnData, ...]
    partitions: tuple[DatasetPartitionData, ...]
    primary_key: tuple[str, ...]
    snapshot_id: int
    location: str


@dataclass
class DatasetQueryResultData:
    columns: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    limit: int = 0
