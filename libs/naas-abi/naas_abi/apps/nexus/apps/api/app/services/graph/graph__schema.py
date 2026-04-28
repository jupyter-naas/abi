from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ── Domain exceptions ────────────────────────────────────────────────────────


class GraphServiceUnavailableError(Exception):
    """Raised when the triple store service cannot be resolved."""


class GraphProtectedError(Exception):
    """Raised when an operation targets a protected system graph (nexus/schema)."""


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
