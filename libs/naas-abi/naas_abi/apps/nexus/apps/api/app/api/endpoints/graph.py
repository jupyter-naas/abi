"""Knowledge Graph API endpoints backed by ABI TripleStoreService."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi_core.services.triple_store.TripleStorePorts import Exceptions
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF, RDFS, XSD

router = APIRouter(dependencies=[Depends(get_current_user_required)])

NEXUS = Namespace("urn:nexus:kg:")
NEXUS_NODE = NEXUS.Node
NEXUS_EDGE = NEXUS.Edge
NEXUS_NODE_ID = NEXUS.nodeId
NEXUS_NODE_TYPE = NEXUS.nodeType
NEXUS_EDGE_ID = NEXUS.edgeId
NEXUS_EDGE_TYPE = NEXUS.edgeType
NEXUS_SOURCE_ID = NEXUS.sourceId
NEXUS_TARGET_ID = NEXUS.targetId
NEXUS_WORKSPACE_ID = NEXUS.workspaceId
NEXUS_PROPERTIES = NEXUS.properties
NEXUS_CREATED_AT = NEXUS.createdAt
NEXUS_UPDATED_AT = NEXUS.updatedAt


# ============ Pydantic Schemas ============


class GraphNode(BaseModel):
    id: str
    workspace_id: str
    type: str
    label: str
    properties: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphEdge(BaseModel):
    id: str
    workspace_id: str
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = {}
    created_at: datetime | None = None


class GraphNodeCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=500)
    properties: dict[str, Any] = {}


class GraphNodeUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=500)
    type: str | None = Field(None, min_length=1, max_length=100)
    properties: dict[str, Any] | None = None


class GraphEdgeCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    source_id: str = Field(..., min_length=1, max_length=100)
    target_id: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=100)
    properties: dict[str, Any] = {}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)
    language: Literal["natural", "sparql"] = "natural"
    limit: int = Field(default=100, ge=1, le=5000)


class GraphQueryResult(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    query_explanation: str | None = None


class GraphNamesResponse(BaseModel):
    graph_names: list[str]


# ============ Helpers ============


def get_triple_store(request: Request) -> TripleStoreService:
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


def _as_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _as_properties(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    text = str(value)
    if not text:
        return {}
    try:
        decoded = json.loads(text)
        if isinstance(decoded, dict):
            return decoded
    except json.JSONDecodeError:
        pass
    return {}


def _sparql_str(value: str) -> str:
    return json.dumps(value)


def _node_uri(workspace_id: str, node_id: str) -> URIRef:
    return URIRef(f"urn:nexus:workspace:{workspace_id}:node:{node_id}")


def _edge_uri(workspace_id: str, edge_id: str) -> URIRef:
    return URIRef(f"urn:nexus:workspace:{workspace_id}:edge:{edge_id}")


def _node_graph(node: GraphNode) -> Graph:
    g = Graph()
    subject = _node_uri(node.workspace_id, node.id)
    g.add((subject, RDF.type, NEXUS_NODE))
    g.add((subject, NEXUS_NODE_ID, RDFLiteral(node.id)))
    g.add((subject, NEXUS_WORKSPACE_ID, RDFLiteral(node.workspace_id)))
    g.add((subject, NEXUS_NODE_TYPE, RDFLiteral(node.type)))
    g.add((subject, RDFS.label, RDFLiteral(node.label)))
    g.add((subject, NEXUS_PROPERTIES, RDFLiteral(json.dumps(node.properties or {}))))
    if node.created_at is not None:
        g.add(
            (
                subject,
                NEXUS_CREATED_AT,
                RDFLiteral(_as_utc_naive(node.created_at).isoformat(), datatype=XSD.dateTime),
            )
        )
    if node.updated_at is not None:
        g.add(
            (
                subject,
                NEXUS_UPDATED_AT,
                RDFLiteral(_as_utc_naive(node.updated_at).isoformat(), datatype=XSD.dateTime),
            )
        )
    return g


def _edge_graph(edge: GraphEdge) -> Graph:
    g = Graph()
    subject = _edge_uri(edge.workspace_id, edge.id)
    g.add((subject, RDF.type, NEXUS_EDGE))
    g.add((subject, NEXUS_EDGE_ID, RDFLiteral(edge.id)))
    g.add((subject, NEXUS_WORKSPACE_ID, RDFLiteral(edge.workspace_id)))
    g.add((subject, NEXUS_SOURCE_ID, RDFLiteral(edge.source_id)))
    g.add((subject, NEXUS_TARGET_ID, RDFLiteral(edge.target_id)))
    g.add((subject, NEXUS_EDGE_TYPE, RDFLiteral(edge.type)))
    g.add((subject, NEXUS_PROPERTIES, RDFLiteral(json.dumps(edge.properties or {}))))
    if edge.created_at is not None:
        g.add(
            (
                subject,
                NEXUS_CREATED_AT,
                RDFLiteral(_as_utc_naive(edge.created_at).isoformat(), datatype=XSD.dateTime),
            )
        )
    return g


def _remove_subject_graph(store: TripleStoreService, subject: URIRef) -> bool:
    try:
        subject_graph = store.get_subject_graph(str(subject))
    except Exceptions.SubjectNotFoundError:
        return False
    store.remove(subject_graph)
    return True


def _list_named_graphs(store: TripleStoreService) -> list[str]:
    graph_names = [str(graph_name) for graph_name in store.list_graphs()]
    if len(graph_names) == 0:
        return ["default"]
    return graph_names


def _query_nodes(
    store: TripleStoreService,
    workspace_id: str | None = None,
    node_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    search: str | None = None,
) -> list[GraphNode]:
    where_parts = [
        "?node a <urn:nexus:kg:Node> .",
        "?node <urn:nexus:kg:nodeId> ?id .",
        "?node <urn:nexus:kg:workspaceId> ?workspace_id .",
        "?node <urn:nexus:kg:nodeType> ?type .",
        "?node <http://www.w3.org/2000/01/rdf-schema#label> ?label .",
        "OPTIONAL { ?node <urn:nexus:kg:properties> ?properties . }",
        "OPTIONAL { ?node <urn:nexus:kg:createdAt> ?created_at . }",
        "OPTIONAL { ?node <urn:nexus:kg:updatedAt> ?updated_at . }",
    ]
    filter_parts: list[str] = []
    if workspace_id is not None:
        filter_parts.append(f"?workspace_id = {_sparql_str(workspace_id)}")
    if node_type is not None:
        filter_parts.append(f"?type = {_sparql_str(node_type)}")
    if search:
        q = _sparql_str(search.lower())
        filter_parts.append(
            f"(CONTAINS(LCASE(STR(?label)), {q}) || CONTAINS(LCASE(STR(?type)), {q}))"
        )
    where = "\n".join(where_parts)
    if filter_parts:
        where += f"\nFILTER({' && '.join(filter_parts)})"
    query = f"""
        SELECT ?id ?workspace_id ?type ?label ?properties ?created_at ?updated_at
        WHERE {{
            {where}
        }}
    """
    if limit is not None:
        query += f"\nLIMIT {int(limit)}"
    if offset is not None and offset > 0:
        query += f"\nOFFSET {int(offset)}"

    rows = store.query(query)
    nodes: list[GraphNode] = []
    for row in rows:
        nodes.append(
            GraphNode(
                id=str(row.id),
                workspace_id=str(row.workspace_id),
                type=str(row.type),
                label=str(row.label),
                properties=_as_properties(getattr(row, "properties", None)),
                created_at=_as_datetime(getattr(row, "created_at", None)),
                updated_at=_as_datetime(getattr(row, "updated_at", None)),
            )
        )
    return nodes


def _query_edges(
    store: TripleStoreService,
    workspace_id: str | None = None,
    edge_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    source_or_target_ids: list[str] | None = None,
    source_and_target_ids: list[str] | None = None,
) -> list[GraphEdge]:
    where_parts = [
        "?edge a <urn:nexus:kg:Edge> .",
        "?edge <urn:nexus:kg:edgeId> ?id .",
        "?edge <urn:nexus:kg:workspaceId> ?workspace_id .",
        "?edge <urn:nexus:kg:sourceId> ?source_id .",
        "?edge <urn:nexus:kg:targetId> ?target_id .",
        "?edge <urn:nexus:kg:edgeType> ?type .",
        "OPTIONAL { ?edge <urn:nexus:kg:properties> ?properties . }",
        "OPTIONAL { ?edge <urn:nexus:kg:createdAt> ?created_at . }",
    ]
    filter_parts: list[str] = []
    if workspace_id is not None:
        filter_parts.append(f"?workspace_id = {_sparql_str(workspace_id)}")
    if edge_type is not None:
        filter_parts.append(f"?type = {_sparql_str(edge_type)}")
    if source_or_target_ids is not None:
        if not source_or_target_ids:
            return []
        values = ", ".join(_sparql_str(value) for value in source_or_target_ids)
        filter_parts.append(f"(?source_id IN ({values}) || ?target_id IN ({values}))")
    if source_and_target_ids is not None:
        if not source_and_target_ids:
            return []
        values = ", ".join(_sparql_str(value) for value in source_and_target_ids)
        filter_parts.append(f"(?source_id IN ({values}) && ?target_id IN ({values}))")
    where = "\n".join(where_parts)
    if filter_parts:
        where += f"\nFILTER({' && '.join(filter_parts)})"

    query = f"""
        SELECT ?id ?workspace_id ?source_id ?target_id ?type ?properties ?created_at
        WHERE {{
            {where}
        }}
    """
    if limit is not None:
        query += f"\nLIMIT {int(limit)}"
    if offset is not None and offset > 0:
        query += f"\nOFFSET {int(offset)}"

    rows = store.query(query)
    edges: list[GraphEdge] = []
    for row in rows:
        edges.append(
            GraphEdge(
                id=str(row.id),
                workspace_id=str(row.workspace_id),
                source_id=str(row.source_id),
                target_id=str(row.target_id),
                type=str(row.type),
                properties=_as_properties(getattr(row, "properties", None)),
                created_at=_as_datetime(getattr(row, "created_at", None)),
            )
        )
    return edges


def _get_node_by_id(store: TripleStoreService, node_id: str) -> GraphNode | None:
    rows = store.query(f"""
        SELECT ?id ?workspace_id ?type ?label ?properties ?created_at ?updated_at
        WHERE {{
            ?node a <urn:nexus:kg:Node> ;
                  <urn:nexus:kg:nodeId> ?id ;
                  <urn:nexus:kg:workspaceId> ?workspace_id ;
                  <urn:nexus:kg:nodeType> ?type ;
                  <http://www.w3.org/2000/01/rdf-schema#label> ?label .
            OPTIONAL {{ ?node <urn:nexus:kg:properties> ?properties . }}
            OPTIONAL {{ ?node <urn:nexus:kg:createdAt> ?created_at . }}
            OPTIONAL {{ ?node <urn:nexus:kg:updatedAt> ?updated_at . }}
            FILTER(?id = {_sparql_str(node_id)})
        }}
        LIMIT 1
    """)
    for row in rows:
        return GraphNode(
            id=str(row.id),
            workspace_id=str(row.workspace_id),
            type=str(row.type),
            label=str(row.label),
            properties=_as_properties(getattr(row, "properties", None)),
            created_at=_as_datetime(getattr(row, "created_at", None)),
            updated_at=_as_datetime(getattr(row, "updated_at", None)),
        )
    return None


def _get_edge_by_id(store: TripleStoreService, edge_id: str) -> GraphEdge | None:
    rows = store.query(f"""
        SELECT ?id ?workspace_id ?source_id ?target_id ?type ?properties ?created_at
        WHERE {{
            ?edge a <urn:nexus:kg:Edge> ;
                  <urn:nexus:kg:edgeId> ?id ;
                  <urn:nexus:kg:workspaceId> ?workspace_id ;
                  <urn:nexus:kg:sourceId> ?source_id ;
                  <urn:nexus:kg:targetId> ?target_id ;
                  <urn:nexus:kg:edgeType> ?type .
            OPTIONAL {{ ?edge <urn:nexus:kg:properties> ?properties . }}
            OPTIONAL {{ ?edge <urn:nexus:kg:createdAt> ?created_at . }}
            FILTER(?id = {_sparql_str(edge_id)})
        }}
        LIMIT 1
    """)
    for row in rows:
        return GraphEdge(
            id=str(row.id),
            workspace_id=str(row.workspace_id),
            source_id=str(row.source_id),
            target_id=str(row.target_id),
            type=str(row.type),
            properties=_as_properties(getattr(row, "properties", None)),
            created_at=_as_datetime(getattr(row, "created_at", None)),
        )
    return None


# ============ Endpoints ============


@router.get("/names")
async def list_graph_names(
    request: Request,
) -> GraphNamesResponse:
    """List all named graphs available in the triple store."""
    store = get_triple_store(request)
    return GraphNamesResponse(graph_names=_list_named_graphs(store))


@router.get("/workspaces/{workspace_id}")
async def get_workspace_graph(
    request: Request,
    workspace_id: str,
    node_type: str | None = None,
    limit: int = Query(default=1000, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> GraphData:
    """Get all nodes and edges for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store(request)
    nodes = await list_nodes(request, workspace_id, node_type, limit, 0, current_user)

    node_ids = [n.id for n in nodes]
    edges = _query_edges(
        store=store,
        workspace_id=workspace_id,
        source_or_target_ids=node_ids,
    )

    return GraphData(nodes=nodes, edges=edges)


@router.get("/nodes")
async def list_nodes(
    request: Request,
    workspace_id: str,
    type: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
) -> list[GraphNode]:
    """List nodes, optionally filtered by type."""
    await require_workspace_access(current_user.id, workspace_id)
    from naas_abi import ABIModule
    from rdflib.query import ResultRow

    triple_store_service = ABIModule.get_instance().engine.services.triple_store

    # Query for all Named Individuals (Nodes) along with their type, type label, and human label
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?uri ?label ?type ?type_label
    WHERE {{
        ?uri a owl:NamedIndividual ;
             rdfs:label ?label ;
             rdf:type ?type .
        OPTIONAL {{ ?type rdfs:label ?type_label . }}
        FILTER(?type != owl:NamedIndividual)
    }}
    LIMIT {int(limit)}
    OFFSET {int(offset)}
    """

    rows = triple_store_service.query(query)
    nodes: list[GraphNode] = []
    for row in rows:
        assert isinstance(row, ResultRow)
        uri = str(row.uri)
        label = str(row.label)
        type_label = str(row.type_label)
        nodes.append(
            GraphNode(
                id=uri,
                workspace_id=workspace_id,
                type=type_label,
                label=label,
                properties=None,
                created_at=None,
                updated_at=None,
            )
        )
    return nodes


@router.post("/nodes")
async def create_node(
    request: Request,
    node: GraphNodeCreate,
    current_user: User = Depends(get_current_user_required),
) -> GraphNode:
    """Create a new node."""
    await require_workspace_access(current_user.id, node.workspace_id)
    store = get_triple_store(request)
    node_id = f"node-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).replace(tzinfo=None)
    created = GraphNode(
        id=node_id,
        workspace_id=node.workspace_id,
        type=node.type,
        label=node.label,
        properties=node.properties,
        created_at=now,
        updated_at=now,
    )
    store.insert(_node_graph(created))
    return created


@router.get("/nodes/{node_id}")
async def get_node(
    request: Request,
    node_id: str,
) -> GraphNode:
    """Get a node by ID."""
    store = get_triple_store(request)
    node = _get_node_by_id(store, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.put("/nodes/{node_id}")
async def update_node(
    request: Request,
    node_id: str,
    updates: GraphNodeUpdate,
) -> GraphNode:
    """Update a node."""
    store = get_triple_store(request)
    existing = _get_node_by_id(store, node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Node not found")

    now = datetime.now(UTC).replace(tzinfo=None)
    updated = GraphNode(
        id=existing.id,
        workspace_id=existing.workspace_id,
        label=updates.label if updates.label is not None else existing.label,
        type=updates.type if updates.type is not None else existing.type,
        properties=updates.properties if updates.properties is not None else existing.properties,
        created_at=existing.created_at,
        updated_at=now,
    )
    _remove_subject_graph(store, _node_uri(existing.workspace_id, existing.id))
    store.insert(_node_graph(updated))
    return updated


@router.delete("/nodes/{node_id}")
async def delete_node(
    request: Request,
    node_id: str,
) -> dict[str, Any]:
    """Delete a node and its connected edges."""
    store = get_triple_store(request)
    node = _get_node_by_id(store, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    connected_edges = store.query(f"""
        SELECT ?id ?workspace_id
        WHERE {{
            ?edge a <urn:nexus:kg:Edge> ;
                  <urn:nexus:kg:edgeId> ?id ;
                  <urn:nexus:kg:workspaceId> ?workspace_id ;
                  <urn:nexus:kg:sourceId> ?source_id ;
                  <urn:nexus:kg:targetId> ?target_id .
            FILTER(?source_id = {_sparql_str(node_id)} || ?target_id = {_sparql_str(node_id)})
        }}
    """)
    edge_count = 0
    for edge_row in connected_edges:
        if _remove_subject_graph(store, _edge_uri(str(edge_row.workspace_id), str(edge_row.id))):
            edge_count += 1
    _remove_subject_graph(store, _node_uri(node.workspace_id, node.id))
    return {"status": "deleted", "edges_deleted": edge_count}


@router.get("/edges")
async def list_edges(
    request: Request,
    workspace_id: str,
    type: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
) -> list[GraphEdge]:
    """List edges, optionally filtered by type."""
    await require_workspace_access(current_user.id, workspace_id)
    from naas_abi import ABIModule
    from rdflib.query import ResultRow

    triple_store_service = ABIModule.get_instance().engine.services.triple_store

    relation_filter = ""
    if type:
        relation_filter = (
            f"FILTER(LCASE(STR(COALESCE(?predicate_label, ?predicate))) = LCASE({_sparql_str(type)}))"
        )

    # Query object-property triples linking Named Individuals.
    # Keep only URIRefs (subject/predicate/object) to exclude blank nodes.
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT DISTINCT ?source ?target ?predicate ?predicate_label
    WHERE {{
        ?source a owl:NamedIndividual .
        ?target a owl:NamedIndividual .
        ?source ?predicate ?target .
        OPTIONAL {{ ?predicate rdfs:label ?predicate_label . }}
        FILTER(isIRI(?source) && isIRI(?predicate) && isIRI(?target))
        {relation_filter}
    }}
    LIMIT {int(limit)}
    OFFSET {int(offset)}
    """

    rows = triple_store_service.query(query)
    edges: list[GraphEdge] = []
    for row in rows:
        assert isinstance(row, ResultRow)
        source = str(row.source)
        target = str(row.target)
        predicate = str(row.predicate)
        predicate_label = str(row.predicate_label) if row.predicate_label else predicate
        edge_id = f"{source}|{predicate}|{target}"
        edges.append(
            GraphEdge(
                id=edge_id,
                workspace_id=workspace_id,
                source_id=source,
                target_id=target,
                type=predicate_label,
                properties={"predicate_iri": predicate},
                created_at=None,
            )
        )
    return edges


@router.post("/edges")
async def create_edge(
    request: Request,
    edge: GraphEdgeCreate,
    current_user: User = Depends(get_current_user_required),
) -> GraphEdge:
    """Create a new edge between nodes."""
    await require_workspace_access(current_user.id, edge.workspace_id)
    store = get_triple_store(request)

    # Verify source and target exist
    for nid, label in [(edge.source_id, "Source"), (edge.target_id, "Target")]:
        if _get_node_by_id(store, nid) is None:
            raise HTTPException(status_code=404, detail=f"{label} node not found")

    edge_id = f"edge-{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).replace(tzinfo=None)
    created = GraphEdge(
        id=edge_id,
        workspace_id=edge.workspace_id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        type=edge.type,
        properties=edge.properties,
        created_at=now,
    )
    store.insert(_edge_graph(created))
    return created


@router.get("/edges/{edge_id}")
async def get_edge(
    request: Request,
    edge_id: str,
) -> GraphEdge:
    """Get an edge by ID."""
    store = get_triple_store(request)
    edge = _get_edge_by_id(store, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    return edge


@router.delete("/edges/{edge_id}")
async def delete_edge(
    request: Request,
    edge_id: str,
) -> dict[str, str]:
    """Delete an edge."""
    store = get_triple_store(request)
    edge = _get_edge_by_id(store, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    _remove_subject_graph(store, _edge_uri(edge.workspace_id, edge.id))
    return {"status": "deleted"}


@router.post("/query")
async def query_graph(
    http_request: Request,
    payload: GraphQuery,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> GraphQueryResult:
    """Query the knowledge graph."""
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store(http_request)
    nodes = _query_nodes(
        store=store,
        workspace_id=workspace_id,
        limit=payload.limit,
        search=payload.query,
    )

    node_ids = [n.id for n in nodes]
    edges = _query_edges(
        store=store,
        workspace_id=workspace_id,
        source_and_target_ids=node_ids,
    )

    return GraphQueryResult(
        nodes=nodes,
        edges=edges,
        query_explanation=f"Found {len(nodes)} nodes matching '{payload.query}'",
    )


@router.get("/statistics/{workspace_id}")
async def get_graph_statistics(
    request: Request,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Get statistics for a workspace's graph."""
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store(request)

    total_nodes = 0
    for row in store.query(f"""
        SELECT (COUNT(?node) AS ?count)
        WHERE {{
            ?node a <urn:nexus:kg:Node> ;
                  <urn:nexus:kg:workspaceId> ?workspace_id .
            FILTER(?workspace_id = {_sparql_str(workspace_id)})
        }}
    """):
        total_nodes = int(str(row.count))

    total_edges = 0
    for row in store.query(f"""
        SELECT (COUNT(?edge) AS ?count)
        WHERE {{
            ?edge a <urn:nexus:kg:Edge> ;
                  <urn:nexus:kg:workspaceId> ?workspace_id .
            FILTER(?workspace_id = {_sparql_str(workspace_id)})
        }}
    """):
        total_edges = int(str(row.count))

    nodes_by_type: dict[str, int] = {}
    for row in store.query(f"""
        SELECT ?type (COUNT(?node) AS ?count)
        WHERE {{
            ?node a <urn:nexus:kg:Node> ;
                  <urn:nexus:kg:workspaceId> ?workspace_id ;
                  <urn:nexus:kg:nodeType> ?type .
            FILTER(?workspace_id = {_sparql_str(workspace_id)})
        }}
        GROUP BY ?type
    """):
        nodes_by_type[str(row.type)] = int(str(row.count))

    edges_by_type: dict[str, int] = {}
    for row in store.query(f"""
        SELECT ?type (COUNT(?edge) AS ?count)
        WHERE {{
            ?edge a <urn:nexus:kg:Edge> ;
                  <urn:nexus:kg:workspaceId> ?workspace_id ;
                  <urn:nexus:kg:edgeType> ?type .
            FILTER(?workspace_id = {_sparql_str(workspace_id)})
        }}
        GROUP BY ?type
    """):
        edges_by_type[str(row.type)] = int(str(row.count))

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "nodes_by_type": nodes_by_type,
        "edges_by_type": edges_by_type,
        "avg_degree": (2 * total_edges / total_nodes) if total_nodes > 0 else 0,
    }
