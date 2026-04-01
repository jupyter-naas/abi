"""Knowledge Graph API endpoints backed by ABI TripleStoreService."""

import hashlib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import KnowledgeGraph
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.SPARQL import SPARQLUtils
from pydantic import BaseModel, Field
from rdflib import OWL, RDF, RDFS, Literal, URIRef
from rdflib.query import ResultRow

router = APIRouter(dependencies=[Depends(get_current_user_required)])

GRAPH_BASE_URI = URIRef("http://ontology.naas.ai/graph/")
NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
SCHEMA_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/schema")


class GraphInfo(BaseModel):
    id: str
    uri: str
    label: str


class GraphCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1, max_length=200)


class GraphClear(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str = Field(..., min_length=1, max_length=200)


class GraphDelete(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str = Field(..., min_length=1, max_length=200)


class GraphOverview(BaseModel):
    kpis: dict[str, Any]
    instances_by_class: list[dict[str, Any]]


class GraphNode(BaseModel):
    id: str
    workspace_id: str
    type: str
    label: str
    properties: dict[str, Any] = {}
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
    properties: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ============ Helpers ============


def get_triple_store_service(request: Request) -> TripleStoreService:
    store = getattr(request.app.state, "triple_store", None)
    if store is not None:
        return store

    # Fallback for routes called from an app where ABIModule wired state was skipped.
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        store = module.engine.services.triple_store
        request.app.state.triple_store = store
        return store
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(
            status_code=500,
            detail="Triple store is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def slugify(value: str) -> str:
    """Convert text to a URL-safe slug."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", ascii_value).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


# ============ Endpoints ============


@router.get("/list")
async def list_graphs(
    request: Request,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> list[GraphInfo]:
    """List all graphs available in the triple store and nexus ontology graph."""
    await require_workspace_access(current_user.id, workspace_id)

    # Get triple store service
    store = get_triple_store_service(request)

    # Get graphs from nexus ontology graph
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?uri ?label
    WHERE {{
        GRAPH <{NEXUS_GRAPH_URI}> {{
            ?uri rdf:type <{KnowledgeGraph._class_uri}> .
            OPTIONAL {{ ?uri rdfs:label ?label . }}
        }}
    }}
    """
    rows = store.query(query)
    graphs: list[GraphInfo] = []
    for row in rows:
        assert isinstance(row, ResultRow)
        graph_uri = str(row.uri)
        graph_id = graph_uri.split("/")[-1]
        graph_label = str(row.label) if row.label else graph_id
        graphs.append(GraphInfo(id=graph_id, uri=graph_uri, label=graph_label))
    return graphs


@router.post("/create")
async def create_graph(
    request: Request,
    payload: GraphCreate,
    current_user: User = Depends(get_current_user_required),
) -> GraphInfo:
    """Create a new named graph. Label is required; slug is optional (derived from label)."""

    await require_workspace_access(current_user.id, payload.workspace_id)

    store = get_triple_store_service(request)

    # Create graph URI
    graph_label = payload.label.strip()
    graph_id = slugify(graph_label)
    if payload.description:
        description = slugify(payload.description)
    new_graph_uri = GRAPH_BASE_URI + graph_id
    store.create_graph(new_graph_uri)

    # Add graph to nexus graph
    new_graph = KnowledgeGraph(_uri=new_graph_uri, label=payload.label.strip())
    if payload.description:
        new_graph.description = description
    store.insert(new_graph.rdf(), graph_name=NEXUS_GRAPH_URI)
    return GraphInfo(id=graph_id, uri=str(new_graph_uri), label=graph_label)


@router.post("/clear")
async def clear_graph(
    request: Request,
    payload: GraphClear,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, str]:
    await require_workspace_access(current_user.id, payload.workspace_id)

    graph_uri = GRAPH_BASE_URI + payload.id
    if graph_uri in [SCHEMA_GRAPH_URI, NEXUS_GRAPH_URI]:
        raise HTTPException(status_code=400, detail="Schema or Nexus graph cannot be cleared.")

    get_triple_store_service(request).clear_graph(graph_uri)
    return {"status": "cleared"}


@router.post("/delete")
async def delete_graph(
    request: Request,
    payload: GraphDelete,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, str]:
    await require_workspace_access(current_user.id, payload.workspace_id)

    graph_uri = GRAPH_BASE_URI + payload.id
    if graph_uri in [SCHEMA_GRAPH_URI, NEXUS_GRAPH_URI]:
        raise HTTPException(status_code=400, detail="Schema or Nexus graph cannot be deleted.")

    get_triple_store_service(request).drop_graph(graph_uri)
    return {"status": "deleted"}


def _get_ontology_label(triple_store: TripleStoreService, uri: str) -> str:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label
    WHERE {{
        GRAPH <http://ontology.naas.ai/graph/schema> {{
            <{uri}> rdfs:label ?label .
        }}
    }}
    """
    rows = triple_store.query(query)
    for row in rows:
        assert isinstance(row, ResultRow)
        return str(row.label) if row.label else uri
    return uri


def list_individuals(
    triple_store: TripleStoreService,
    workspace_id: str,
    graph_names: list[str],
    graph_filters: list[dict[str, str | None]],
    limit: int = 500,
    depth: int = 2,
) -> GraphData:
    sparql_utils = SPARQLUtils(triple_store)
    values = " ".join(f"<{graph_name}>" for graph_name in graph_names)
    filter_clauses: list[str] = []
    for filter_item in graph_filters:
        parts: list[str] = []
        subject_uri = filter_item.get("subject_uri")
        predicate_uri = filter_item.get("predicate_uri")
        object_uri = filter_item.get("object_uri")
        if subject_uri:
            parts.append(f"?s = <{subject_uri}>")
        if predicate_uri:
            parts.append(f"?p = <{predicate_uri}>")
        if object_uri:
            parts.append(f"?o = <{object_uri}>")
        if parts:
            filter_clauses.append(f"({' && '.join(parts)})")
    triple_filter_clause = f"FILTER({' || '.join(filter_clauses)})" if filter_clauses else ""

    query = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT DISTINCT ?uri
    WHERE {{
        VALUES ?g {{ {values} }}
        GRAPH ?g {{
            ?s ?p ?o .
            ?s a owl:NamedIndividual ;
            FILTER(?s != owl:NamedIndividual)
            {triple_filter_clause}
            BIND(?s AS ?uri)
        }}
    }}
    """
    rows = triple_store.query(query)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        row_uri = str(row.uri)
        subject_graph = sparql_utils.get_subject_graph(
            row_uri, depth=depth, graph_names=graph_names
        )
        for s, p, o in subject_graph:
            subject_uri = str(s)
            subject_label = (
                subject_graph.value(URIRef(subject_uri), RDFS.label)
                if subject_graph.value(URIRef(subject_uri), RDFS.label)
                else subject_uri
            )
            subject_types = list(subject_graph.objects(URIRef(subject_uri), RDF.type))
            if OWL.NamedIndividual not in subject_types:
                continue
            if o == OWL.NamedIndividual or p == RDFS.label:
                continue
            if subject_uri not in nodes:
                nodes[subject_uri] = {"uri": subject_uri, "label": str(subject_label)}
            if "type" not in nodes[subject_uri]:
                class_type = next(
                    (
                        str(subject_type)
                        for subject_type in subject_types
                        if subject_type not in {OWL.NamedIndividual, OWL.Class}
                    ),
                    None,
                )
                if class_type:
                    nodes[subject_uri]["type"] = class_type
                    nodes[subject_uri]["type_label"] = _get_ontology_label(triple_store, class_type)
            if isinstance(o, Literal):
                nodes[subject_uri][_get_ontology_label(triple_store, str(p))] = str(o)
            elif isinstance(o, URIRef) and p != RDF.type:
                object_uri = str(o)
                edge_id = hashlib.sha256(
                    f"{subject_uri}|{str(p)}|{object_uri}".encode()
                ).hexdigest()
                if edge_id not in edges:
                    object_label = (
                        subject_graph.value(URIRef(object_uri), RDFS.label)
                        if subject_graph.value(URIRef(object_uri), RDFS.label)
                        else object_uri
                    )
                    edges[edge_id] = {
                        "id": edge_id,
                        "label": _get_ontology_label(triple_store, str(p)),
                        "source_id": subject_uri,
                        "source_label": str(subject_label),
                        "target_id": object_uri,
                        "target_label": str(object_label),
                    }
    listed_nodes = list(nodes.values())
    listed_edges = list(edges.values())

    graph_nodes: list[GraphNode] = []
    graph_edges: list[GraphEdge] = []

    for node_data in listed_nodes[: int(limit)]:
        node_id = str(node_data.get("uri", "") or "").strip()
        if not node_id:
            continue
        graph_nodes.append(
            GraphNode(
                id=node_id,
                workspace_id=workspace_id,
                type=str(node_data.get("type_label") or node_data.get("type") or "unknown"),
                label=str(node_data.get("label") or node_id),
                properties={
                    key: value
                    for key, value in node_data.items()
                    if key not in {"uri", "label", "type", "type_label"}
                },
            )
        )

    for edge_data in listed_edges[: int(limit)]:
        source_id = str(edge_data.get("source_id", "") or "").strip()
        target_id = str(edge_data.get("target_id", "") or "").strip()
        if not source_id or not target_id:
            continue
        graph_edges.append(
            GraphEdge(
                id=str(
                    edge_data.get("id") or f"{source_id}|{edge_data.get('label', '')}|{target_id}"
                ),
                workspace_id=workspace_id,
                source_id=source_id,
                target_id=target_id,
                source_label=str(edge_data.get("source_label") or source_id),
                target_label=str(edge_data.get("target_label") or target_id),
                type=str(edge_data.get("label") or "related"),
                properties={},
            )
        )

    return GraphData(nodes=graph_nodes, edges=graph_edges)


def build_graph_overview(
    triple_store: TripleStoreService, graph_uri: URIRef, limit: int = 500
) -> GraphOverview:
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?uri ?label ?type
    WHERE {{
        GRAPH <{str(graph_uri)}> {{
            ?uri a owl:NamedIndividual ;
                 rdfs:label ?label ;
                 rdf:type ?type .
            FILTER(?type != owl:NamedIndividual)
        }}
    }}
    LIMIT {int(limit)}
    """
    rows = triple_store.query(query)
    nodes: list[dict[str, Any]] = []
    class_dict: dict[str, str] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        assert isinstance(row, ResultRow)

        class_uri = str(row.type)
        class_label = class_dict.get(class_uri)
        if not class_label:
            class_label = _get_ontology_label(triple_store, class_uri)
            class_dict[class_uri] = class_label
        type_counts[class_label] = type_counts.get(class_label, 0) + 1

        nodes.append(
            {
                "uri": str(row.uri),
                "label": str(row.label),
                "type": str(row.type),
                "type_label": class_label,
            }
        )

    edges: list[dict[str, Any]] = []

    node_uris = [node["uri"] for node in nodes]
    if node_uris:
        values_clause = " ".join(f"<{uri}>" for uri in node_uris)
        query_edges = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?s ?p ?o
        WHERE {{
            GRAPH <{str(graph_uri)}> {{
                VALUES ?s {{ {values_clause} }}
                ?s ?p ?o .
                FILTER(?p != rdf:type && isIRI(?o))
            }}
        }}
        """
        rows_edges = triple_store.query(query_edges)
        for row_edge in rows_edges:
            assert isinstance(row_edge, ResultRow)
            edges.append(
                {
                    "s": str(row_edge.s),
                    "p": str(row_edge.p),
                    "o": str(row_edge.o),
                }
            )

    kpis = {
        "total_instances": len(nodes),
        "total_relationships": len(edges),
        "average_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
        "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0,
    }
    instances_by_class = [
        {"type": node_type, "count": count}
        for node_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return GraphOverview(
        kpis=kpis,
        instances_by_class=instances_by_class,
    )


@router.get("/{graph_id}/overview")
async def get_graph_overview(
    request: Request,
    graph_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> GraphOverview:
    """Get overview of a given graph."""
    await require_workspace_access(current_user.id, workspace_id)

    store = get_triple_store_service(request)
    graph_uri = GRAPH_BASE_URI + graph_id

    return build_graph_overview(
        triple_store=store,
        graph_uri=graph_uri,
        limit=limit,
    )


@router.get("/{graph_id}/network")
async def get_graph_network(
    request: Request,
    graph_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> GraphData:
    """Get all nodes and edges for a given graph."""
    await require_workspace_access(current_user.id, workspace_id)

    store = get_triple_store_service(request)

    graph_uri = GRAPH_BASE_URI + graph_id

    return list_individuals(
        triple_store=store,
        workspace_id=workspace_id,
        graph_names=[graph_uri],
        graph_filters=[],
        limit=limit,
        depth=2,
    )
