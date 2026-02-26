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
from rdflib.term import URIRef

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
    type: str
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


def _resolve_target_ontology_paths(
    ontology_path: str | None, ontologies: list[OntologyFileItem]
) -> list[str]:
    ontology_paths: list[str] = [item.path for item in ontologies]
    if ontology_path:
        if ontology_path not in ontology_paths:
            raise HTTPException(status_code=404, detail="Ontology path not found")
        return [ontology_path]
    return ontology_paths


def _sparql_iri(value: str) -> str | None:
    """Return a safe SPARQL IRI token or None when value is invalid."""
    candidate = value.strip()
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
    from rdflib.query import ResultRow

    """List ontology classes by file path (or all registered ontologies when omitted)."""
    ontologies = await list_ontology_files()
    target_paths = _resolve_target_ontology_paths(ontology_path, ontologies["items"])
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
            assert isinstance(row, ResultRow)
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
    from rdflib.query import ResultRow

    ontologies = await list_ontology_files()
    target_paths = _resolve_target_ontology_paths(ontology_path, ontologies["items"])
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
            assert isinstance(row, ResultRow)
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

        def _count_iri_subjects(rdf_type: URIRef) -> int:
            return len({subject for subject in graph.subjects(RDF.type, rdf_type) if isinstance(subject, URIRef)})

        classes_count = _count_iri_subjects(OWL.Class)
        object_properties_count = _count_iri_subjects(OWL.ObjectProperty)
        data_properties_count = _count_iri_subjects(OWL.DatatypeProperty)
        named_individuals_count = _count_iri_subjects(OWL.NamedIndividual)
        total_items_count = (
            classes_count
            + object_properties_count
            + data_properties_count
            + named_individuals_count
        )
        imports_count = len(set(graph.objects(None, OWL.imports)))

        return OntologyOverviewStats(
            name=Path(ontology_path).name,
            path=ontology_path,
            total_items=total_items_count,
            classes=classes_count,
            object_properties=object_properties_count,
            data_properties=data_properties_count,
            named_individuals=named_individuals_count,
            imports=imports_count,
        )
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
        ontologies = await list_ontology_files()
        ontology_paths = [item.path for item in ontologies.get("items", [])]
        totals = {
            "total_items": 0,
            "classes": 0,
            "object_properties": 0,
            "data_properties": 0,
            "named_individuals": 0,
            "imports": 0,
        }

        for ontology_path in ontology_paths:
            stats = await get_ontology_overview_stats(ontology_path)
            totals["total_items"] += stats.total_items
            totals["classes"] += stats.classes
            totals["object_properties"] += stats.object_properties
            totals["data_properties"] += stats.data_properties
            totals["named_individuals"] += stats.named_individuals
            totals["imports"] += stats.imports

        return OntologyOverviewAggregateStats(
            name="All ontologies",
            path="*",
            ontologies_count=len(ontology_paths),
            total_items=totals["total_items"],
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
        ontologies = await list_ontology_files()
        target_paths = _resolve_target_ontology_paths(ontology_path, ontologies["items"])
        named_individuals = 0
        data_properties = 0

        for path in target_paths:
            graph = _load_ontology_graph(path)
            named_individuals += len(set(graph.subjects(RDF.type, OWL.NamedIndividual)))
            data_properties += len(set(graph.subjects(RDF.type, OWL.DatatypeProperty)))

        return OntologyTypeCounts(
            name=Path(ontology_path).name if ontology_path else "All ontologies",
            path=ontology_path or "*",
            data_properties=data_properties,
            named_individuals=named_individuals,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to compute ontology type counts"
        ) from exc


@router.get("/overview/graph")
async def get_ontology_overview_graph(
    ontology_path: str | None = Query(None, alias="ontology_path"),
) -> OntologyOverviewGraph:
    """Return graph data where nodes are classes and edges are class relations."""
    from rdflib.query import ResultRow

    try:
        ontologies = await list_ontology_files()
        target_paths = _resolve_target_ontology_paths(ontology_path, ontologies["items"])

        classes_by_iri: dict[str, OntologyOverviewGraphNode] = {}
        edges_by_id: dict[str, OntologyOverviewGraphEdge] = {}

        class_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?classIri ?label ?definition ?parentIri ?parentLabel WHERE {
                ?classIri rdf:type owl:Class .
                FILTER(isIRI(?classIri))
                OPTIONAL { ?classIri rdfs:label ?label . }
                OPTIONAL { ?classIri skos:definition ?definition . }
                OPTIONAL {
                    ?classIri rdfs:subClassOf ?parentIri .
                    FILTER(isIRI(?parentIri))
                    OPTIONAL { ?parentIri rdfs:label ?parentLabel . }
                }
            }
        """

        relation_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?propertyIri ?propertyLabel ?propertyDefinition ?domain ?range ?parentPropertyIri WHERE {
                ?propertyIri rdf:type owl:ObjectProperty .
                FILTER(isIRI(?propertyIri))
                OPTIONAL { ?propertyIri rdfs:label ?propertyLabel . }
                OPTIONAL { ?propertyIri skos:definition ?propertyDefinition . }
                OPTIONAL {
                    ?propertyIri rdfs:domain ?domain .
                    FILTER(isIRI(?domain))
                }
                OPTIONAL {
                    ?propertyIri rdfs:range ?range .
                    FILTER(isIRI(?range))
                }
                OPTIONAL {
                    ?propertyIri rdfs:subPropertyOf ?parentPropertyIri .
                    FILTER(isIRI(?parentPropertyIri))
                }
            }
        """

        subclass_query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?childClass ?parentClass WHERE {
                ?childClass rdfs:subClassOf ?parentClass .
                FILTER(isIRI(?childClass) && isIRI(?parentClass))
            }
        """

        for path in target_paths:
            graph = _load_ontology_graph(path)

            for row in graph.query(class_query):
                assert isinstance(row, ResultRow)
                class_iri = str(row.get("classIri"))
                if not class_iri:
                    continue
                class_label = (
                    str(row.get("label")) if row.get("label") else class_iri.split("/")[-1]
                )
                definition = str(row.get("definition")) if row.get("definition") else ""
                parent_iri = str(row.get("parentIri")) if row.get("parentIri") else ""
                parent_label = str(row.get("parentLabel")) if row.get("parentLabel") else ""

                existing = classes_by_iri.get(class_iri)
                if existing:
                    if not existing.properties.get("definition") and definition:
                        existing.properties["definition"] = definition
                    if not existing.properties.get("parent_iri") and parent_iri:
                        existing.properties["parent_iri"] = parent_iri
                    if not existing.properties.get("parent_label") and parent_label:
                        existing.properties["parent_label"] = parent_label
                    continue

                properties = {
                    "iri": class_iri,
                    "definition": definition,
                    "parent_iri": parent_iri,
                    "parent_label": parent_label,
                }
                classes_by_iri[class_iri] = OntologyOverviewGraphNode(
                    id=class_iri,
                    label=class_label,
                    type="Entity",
                    properties=properties,
                )

            for row in graph.query(relation_query):
                assert isinstance(row, ResultRow)
                property_iri = str(row.get("propertyIri"))
                if not property_iri:
                    continue

                source_iri = str(row.get("domain")) if row.get("domain") else None
                target_iri = str(row.get("range")) if row.get("range") else None
                if not source_iri or not target_iri:
                    continue

                if source_iri not in classes_by_iri:
                    classes_by_iri[source_iri] = OntologyOverviewGraphNode(
                        id=source_iri,
                        label=source_iri.split("/")[-1],
                        type="Entity",
                        properties={"iri": source_iri},
                    )
                if target_iri not in classes_by_iri:
                    classes_by_iri[target_iri] = OntologyOverviewGraphNode(
                        id=target_iri,
                        label=target_iri.split("/")[-1],
                        type="Entity",
                        properties={"iri": target_iri},
                    )

                property_label = (
                    str(row.get("propertyLabel"))
                    if row.get("propertyLabel")
                    else property_iri.split("/")[-1]
                )
                edge_id = f"{source_iri}|{property_iri}|{target_iri}"
                if edge_id in edges_by_id:
                    continue

                property_definition = (
                    str(row.get("propertyDefinition")) if row.get("propertyDefinition") else ""
                )
                parent_property_iri = (
                    str(row.get("parentPropertyIri")) if row.get("parentPropertyIri") else ""
                )
                edges_by_id[edge_id] = OntologyOverviewGraphEdge(
                    id=edge_id,
                    source=source_iri,
                    target=target_iri,
                    type=property_label,
                    label=property_label,
                    properties={
                        "relation_kind": "object_property",
                        "iri": property_iri,
                        "definition": property_definition,
                        "parent_property_iri": parent_property_iri,
                    },
                )

            for row in graph.query(subclass_query):
                assert isinstance(row, ResultRow)
                child_class = str(row.get("childClass")) if row.get("childClass") else ""
                parent_class = str(row.get("parentClass")) if row.get("parentClass") else ""
                if not child_class or not parent_class:
                    continue

                if child_class not in classes_by_iri:
                    classes_by_iri[child_class] = OntologyOverviewGraphNode(
                        id=child_class,
                        label=child_class.split("/")[-1],
                        type="Entity",
                        properties={"iri": child_class, "definition": "", "parent_iri": "", "parent_label": ""},
                    )
                if parent_class not in classes_by_iri:
                    classes_by_iri[parent_class] = OntologyOverviewGraphNode(
                        id=parent_class,
                        label=parent_class.split("/")[-1],
                        type="Entity",
                        properties={"iri": parent_class, "definition": "", "parent_iri": "", "parent_label": ""},
                    )

                edge_id = f"{child_class}|is-a|{parent_class}"
                if edge_id in edges_by_id:
                    continue
                edges_by_id[edge_id] = OntologyOverviewGraphEdge(
                    id=edge_id,
                    source=child_class,
                    target=parent_class,
                    type="is a",
                    label="is a",
                    properties={
                        "relation_kind": "subclass_of",
                        "iri": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
                        "definition": "Subclass relationship between two classes.",
                        "parent_property_iri": "",
                    },
                )

        nodes = sorted(classes_by_iri.values(), key=lambda node: node.label.lower())
        edges = sorted(edges_by_id.values(), key=lambda edge: edge.label.lower())
        return OntologyOverviewGraph(nodes=nodes, edges=edges)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to compute ontology overview graph") from exc


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
                if (
                    "sparqlquery" in ontology_path.lower()
                    or "sparqlqueries" in ontology_path.lower()
                ):
                    continue
                if ontology_path not in seen_paths:
                    if module_name.lower() in ontology_path.lower():
                        seen_paths.add(ontology_path)
                        ontology_files.append(
                            OntologyFileItem(
                                name=os.path.basename(ontology_path),
                                path=ontology_path,
                                module_name=module_name,
                            )
                        )
                    elif "/naas-abi/" in ontology_path.lower():
                        seen_paths.add(ontology_path)
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
    path = Path(ontology_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Ontology file does not exist")

    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
