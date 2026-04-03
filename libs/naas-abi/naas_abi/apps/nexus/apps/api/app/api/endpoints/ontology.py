"""Ontology API endpoints for managing ontology items and importing reference ontologies."""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi_core import logger
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from pydantic import BaseModel, Field
from rdflib import Graph
from rdflib.namespace import OWL, RDF
from rdflib.query import ResultRow
from rdflib.term import URIRef

cache = CacheFactory.CacheFS_find_storage(subpath="ontology")

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# Data models
class OntologyItem(BaseModel):
    id: str
    name: str
    type: str  # entity, relationship, schema, folder
    description: str | None = None
    example: str | None = None
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


def _load_ontology_graph(ontology_path: str, add_imports: bool = False) -> Graph:
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

    if add_imports:
        imports = graph.objects(None, OWL.imports)
        for import_uri in imports:
            graph_imports = Graph()
            try:
                import_path = str(import_uri)
                import_extension = Path(import_path).suffix.lower()
                import_parse_format = {
                    ".ttl": "turtle",
                    ".owl": "xml",
                    ".rdf": "xml",
                    ".nt": "nt",
                }.get(import_extension)
                graph_imports.parse(import_path, format=import_parse_format)
            except Exception as e:
                logger.error(f"Error parsing import {import_uri}: {e}")
                continue
            graph += graph_imports
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


@cache(lambda uri: f"uri_metadata_{uri}", DataType.JSON, ttl=timedelta(days=1))
def get_uri_metadata(uri: str) -> dict:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?label ?definition ?example ?subClassOf ?subPropertyOf
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            OPTIONAL {{ <{uri}> rdfs:label ?label . }}
            OPTIONAL {{ <{uri}> skos:definition ?definition . }}
            OPTIONAL {{ <{uri}> skos:example ?example . }}
            OPTIONAL {{
                <{uri}> rdfs:subClassOf ?subClassOf .
                FILTER(isIRI(?subClassOf))
            }}
            OPTIONAL {{
                <{uri}> rdfs:subPropertyOf ?subPropertyOf .
                FILTER(isIRI(?subPropertyOf))
            }}
        }}
    }}
    """
    result: dict = {}
    rows = ABIModule.get_instance().engine.services.triple_store.query(query)
    for row in rows:
        assert isinstance(row, ResultRow)
        result = {
            "label": str(row.label) if row.label else uri,
            "definition": str(row.definition) if row.definition else None,
            "example": str(row.example) if row.example else None,
            "subClassOf": str(row.subClassOf) if row.subClassOf else None,
            "subPropertyOf": str(row.subPropertyOf) if row.subPropertyOf else None,
        }
    return result


# @cache(lambda uri: f"uri_metadata_{uri}", DataType.JSON, ttl=timedelta(days=1))
def get_ontology_metadata(ontology_iri: str) -> dict:
    from naas_abi import ABIModule
    from rdflib.query import ResultRow

    """
    Get metadata for an OWL ontology (owl:Ontology) given its IRI.
    Metadata includes label, comment, version info, contributors, title, description, and license.
    """
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX dc11: <http://purl.org/dc/elements/1.1/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT ?label ?comment ?versionInfo ?contributor ?title ?description ?license ?date
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{ontology_iri}> rdf:type owl:Ontology .
            OPTIONAL {{ <{ontology_iri}> rdfs:comment ?comment . }}
            OPTIONAL {{ <{ontology_iri}> owl:versionInfo ?versionInfo . }}
            OPTIONAL {{ <{ontology_iri}> dc:title ?title . }}
            OPTIONAL {{ <{ontology_iri}> dc:description ?description . }}
            OPTIONAL {{ <{ontology_iri}> dc:license ?license . }}
            OPTIONAL {{ <{ontology_iri}> dc11:date ?date . }}
        }}
    }}
    """
    rows = ABIModule.get_instance().engine.services.triple_store.query(query)
    result = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        result.update(
            {
                "comment": str(row.comment) if getattr(row, "comment", None) else None,
                "versionInfo": str(row.versionInfo) if getattr(row, "versionInfo", None) else None,
                "title": str(row.title) if getattr(row, "title", None) else None,
                "description": str(row.description) if getattr(row, "description", None) else None,
                "license": str(row.license) if getattr(row, "license", None) else None,
                "date": str(row.date) if getattr(row, "date", None) else None,
            }
        )
    return result


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
        SELECT ?s WHERE {
            ?s rdf:type owl:Class .
            FILTER(isIRI(?s))
        }
    """

    for path in target_paths:
        graph = _load_ontology_graph(path)
        for row in graph.query(query):
            assert isinstance(row, ResultRow)
            iri = str(row.get("s"))
            existing = by_iri.get(iri)
            if existing:
                continue

            data = get_uri_metadata(iri)
            label = data.get("label", "Unknown")
            definition = data.get("definition")
            example = data.get("example")
            parent_id = data.get("subClassOf")
            parent_data = get_uri_metadata(parent_id) if parent_id else None
            parent_label = parent_data.get("label", "Unknown") if parent_data else None

            by_iri[iri] = OntologyItem(
                id=iri,
                name=label,
                type="Class",
                description=definition,
                example=example,
                parent_id=parent_id,
                parent_name=parent_label,
            )

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
            data = get_uri_metadata(iri)
            label = data.get("label", "Unknown")
            definition = data.get("definition")
            parent_id = data.get("subPropertyOf")
            parent_data = get_uri_metadata(parent_id) if parent_id else None
            parent_label = parent_data.get("label", "Unknown") if parent_data else None
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
                type="Object Property",
                description=definition,
                parent_id=parent_id,
                parent_name=parent_label,
            )

    items = sorted(by_iri.values(), key=lambda item: item.name.lower())
    return {"items": items}


@router.get("/overview/stats")
async def get_ontology_overview_stats(
    ontology_path: str = Query(..., alias="ontology_path", min_length=1),
) -> OntologyOverviewStats:
    """Return ontology element counts for a specific ontology path."""
    try:
        graph = _load_ontology_graph(ontology_path)
        (
            classes_count,
            object_properties_count,
            data_properties_count,
            named_individuals_count,
            imports_count,
        ) = _compute_ontology_stats_for_graph(graph)
        total_items_count = (
            classes_count
            + object_properties_count
            + data_properties_count
            + named_individuals_count
        )
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


def _compute_ontology_stats_for_graph(graph: Graph) -> tuple[int, int, int, int, int]:
    """Return (classes, object_properties, data_properties, named_individuals, imports) for a graph."""

    def _count_iri_subjects(rdf_type: URIRef) -> int:
        return len(
            {
                subject
                for subject in graph.subjects(RDF.type, rdf_type)
                if isinstance(subject, URIRef)
            }
        )

    classes_count = _count_iri_subjects(OWL.Class)
    object_properties_count = _count_iri_subjects(OWL.ObjectProperty)
    data_properties_count = _count_iri_subjects(OWL.DatatypeProperty)
    named_individuals_count = _count_iri_subjects(OWL.NamedIndividual)
    imports_count = len(set(graph.objects(None, OWL.imports)))
    return (
        classes_count,
        object_properties_count,
        data_properties_count,
        named_individuals_count,
        imports_count,
    )


@router.get("/overview/stats/all")
async def get_all_ontologies_overview_stats() -> OntologyOverviewAggregateStats:
    """Return consolidated overview stats across all registered ontology files (file-based aggregation)."""
    try:
        ontologies = await list_ontology_files()
        ontology_paths = [item.path for item in ontologies.get("items", [])]

        total_classes = 0
        total_object_properties = 0
        total_data_properties = 0
        total_named_individuals = 0
        total_imports = 0

        for path in ontology_paths:
            try:
                graph = _load_ontology_graph(path)
                (
                    classes_count,
                    object_properties_count,
                    data_properties_count,
                    named_individuals_count,
                    imports_count,
                ) = _compute_ontology_stats_for_graph(graph)
                total_classes += classes_count
                total_object_properties += object_properties_count
                total_data_properties += data_properties_count
                total_named_individuals += named_individuals_count
                total_imports += imports_count
            except Exception:
                # Skip files that fail to load (e.g. missing path)
                continue

        total_items = (
            total_classes
            + total_object_properties
            + total_data_properties
            + total_named_individuals
        )

        return OntologyOverviewAggregateStats(
            name="All ontologies",
            path="*",
            ontologies_count=len(ontology_paths),
            total_items=total_items,
            classes=total_classes,
            object_properties=total_object_properties,
            data_properties=total_data_properties,
            named_individuals=total_named_individuals,
            imports=total_imports,
        )
    except HTTPException:
        raise
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
    """Return ontology dependency graph based on owl:imports relations."""
    from rdflib.query import ResultRow

    try:
        ontologies = await list_ontology_files()
        target_paths = _resolve_target_ontology_paths(ontology_path, ontologies["items"])

        # Single ontology selected: show classes + object properties (+ subclass links)
        if ontology_path:
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

                    data = get_uri_metadata(class_iri)
                    class_label = data.get("label", "Unknown")
                    definition = data.get("definition")
                    parent_iri = data.get("subClassOf")
                    parent_data = get_uri_metadata(parent_iri) if parent_iri else None
                    parent_label = parent_data.get("label", "Unknown") if parent_data else None

                    existing = classes_by_iri.get(class_iri)
                    if existing:
                        if not existing.properties.get("definition") and definition:
                            existing.properties["definition"] = definition
                        if not existing.properties.get("parent_iri") and parent_iri:
                            existing.properties["parent_iri"] = parent_iri
                        if not existing.properties.get("parent_label") and parent_label:
                            existing.properties["parent_label"] = parent_label
                        continue

                    classes_by_iri[class_iri] = OntologyOverviewGraphNode(
                        id=class_iri,
                        label=class_label,
                        type=parent_label,
                        properties={
                            "iri": class_iri,
                            "definition": definition,
                            "parent_iri": parent_iri,
                            "parent_label": parent_label,
                        },
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

                    source_data = get_uri_metadata(source_iri) if source_iri else None
                    source_label = source_data.get("label", "Unknown") if source_data else None
                    source_type = source_data.get("subClassOf") if source_data else None
                    source_type_data = get_uri_metadata(source_type) if source_type else None
                    source_type_label = (
                        source_type_data.get("label", "Unknown") if source_type_data else None
                    )
                    target_data = get_uri_metadata(target_iri) if target_iri else None
                    target_label = target_data.get("label", "Unknown") if target_data else None
                    target_type = target_data.get("subClassOf") if target_data else None
                    target_type_data = get_uri_metadata(target_type) if target_type else None
                    target_type_label = (
                        target_type_data.get("label", "Unknown") if target_type_data else None
                    )

                    if source_iri not in classes_by_iri:
                        classes_by_iri[source_iri] = OntologyOverviewGraphNode(
                            id=source_iri,
                            label=source_label,
                            type=source_type_label,
                            properties={
                                "iri": source_iri,
                                "definition": source_data.get("definition"),
                                "parent_iri": source_type,
                                "parent_label": source_type_label,
                            },
                        )
                    if target_iri not in classes_by_iri:
                        classes_by_iri[target_iri] = OntologyOverviewGraphNode(
                            id=target_iri,
                            label=target_label,
                            type=target_type_label,
                            properties={
                                "iri": target_iri,
                                "definition": target_data.get("definition"),
                                "parent_iri": target_type,
                                "parent_label": target_type_label,
                            },
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

                # for row in graph.query(subclass_query):
                #     assert isinstance(row, ResultRow)
                #     child_class = str(row.get("childClass")) if row.get("childClass") else ""
                #     parent_class = str(row.get("parentClass")) if row.get("parentClass") else ""
                #     if not child_class or not parent_class:
                #         continue

                #     child_data = get_uri_metadata(child_class) if child_class else None
                #     child_label = child_data.get("label", "Unknown") if child_data else None
                #     child_type = child_data.get("subClassOf") if child_data else None
                #     child_type_data = get_uri_metadata(child_type) if child_type else None
                #     child_type_label = (
                #         child_type_data.get("label", "Unknown") if child_type_data else None
                #     )

                #     parent_data = get_uri_metadata(parent_class) if parent_class else None
                #     parent_label = parent_data.get("label", "Unknown") if parent_data else None
                #     parent_type = parent_data.get("subClassOf") if parent_data else None
                #     parent_type_data = get_uri_metadata(parent_type) if parent_type else None
                #     parent_type_label = (
                #         parent_type_data.get("label", "Unknown") if parent_type_data else None
                #     )

                #     if child_class not in classes_by_iri:
                #         classes_by_iri[child_class] = OntologyOverviewGraphNode(
                #             id=child_class,
                #             label=child_label,
                #             type=child_type_label,
                #             properties={
                #                 "iri": child_class,
                #                 "definition": child_data.get("definition"),
                #                 "parent_iri": child_type,
                #                 "parent_label": child_type_label,
                #             },
                #         )
                #     if parent_class not in classes_by_iri:
                #         classes_by_iri[parent_class] = OntologyOverviewGraphNode(
                #             id=parent_class,
                #             label=parent_label,
                #             type=parent_type_label,
                #             properties={
                #                 "iri": parent_class,
                #                 "definition": parent_data.get("definition"),
                #                 "parent_iri": parent_type,
                #                 "parent_label": parent_type_label,
                #             },
                #         )

                #     edge_id = f"{child_class}|is-a|{parent_class}"
                #     if edge_id in edges_by_id:
                #         continue
                #     edges_by_id[edge_id] = OntologyOverviewGraphEdge(
                #         id=edge_id,
                #         source=child_class,
                #         target=parent_class,
                #         type="is a",
                #         label="is a",
                #         properties={
                #             "relation_kind": "subclass_of",
                #             "iri": str(RDFS.subClassOf),
                #             "definition": "Subclass relationship between two classes.",
                #             "parent_property_iri": "",
                #         },
                #     )

            nodes = sorted(classes_by_iri.values(), key=lambda node: node.label.lower())
            edges = sorted(edges_by_id.values(), key=lambda edge: edge.label.lower())
            return OntologyOverviewGraph(nodes=nodes, edges=edges)

        # All ontologies selected: show ontology import dependencies
        ontologies_by_iri: dict[str, OntologyOverviewGraphNode] = {}
        edges_by_id: dict[str, OntologyOverviewGraphEdge] = {}

        ontology_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?ontologyIri ?label ?comment ?versionInfo WHERE {
                ?ontologyIri rdf:type owl:Ontology .
                FILTER(isIRI(?ontologyIri))
                OPTIONAL { ?ontologyIri rdfs:label ?label . }
                OPTIONAL { ?ontologyIri rdfs:comment ?comment . }
                OPTIONAL { ?ontologyIri owl:versionInfo ?versionInfo . }
            }
        """

        imports_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?sourceOntology ?targetOntology WHERE {
                ?sourceOntology rdf:type owl:Ontology .
                ?sourceOntology owl:imports ?targetOntology .
                FILTER(isIRI(?sourceOntology) && isIRI(?targetOntology))
            }
        """

        def _label_from_iri(iri: str) -> str:
            if "#" in iri:
                return iri.rsplit("#", 1)[-1]
            return iri.rstrip("/").rsplit("/", 1)[-1]

        for path in target_paths:
            graph = _load_ontology_graph(path)

            for row in graph.subjects(RDF.type, OWL.Ontology):
                ontology_iri = str(row)
                if not ontology_iri:
                    continue
                if ontologies_by_iri.get(ontology_iri):
                    continue

                ontology_metadata = get_ontology_metadata(ontology_iri)
                ontology_title = ontology_metadata.get("title", "")
                ontology_comment = ontology_metadata.get("comment", "")
                ontology_description = ontology_metadata.get("description", "")
                ontology_version_info = ontology_metadata.get("versionInfo", "")
                ontology_license = ontology_metadata.get("license", "")
                ontology_date = ontology_metadata.get("date", "")

                properties = {
                    "iri": ontology_iri,
                    "source_path": path,
                }
                if ontology_description:
                    properties["description"] = str(ontology_description)
                elif ontology_comment:
                    properties["comment"] = str(ontology_comment)
                if ontology_version_info:
                    properties["version_info"] = str(ontology_version_info)
                if ontology_license:
                    properties["license"] = str(ontology_license)
                if ontology_date:
                    properties["date"] = str(ontology_date)

                ontologies_by_iri[ontology_iri] = OntologyOverviewGraphNode(
                    id=ontology_iri,
                    label=ontology_title,
                    type="Ontology",
                    properties=properties,
                )

            for row in graph.query(imports_query):
                assert isinstance(row, ResultRow)
                source_iri = str(row.get("sourceOntology")) if row.get("sourceOntology") else ""
                target_iri = str(row.get("targetOntology")) if row.get("targetOntology") else ""
                if not source_iri or not target_iri:
                    continue

                if source_iri not in ontologies_by_iri:
                    ontologies_by_iri[source_iri] = OntologyOverviewGraphNode(
                        id=source_iri,
                        label=_label_from_iri(source_iri),
                        type="Imports",
                        properties={
                            "iri": source_iri,
                        },
                    )
                if target_iri not in ontologies_by_iri:
                    ontologies_by_iri[target_iri] = OntologyOverviewGraphNode(
                        id=target_iri,
                        label=_label_from_iri(target_iri),
                        type="Imports",
                        properties={
                            "iri": target_iri,
                        },
                    )

                edge_id = f"{source_iri}|imports|{target_iri}"
                if edge_id in edges_by_id:
                    continue

                edges_by_id[edge_id] = OntologyOverviewGraphEdge(
                    id=edge_id,
                    source=source_iri,
                    target=target_iri,
                    type="imports",
                    label="imports",
                    properties={
                        "relation_kind": "imports",
                        "iri": str(OWL.imports),
                        "definition": "Ontology import dependency.",
                        "parent_property_iri": "",
                    },
                )

        nodes = sorted(ontologies_by_iri.values(), key=lambda node: node.label.lower())
        edges = sorted(edges_by_id.values(), key=lambda edge: edge.label.lower())
        return OntologyOverviewGraph(nodes=nodes, edges=edges)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to compute ontology overview graph: {exc}"
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


@router.get("/ontologies")
async def list_ontology_files() -> dict[str, list[OntologyFileItem]]:
    """
    List ontology files loaded into the platform from all registered modules.
    Deduplicates ontology files across all modules but ensures at least
    one 'naas-abi' (or abi) entry is present for each unique file.
    """

    from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

    ontology_files: list[OntologyFileItem] = []
    seen_ontologies: set[str] = set()

    try:
        abi_module = ABIModule.get_instance()
        abi_ontologies = abi_module.ontologies
        abi_modules_ontologies: list[str] = [
            ontology
            for module in abi_module.engine.modules.values()
            for ontology in module.ontologies
        ]

        abi_ontologies.extend(abi_modules_ontologies)

        for ontology in abi_ontologies:
            if ontology in seen_ontologies:
                continue
            seen_ontologies.add(ontology)

            if "sandbox" in ontology.lower() or "modules" not in ontology.lower():
                continue

            ontology_graph = Graph()
            ontology_graph.parse(ontology, format="turtle")

            # Get metadata
            ontology_uri = next(ontology_graph.subjects(RDF.type, OWL.Ontology), None)
            if ontology_uri is None:
                continue

            # Metadata
            title = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.title)
            description = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.description)
            license = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.license)
            contributors = ontology_graph.objects(URIRef(str(ontology_uri)), DCTERMS.contributor)
            date = ontology_graph.value(URIRef(str(ontology_uri)), DCTERMS.date)
            imports = ontology_graph.objects(URIRef(str(ontology_uri)), OWL.imports)

            # Module name is the folder before "ontologies" in the path
            ontology_parts = ontology.split("/")
            try:
                ontologies_index = ontology_parts.index("ontologies")
                if ontologies_index > 0:
                    module_name = ontology_parts[ontologies_index - 1]
                else:
                    module_name = ""
            except ValueError:
                # "ontologies" not found in path; fallback to first segment or empty
                module_name = ontology_parts[0] if ontology_parts else ""

            ontology_files.append(
                OntologyFileItem(
                    name=str(title),
                    description=str(description),
                    license=str(license),
                    contributors=[str(contributor) for contributor in contributors],
                    date=str(date),
                    path=ontology,
                    module_name=module_name,
                    submodule_name=None,
                    imports=[str(import_) for import_ in imports],
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
