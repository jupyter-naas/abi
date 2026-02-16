"""Ontology API endpoints for managing ontology items and importing reference ontologies."""

import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# Data models
class OntologyItem(BaseModel):
    id: str
    name: str
    type: str  # entity, relationship, schema, folder
    description: str | None = None
    base_class: str | None = None
    parent_id: str | None = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


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


class EntityCreate(BaseModel):
    """Create a new ontology entity."""

    name: str = Field(..., min_length=1, max_length=200, description="Entity name")
    description: str | None = Field(None, max_length=2000, description="Entity description")
    base_class: str | None = Field(None, max_length=500, description="Base class IRI")


class RelationshipCreate(BaseModel):
    """Create a new ontology relationship."""

    name: str = Field(..., min_length=1, max_length=200, description="Relationship name")
    description: str | None = Field(None, max_length=2000, description="Relationship description")
    base_property: str | None = Field(None, max_length=500, description="Base property IRI")


class ImportRequest(BaseModel):
    content: str = Field(
        ..., min_length=1, max_length=5_000_000, description="File content (text, max ~5MB)"
    )
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[\w\-. ]+\.\w+$",
        description="Original filename",
    )


# In-memory storage (replace with database later)
ontology_items: list[OntologyItem] = []


def parse_ttl(content: str, file_path: str) -> ReferenceOntology:
    """Parse TTL/Turtle format ontology file."""
    classes: list[ReferenceClass] = []
    properties: list[ReferenceProperty] = []

    # Find classes (owl:Class)
    class_pattern = r"<([^>]+)>\s+a\s+owl:Class\s*;([^.]+)\."
    for match in re.finditer(class_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)

        # Extract label
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]

        # Extract definition
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None

        # Extract examples
        example_match = re.search(r'skos:example\s+"([^"]+)"', body)
        examples = example_match.group(1) if example_match else None

        classes.append(
            ReferenceClass(iri=iri, label=label, definition=definition, examples=examples)
        )

    # Find object properties
    prop_pattern = r"<([^>]+)>\s+rdf:type\s+owl:ObjectProperty\s*;?([^.]*)\."
    for match in re.finditer(prop_pattern, content, re.DOTALL):
        iri = match.group(1)
        body = match.group(2)

        # Extract label
        label_match = re.search(r'rdfs:label\s+"([^"]+)"', body)
        label = label_match.group(1) if label_match else iri.split("/")[-1]

        # Extract definition
        def_match = re.search(r'skos:definition\s+"([^"]+)"', body)
        definition = def_match.group(1) if def_match else None

        properties.append(ReferenceProperty(iri=iri, label=label, definition=definition))

    # Extract ontology name
    name_match = re.search(r'dc:title\s+"([^"]+)"', content)
    name = name_match.group(1) if name_match else os.path.basename(file_path).replace(".ttl", "")

    return ReferenceOntology(
        id=f"ref-{int(datetime.now().timestamp() * 1000)}",
        name=name,
        file_path=file_path,
        format="ttl",
        classes=classes,
        properties=properties,
        imported_at=datetime.now(),
    )


@router.get("")
async def list_ontology_items():
    """List all ontology items."""
    return {"items": ontology_items}


@router.post("/entity")
async def create_entity(data: EntityCreate):
    """Create a new entity."""
    item = OntologyItem(
        id=f"entity-{int(datetime.now().timestamp() * 1000)}",
        name=data.name,
        type="entity",
        description=data.description,
        base_class=data.base_class,
    )
    ontology_items.append(item)
    return item


@router.post("/relationship")
async def create_relationship(data: RelationshipCreate):
    """Create a new relationship."""
    item = OntologyItem(
        id=f"rel-{int(datetime.now().timestamp() * 1000)}",
        name=data.name,
        type="relationship",
        description=data.description,
        base_class=data.base_property,
    )
    ontology_items.append(item)
    return item


@router.delete("/{item_id}")
async def delete_item(item_id: str):
    """Delete an ontology item."""
    global ontology_items
    ontology_items = [i for i in ontology_items if i.id != item_id]
    return {"success": True}


@router.post("/import")
async def import_reference_ontology(request: ImportRequest):
    """Import a reference ontology from content (TTL, OWL, RDF).

    Accepts the file content directly - no server filesystem access.
    The frontend should read the file and send its content.
    """
    try:
        content = request.content
        filename = request.filename

        # Determine format from filename extension
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".ttl":
            ontology = parse_ttl(content, filename)
        else:
            # For now, treat all other formats as TTL-like
            ontology = parse_ttl(content, filename)
        return ontology.model_dump()

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to parse ontology file") from e


@router.post("/import/preview")
async def preview_ontology_file(request: ImportRequest):
    """Preview an ontology file before importing.

    Accepts content directly - no server filesystem access.
    """
    try:
        ontology = parse_ttl(request.content, request.filename)

        return {
            "name": ontology.name,
            "classCount": len(ontology.classes),
            "propertyCount": len(ontology.properties),
            "preview": {
                "classes": [c.model_dump() for c in ontology.classes[:5]],
                "properties": [p.model_dump() for p in ontology.properties[:5]],
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to preview ontology file") from e


@router.get("/reference/bfo7")
async def get_bfo7_reference() -> dict:
    """Return the parsed BFO 7 Buckets reference ontology bundled with the server.

    This enables clients to load a standard bucket taxonomy by default without
    shipping the TTL file to the browser. The response mirrors /ontology/import.
    """
    try:
        from pathlib import Path

        # Locate repository root by walking up until we find the 'apps' directory
        p = Path(__file__).resolve()
        root = None
        for _ in range(6):
            if p.name == "apps":
                root = p.parent
                break
            p = p.parent
        if root is None:
            # Fallback: assume five levels up from this file is repo root
            root = Path(__file__).resolve().parents[4]

        ttl_path = root / "ontology" / "BFO7Buckets.ttl"
        if not ttl_path.exists():
            raise FileNotFoundError(f"BFO7Buckets.ttl not found at {ttl_path}")

        content = ttl_path.read_text(encoding="utf-8")
        ontology = parse_ttl(content, str(ttl_path))
        return ontology.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load BFO7 reference ontology") from e
