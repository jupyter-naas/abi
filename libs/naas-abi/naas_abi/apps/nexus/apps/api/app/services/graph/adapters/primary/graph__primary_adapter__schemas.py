from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GraphInfo(BaseModel):
    id: str
    uri: str
    label: str
    role_label: str = "unknown"


class GraphPack(BaseModel):
    role_label: str
    graphs: list[GraphInfo]


class GraphCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1, max_length=200)


class GraphClear(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str = Field(..., min_length=1, max_length=200)


class GraphDelete(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str = Field(..., min_length=1, max_length=200)


class GraphOverview(BaseModel):
    kpis: dict[str, Any]
    instances_by_class: list[dict[str, Any]]


class GraphNode(BaseModel):
    id: str
    workspace_id: str
    type: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphEdge(BaseModel):
    id: str
    workspace_id: str
    source_id: str
    target_id: str
    source_label: str
    target_label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
