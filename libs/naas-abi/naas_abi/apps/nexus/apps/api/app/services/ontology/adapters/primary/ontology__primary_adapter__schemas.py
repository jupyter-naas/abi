from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OntologyItem(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None
    example: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ReferenceClass(BaseModel):
    iri: str
    label: str
    definition: str | None = None
    examples: str | None = None
    sub_class_of: list[str] | None = None


class ReferenceProperty(BaseModel):
    iri: str
    label: str
    definition: str | None = None
    inverse_of: str | None = None


class ReferenceOntology(BaseModel):
    id: str
    name: str
    file_path: str
    format: str
    classes: list[ReferenceClass]
    properties: list[ReferenceProperty]
    imported_at: datetime


class OntologyFileItem(BaseModel):
    name: str
    path: str
    module_name: str
    submodule_name: str | None = None
    description: str | None = None
    license: str | None = None
    contributors: list[str] | None = None
    date: str | None = None
    imports: list[str] | None = None


class OntologyOverviewStats(BaseModel):
    name: str
    path: str
    total_items: int
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


class OntologyOverviewAggregateStats(BaseModel):
    name: str
    path: str
    ontologies_count: int
    total_items: int
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


class OntologyTypeCounts(BaseModel):
    name: str
    path: str
    data_properties: int
    named_individuals: int


class OntologyOverviewGraphNode(BaseModel):
    id: str
    label: str
    type: str | None = None
    properties: dict[str, str]


class OntologyOverviewGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str
    properties: dict[str, str]


class OntologyOverviewGraph(BaseModel):
    nodes: list[OntologyOverviewGraphNode]
    edges: list[OntologyOverviewGraphEdge]


class EntityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Entity name")
    description: str | None = Field(None, max_length=2000, description="Entity description")
    base_class: str | None = Field(None, max_length=500, description="Base class IRI")


class RelationshipCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Relationship name")
    description: str | None = Field(None, max_length=2000, description="Relationship description")
    base_property: str | None = Field(None, max_length=500, description="Base property IRI")


class ImportRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5_000_000, description="File content (text, max ~5MB)")
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[\w\-. ]+\.\w+$",
        description="Original filename",
    )
