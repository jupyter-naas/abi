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
    uri: str = Field(..., min_length=1)


class GraphDelete(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    uri: str = Field(..., min_length=1)


class IndividualCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, max_length=500)
    class_uri: str | None = Field(default=None, min_length=1)


class IndividualDelete(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    individual_uri: str = Field(..., min_length=1)


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


class GraphAnalysis(BaseModel):
    total_triples: int
    total_subjects: int
    named_individuals_subjects: int
    named_individuals_triples: int
    classes_subjects: int
    classes_triples: int
    object_properties_subjects: int
    object_properties_triples: int
    datatype_properties_subjects: int
    datatype_properties_triples: int
    restrictions_subjects: int
    restrictions_triples: int
    unknown_subjects: int
    unknown_triples: int
