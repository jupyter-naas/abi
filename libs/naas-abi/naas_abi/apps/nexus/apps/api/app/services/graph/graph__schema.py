from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ── Domain exceptions ────────────────────────────────────────────────────────


class GraphServiceUnavailableError(Exception):
    """Raised when the triple store service cannot be resolved."""


class GraphProtectedError(Exception):
    """Raised when an operation targets a protected system graph (nexus/schema)."""


class GraphQuerySpecError(Exception):
    """Raised when a view query spec is malformed or violates a guard.

    The primary adapter maps this to HTTP 400 (a well-formed body whose spec cannot be
    executed — unknown column, bad IRI, guard exceeded — as opposed to a 422 Pydantic
    shape error).
    """


class GraphAccessError(Exception):
    """Raised when a spec references graphs the workspace does not own.

    The primary adapter maps this to HTTP 403 (authorization, distinct from a malformed
    spec). Workspace isolation == named-graph ownership.
    """


class GraphQueryTimeoutError(Exception):
    """Raised when a query exceeds its per-query budget. Adapter maps to HTTP 504."""


# ── Domain data ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GraphInfoData:
    id: str
    uri: str
    label: str
    role_label: str = "unknown"


@dataclass(frozen=True)
class GraphPackData:
    role_label: str
    graphs: list[GraphInfoData]


@dataclass(frozen=True)
class GraphOverviewData:
    kpis: dict[str, Any]
    instances_by_class: list[dict[str, Any]]


@dataclass(frozen=True)
class GraphNodeData:
    id: str
    workspace_id: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class GraphEdgeData:
    id: str
    workspace_id: str
    source_id: str
    target_id: str
    source_label: str
    target_label: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class GraphNetworkData:
    nodes: list[GraphNodeData]
    edges: list[GraphEdgeData]


# ── Discovery (Notion/Excel-like exploration) ────────────────────────────────


@dataclass(frozen=True)
class DiscoveryClassData:
    uri: str
    label: str
    count: int


@dataclass(frozen=True)
class DiscoveryClassMetaData:
    class_uri: str
    class_label: str
    bfo_parent_iri: str
    bfo_parent_label: str


@dataclass(frozen=True)
class DiscoveryPropertyData:
    uri: str
    label: str
    kind: str  # "datatype" | "annotation"


@dataclass(frozen=True)
class DiscoveryRangeOptionData:
    uri: str
    label: str
    kind: str  # "class" | "individual"


@dataclass(frozen=True)
class DiscoveryClassObjectPropertyData:
    uri: str
    label: str
    range_options: list[DiscoveryRangeOptionData]


@dataclass(frozen=True)
class DiscoveryRelationTargetData:
    uri: str
    label: str
    class_uri: str
    class_label: str


@dataclass(frozen=True)
class DiscoveryInstanceData:
    uri: str
    label: str
    class_uri: str
    class_label: str
    properties: dict[str, str]
    object_properties: dict[str, dict[str, str]] = field(default_factory=dict)
    domain_relations_count: int = 0
    range_relations_count: int = 0
    properties_count: int = 0
    bfo_bucket_uri: str = ""
    bfo_bucket_label: str = ""


@dataclass(frozen=True)
class DiscoveryRelationTypeData:
    uri: str
    label: str
    count: int


@dataclass(frozen=True)
class DiscoveryRelationRowData:
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
    role: str = "domain"  # "domain" = working instance is subject; "range" = working instance is object


@dataclass(frozen=True)
class DiscoveryDataProperty:
    predicate_uri: str
    predicate_label: str
    value: str


@dataclass(frozen=True)
class DiscoveryInspectorRelation:
    role: str  # "domain" | "range"
    predicate_uri: str
    predicate_label: str
    other_uri: str
    other_label: str


@dataclass(frozen=True)
class DiscoveryInstanceDetailData:
    uri: str
    label: str
    class_uri: str
    class_label: str
    data_properties: list[DiscoveryDataProperty]
    relations: list[DiscoveryInspectorRelation]


@dataclass(frozen=True)
class GraphKpisData:
    classes: int
    individuals: int
    relations: int
    properties: int


@dataclass(frozen=True)
class NetworkSchemaNodeData:
    class_uri: str
    class_label: str
    count: int
    bfo_parent_iri: str = ""


@dataclass(frozen=True)
class NetworkSchemaEdgeData:
    source_class_uri: str
    target_class_uri: str
    relation_uri: str
    relation_label: str
    count: int


@dataclass(frozen=True)
class NetworkSchemaData:
    nodes: list[NetworkSchemaNodeData]
    edges: list[NetworkSchemaEdgeData]


@dataclass(frozen=True)
class GraphAnalysisData:
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
