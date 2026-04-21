from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ── Domain exceptions ─────────────────────────────────────────────────────────


class OntologyPathNotFoundError(Exception):
    """Raised when a requested ontology path is not registered."""


class OntologyServiceUnavailableError(Exception):
    """Raised when the underlying triple store / ABIModule cannot be resolved."""


class OntologyParseError(Exception):
    """Raised when an ontology file cannot be parsed."""


class OntologyFileNotFoundError(Exception):
    """Raised when an ontology file does not exist on the filesystem."""


# ── Domain data ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OntologyItemData:
    id: str
    name: str
    type: str
    description: str | None = None
    example: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ReferenceClassData:
    iri: str
    label: str
    definition: str | None = None
    examples: str | None = None
    sub_class_of: list[str] | None = None


@dataclass(frozen=True)
class ReferencePropertyData:
    iri: str
    label: str
    definition: str | None = None
    inverse_of: str | None = None


@dataclass(frozen=True)
class ReferenceOntologyData:
    id: str
    name: str
    file_path: str
    format: str
    classes: list[ReferenceClassData]
    properties: list[ReferencePropertyData]
    imported_at: datetime


@dataclass(frozen=True)
class OntologyFileItemData:
    name: str
    path: str
    module_name: str
    submodule_name: str | None = None
    description: str | None = None
    license: str | None = None
    contributors: list[str] = field(default_factory=list)
    date: str | None = None
    imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OntologyOverviewStatsData:
    name: str
    path: str
    total_items: int
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


@dataclass(frozen=True)
class OntologyOverviewAggregateStatsData:
    name: str
    path: str
    ontologies_count: int
    total_items: int
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


@dataclass(frozen=True)
class OntologyTypeCountsData:
    name: str
    path: str
    data_properties: int
    named_individuals: int


@dataclass(frozen=True)
class OntologyOverviewGraphNodeData:
    id: str
    label: str
    properties: dict[str, str]
    type: str | None = None


@dataclass(frozen=True)
class OntologyOverviewGraphEdgeData:
    id: str
    source: str
    target: str
    type: str
    label: str
    properties: dict[str, str]


@dataclass(frozen=True)
class OntologyOverviewGraphData:
    nodes: list[OntologyOverviewGraphNodeData]
    edges: list[OntologyOverviewGraphEdgeData]
