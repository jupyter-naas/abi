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
    role_label: str = Field(default="unknown", min_length=1, max_length=100)


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
    properties: dict[str, str] = Field(default_factory=dict)


class DiscoveryClassMeta(BaseModel):
    class_uri: str
    class_label: str
    bfo_parent_iri: str = ""
    bfo_parent_label: str = ""


class IndividualDelete(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    individual_uri: str = Field(..., min_length=1)


class DeleteDataPropertyRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    individual_uri: str = Field(..., min_length=1)
    predicate_uri: str = Field(..., min_length=1)
    value: str


class UpdateDataPropertyRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    individual_uri: str = Field(..., min_length=1)
    predicate_uri: str = Field(..., min_length=1)
    old_value: str
    new_value: str = Field(..., min_length=1)


class DeleteObjectPropertyRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    individual_uri: str = Field(..., min_length=1)
    predicate_uri: str = Field(..., min_length=1)
    other_uri: str = Field(..., min_length=1)


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


# ── Discovery schemas ────────────────────────────────────────────────────────


class DiscoveryClass(BaseModel):
    uri: str
    label: str
    count: int


class DiscoveryProperty(BaseModel):
    uri: str
    label: str
    kind: str


class DiscoveryInstance(BaseModel):
    uri: str
    label: str
    class_uri: str
    class_label: str
    properties: dict[str, str] = Field(default_factory=dict)
    object_properties: dict[str, dict[str, str]] = Field(default_factory=dict)
    domain_relations_count: int = 0
    range_relations_count: int = 0
    properties_count: int = 0
    bfo_bucket_uri: str = ""
    bfo_bucket_label: str = ""


class DiscoveryDataPropertyItem(BaseModel):
    predicate_uri: str
    predicate_label: str
    value: str


class DiscoveryInspectorRelationItem(BaseModel):
    role: str
    predicate_uri: str
    predicate_label: str
    other_uri: str
    other_label: str


class DiscoveryInstanceDetail(BaseModel):
    uri: str
    label: str
    class_uri: str
    class_label: str
    data_properties: list[DiscoveryDataPropertyItem] = Field(default_factory=list)
    relations: list[DiscoveryInspectorRelationItem] = Field(default_factory=list)


class DiscoveryInstanceDetailRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    instance_uri: str = Field(..., min_length=1)


class DiscoveryRelationType(BaseModel):
    uri: str
    label: str
    count: int


class DiscoveryRelationRow(BaseModel):
    relation_uri: str
    relation_label: str
    domain_uri: str
    domain_label: str
    domain_class_uri: str
    domain_class_label: str
    range_uri: str
    range_label: str
    range_class_uri: str
    range_class_label: str
    role: str = "domain"


class DiscoveryPropertiesRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    class_uris: list[str] = Field(default_factory=list)


class DiscoveryInstancesRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    class_uris: list[str] = Field(default_factory=list)
    property_uris: list[str] = Field(default_factory=list)
    search: str = ""
    limit: int | None = Field(default=None, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)
    enrich: bool = True


class DiscoveryRelationTypesRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    instance_uris: list[str] = Field(default_factory=list)


class DiscoveryRelationsRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_uri: str = Field(..., min_length=1)
    instance_uris: list[str] = Field(default_factory=list)
    relation_uris: list[str] = Field(default_factory=list)
    limit: int = Field(default=5000, ge=1, le=50000)


class DiscoveryTripleInput(BaseModel):
    s: str = Field(..., min_length=1)
    p: str = Field(..., min_length=1)
    o: str = ""
    is_literal: bool = False


class DiscoveryTriplesExportRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    triples: list[DiscoveryTripleInput] = Field(default_factory=list)
    format: str = Field(default="ttl", pattern="^(nt|ttl|owl)$")


class DiscoveryTriplesExportResponse(BaseModel):
    content: str
    filename: str
    media_type: str


class GraphKpis(BaseModel):
    individuals: int
    relations: int
    properties: int
    classes: int


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


# ── Network schema (class-level aggregation) ─────────────────────────────────


class NetworkSchemaNode(BaseModel):
    class_uri: str
    class_label: str
    count: int
    bfo_parent_iri: str = ""


class NetworkSchemaEdge(BaseModel):
    source_class_uri: str
    target_class_uri: str
    relation_uri: str
    relation_label: str
    count: int


class NetworkSchema(BaseModel):
    nodes: list[NetworkSchemaNode]
    edges: list[NetworkSchemaEdge]


# ── Network node schemas ─────────────────────────────────────────────────────


class NetworkNodePropertiesRequest(BaseModel):
    workspace_id: str
    graph_uri: str
    class_uri: str


class NetworkNodeInstancesRequest(BaseModel):
    workspace_id: str
    graph_uri: str
    class_uri: str
    property_uris: list[str] = []
    limit: int = Field(default=500, ge=1, le=5000)
    enrich: bool = False
