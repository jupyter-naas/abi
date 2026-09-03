from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetColumn(BaseModel):
    name: str
    type: str


class DatasetPartition(BaseModel):
    column: str
    transform: str


class DatasetInfo(BaseModel):
    name: str
    namespace: str
    columns: list[DatasetColumn]
    partitions: list[DatasetPartition]
    primary_key: list[str]
    snapshot_id: int
    location: str


class DatasetListResponse(BaseModel):
    datasets: list[DatasetInfo]
    total: int


class DatasetQueryRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    sql: str = Field(..., min_length=1, max_length=20_000)
    snapshot_id: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=1, le=5_000)


class DatasetQueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool = False
    limit: int = 0
