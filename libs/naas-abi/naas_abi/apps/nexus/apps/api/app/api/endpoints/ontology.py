"""Ontology API endpoints for managing ontology items and importing reference ontologies."""

import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from pydantic import BaseModel, Field
from rdflib import Graph
from rdflib.namespace import OWL, RDF

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# Data models
class OntologyItem(BaseModel):
    id: str
    name: str
    type: str  # entity, relationship, schema, folder
    description: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
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


class OntologyFileItem(BaseModel):
    name: str
    path: str
    module_name: str
    submodule_name: str | None = None


class OntologyOverviewStats(BaseModel):
    name: str
    path: str
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


class OntologyOverviewAggregateStats(BaseModel):
    name: str
    path: str
    ontologies_count: int
    classes: int
    object_properties: int
    data_properties: int
    named_individuals: int
    imports: int


class OntologyTypeCounts(BaseModel):
    name: str
    path: str
    named_individuals: int
    data_properties: int


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


def _resolve_ontology_directory() -> Path:
    """Resolve repository ontology directory for the NEXUS app."""
    p = Path(__file__).resolve()
    root = None
    for _ in range(8):
        if p.name == "apps":
            root = p.parent
            break
        p = p.parent
    if root is None:
        root = Path(__file__).resolve().parents[6]
    return root / "ontology"


def _list_registered_ontology_paths() -> set[str]:
    """Return ontology file paths declared by all loaded ABI modules."""
    abi_module = ABIModule.get_instance()
    paths: set[str] = set()
    for module in abi_module.engine.modules.values():
        ontologies = getattr(module, "ontologies", None) or []
        for ontology in ontologies:
            paths.add(str(ontology))
    return paths


def _compute_ontology_overview_stats(ontology_path: str) -> OntologyOverviewStats:
    extension = Path(ontology_path).suffix.lower()
    parse_format = {
        ".ttl": "turtle",
        ".owl": "xml",
        ".rdf": "xml",
        ".nt": "nt",
    }.get(extension)

    graph = Graph()
    try:
        graph.parse(ontology_path, format=parse_format)
    except Exception:
        # Fallback to rdflib format auto-detection when explicit mapping fails.
        graph.parse(ontology_path)

    classes_count = len(set(graph.subjects(RDF.type, OWL.Class)))
    object_properties_count = len(set(graph.subjects(RDF.type, OWL.ObjectProperty)))
    data_properties_count = len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))
    named_individuals_count = len(set(graph.subjects(RDF.type, OWL.NamedIndividual)))
    imports_count = len(set(graph.objects(None, OWL.imports)))

    return OntologyOverviewStats(
        name=Path(ontology_path).name,
        path=ontology_path,
        classes=classes_count,
        object_properties=object_properties_count,
        data_properties=data_properties_count,
        named_individuals=named_individuals_count,
        imports=imports_count,
    )


def _load_ontology_graph(ontology_path: str) -> Graph:
    extension = Path(ontology_path).suffix.lower()
    parse_format = {
        ".ttl": "turtle",
        ".owl": "xml",
        ".rdf": "xml",
        ".nt": "nt",
    }.get(extension)

    graph = Graph()
    try:
        graph.parse(ontology_path, format=parse_format)
    except Exception:
        # Fallback to rdflib format auto-detection when explicit mapping fails.
        graph.parse(ontology_path)
    return graph


def _resolve_target_ontology_paths(ontology_path: str | None) -> list[str]:
    registered_paths = sorted(_list_registered_ontology_paths())
    if ontology_path:
        if ontology_path not in registered_paths:
            raise HTTPException(status_code=404, detail="Ontology path not found")
        return [ontology_path]
    return registered_paths


def _sparql_iri(value: str) -> str | None:
    """Return a safe SPARQL IRI token or None when value is invalid."""
    candidate = (value or "").strip()
    if not candidate:
        return None
    # Basic guard to avoid malformed query injection.
    if any(char in candidate for char in ("<", ">", '"', "'", " ")):
        return None
    return f"<{candidate}>"


def _get_parent_labels_from_triple_store(parent_ids: set[str]) -> dict[str, str]:
    """Resolve parent labels from the configured triple store service."""
    if not parent_ids:
        return {}

    iri_values = [iri for value in sorted(parent_ids) if (iri := _sparql_iri(value)) is not None]
    if not iri_values:
        return {}

    try:
        triple_store_service = ABIModule.get_instance().engine.services.triple_store
    except Exception:
        return {}

    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?parentId ?label WHERE {{
            VALUES ?parentId {{ {" ".join(iri_values)} }}
            OPTIONAL {{ ?parentId rdfs:label ?label . }}
        }}
    """

    labels: dict[str, str] = {}
    rows = triple_store_service.query(query)
    for row in rows:
        parent_id = str(getattr(row, "parentId", "") or "")
        label = str(getattr(row, "label", "") or "")
        if parent_id and label and parent_id not in labels:
            labels[parent_id] = label
    return labels


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
    """List all ontology items (OWL Classes and Object Properties) with label, definition, type, and subclassOf."""
    classes = await list_classes()
    relationships = await list_relations()
    return {
        "items": [*classes.get("items", []), *relationships.get("items", [])],
    }


@router.get("/classes")
async def list_classes(
    ontology_path: str | None = Query(None, alias="ontology_path"),
):
    """List ontology classes by file path (or all registered ontologies when omitted)."""
    target_paths = _resolve_target_ontology_paths(ontology_path)
    by_iri: dict[str, OntologyItem] = {}

    query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?s ?label ?definition ?parentId WHERE {
            ?s rdf:type owl:Class .
            FILTER(isIRI(?s))
            OPTIONAL { ?s rdfs:label ?label . }
            OPTIONAL { ?s skos:definition ?definition . }
            OPTIONAL {
                ?s rdfs:subClassOf ?parentId .
                FILTER(isIRI(?parentId))
            }
        }
    """

    for path in target_paths:
        graph = _load_ontology_graph(path)
        for row in graph.query(query):
            iri = str(row.get("s"))
            label = str(row.get("label")) if row.get("label") else iri.split("/")[-1]
            definition = str(row.get("definition")) if row.get("definition") else None
            parent_id = str(row.get("parentId")) if row.get("parentId") else None
            existing = by_iri.get(iri)
            if existing:
                if existing.parent_id is None and parent_id is not None:
                    existing.parent_id = parent_id
                if existing.description is None and definition is not None:
                    existing.description = definition
                continue

            by_iri[iri] = OntologyItem(
                id=iri,
                name=label,
                type="entity",
                description=definition,
                parent_id=parent_id,
            )

    parent_labels = _get_parent_labels_from_triple_store(
        {item.parent_id for item in by_iri.values() if item.parent_id}
    )
    for item in by_iri.values():
        if item.parent_id:
            item.parent_name = parent_labels.get(item.parent_id)

    items = sorted(by_iri.values(), key=lambda item: item.name.lower())
    return {"items": items}


@router.get("/relationships")
async def list_relations(
    ontology_path: str | None = Query(None, alias="ontology_path"),
):
    """List ontology object properties by file path (or all registered ontologies when omitted)."""
    target_paths = _resolve_target_ontology_paths(ontology_path)
    by_iri: dict[str, OntologyItem] = {}

    query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?s ?label ?definition ?parentId WHERE {
            ?s rdf:type owl:ObjectProperty .
            FILTER(isIRI(?s))
            OPTIONAL { ?s rdfs:label ?label . }
            OPTIONAL { ?s skos:definition ?definition . }
            OPTIONAL {
                ?s rdfs:subPropertyOf ?parentId .
                FILTER(isIRI(?parentId))
            }
        }
    """

    for path in target_paths:
        graph = _load_ontology_graph(path)
        for row in graph.query(query):
            iri = str(row.get("s"))
            label = str(row.get("label")) if row.get("label") else iri.split("/")[-1]
            definition = str(row.get("definition")) if row.get("definition") else None
            parent_id = str(row.get("parentId")) if row.get("parentId") else None
            existing = by_iri.get(iri)
            if existing:
                if existing.parent_id is None and parent_id is not None:
                    existing.parent_id = parent_id
                if existing.description is None and definition is not None:
                    existing.description = definition
                continue

            by_iri[iri] = OntologyItem(
                id=iri,
                name=label,
                type="relationship",
                description=definition,
                parent_id=parent_id,
            )

    parent_labels = _get_parent_labels_from_triple_store(
        {item.parent_id for item in by_iri.values() if item.parent_id}
    )
    for item in by_iri.values():
        if item.parent_id:
            item.parent_name = parent_labels.get(item.parent_id)

    items = sorted(by_iri.values(), key=lambda item: item.name.lower())
    return {"items": items}


@router.get("/overview/stats")
async def get_ontology_overview_stats(
    ontology_path: str = Query(..., alias="ontology_path", min_length=1),
) -> OntologyOverviewStats:
    """Return ontology element counts for a specific ontology path."""
    try:
        registered_paths = _list_registered_ontology_paths()
        if ontology_path not in registered_paths:
            raise HTTPException(status_code=404, detail="Ontology path not found")
        return _compute_ontology_overview_stats(ontology_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to compute ontology overview stats"
        ) from exc


@router.get("/overview/stats/all")
async def get_all_ontologies_overview_stats() -> OntologyOverviewAggregateStats:
    """Return consolidated overview stats across all registered ontologies."""
    try:
        ontology_paths = sorted(_list_registered_ontology_paths())
        totals = {
            "classes": 0,
            "object_properties": 0,
            "data_properties": 0,
            "named_individuals": 0,
            "imports": 0,
        }

        for ontology_path in ontology_paths:
            stats = _compute_ontology_overview_stats(ontology_path)
            totals["classes"] += stats.classes
            totals["object_properties"] += stats.object_properties
            totals["data_properties"] += stats.data_properties
            totals["named_individuals"] += stats.named_individuals
            totals["imports"] += stats.imports

        return OntologyOverviewAggregateStats(
            name="All ontologies",
            path="*",
            ontologies_count=len(ontology_paths),
            classes=totals["classes"],
            object_properties=totals["object_properties"],
            data_properties=totals["data_properties"],
            named_individuals=totals["named_individuals"],
            imports=totals["imports"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to compute consolidated ontology overview stats"
        ) from exc


@router.get("/counts/types")
async def get_ontology_type_counts(
    ontology_path: str | None = Query(None, alias="ontology_path"),
) -> OntologyTypeCounts:
    """Return counts for owl:NamedIndividual and owl:DatatypeProperty."""
    try:
        target_paths = _resolve_target_ontology_paths(ontology_path)
        named_individuals = 0
        data_properties = 0

        for path in target_paths:
            graph = _load_ontology_graph(path)
            named_individuals += len(set(graph.subjects(RDF.type, OWL.NamedIndividual)))
            data_properties += len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))

        return OntologyTypeCounts(
            name=Path(ontology_path).name if ontology_path else "All ontologies",
            path=ontology_path or "*",
            named_individuals=named_individuals,
            data_properties=data_properties,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to compute ontology type counts"
        ) from exc


@router.post("/entity")
async def create_entity(data: EntityCreate):
    """Create a new entity."""
    item = OntologyItem(
        id=f"entity-{int(datetime.now().timestamp() * 1000)}",
        name=data.name,
        type="entity",
        description=data.description,
        parent_id=data.base_class,
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
        parent_id=data.base_property,
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

    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to parse ontology file") from exc


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

    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to preview ontology file") from exc


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
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to load BFO7 reference ontology"
        ) from exc


@router.get("/ontologies")
async def list_ontology_files() -> dict[str, list[OntologyFileItem]]:
    """
    List ontology files loaded into the platform from all registered modules.
    Deduplicates ontology files across all modules but ensures at least
    one 'naas-abi' (or abi) entry is present for each unique file.
    """
    try:
        abi_module = ABIModule.get_instance()

        ontology_files: list[OntologyFileItem] = []
        seen_paths: set[str] = set()

        # Gather all ontologies, and keep a record if any belong to naas-abi/abi.
        for module in abi_module.engine.modules.values():
            module_name = str(module.__module__.split(".")[-1])
            for ontology in module.ontologies:
                ontology_path = str(ontology)
                submodule_name = ontology_path.split("/")[-2]
                if "sparqlquery" in ontology_path.lower():
                    continue
                if ontology_path not in seen_paths:
                    seen_paths.add(ontology_path)
                    if module_name.lower() in ontology_path.lower():
                        ontology_files.append(
                            OntologyFileItem(
                                name=os.path.basename(ontology_path),
                                path=ontology_path,
                                module_name=module_name,
                            )
                        )
                    elif "/naas-abi/" in ontology_path.lower():
                        ontology_files.append(
                            OntologyFileItem(
                                name=os.path.basename(ontology_path),
                                path=ontology_path,
                                module_name="abi",
                                submodule_name=submodule_name,
                            )
                        )

        ontology_files.sort(key=lambda item: (item.module_name.lower(), item.name.lower()))
        return {"items": ontology_files}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to list ontology files") from exc


@router.get("/export")
async def export_ontology_file(
    ontology_path: str = Query(..., alias="ontology_path", min_length=1),
):
    """Export a selected ontology file as attachment."""
    registered_paths = _list_registered_ontology_paths()
    if ontology_path not in registered_paths:
        raise HTTPException(status_code=404, detail="Ontology path not found")

    path = Path(ontology_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Ontology file does not exist")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
