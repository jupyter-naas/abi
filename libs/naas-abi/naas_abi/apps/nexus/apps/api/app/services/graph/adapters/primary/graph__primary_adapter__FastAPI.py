"""Graph FastAPI primary adapter."""

from __future__ import annotations

import datetime
import io
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (  # noqa: E501
    get_graph_service,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__schemas import (  # noqa: E501
    AddDataPropertyRequest,
    AddObjectPropertyRequest,
    DeleteDataPropertyRequest,
    DeleteObjectPropertyRequest,
    DiscoveryClass,
    DiscoveryClassMeta,
    DiscoveryClassObjectProperty,
    DiscoveryDataPropertyItem,
    DiscoveryInspectorRelationItem,
    DiscoveryInstance,
    DiscoveryInstanceDetail,
    DiscoveryInstanceDetailRequest,
    DiscoveryInstancesRequest,
    DiscoveryPropertiesRequest,
    DiscoveryProperty,
    DiscoveryRangeOption,
    DiscoveryRelationRow,
    DiscoveryRelationsRequest,
    DiscoveryRelationTarget,
    DiscoveryRelationTargetsRequest,
    DiscoveryRelationType,
    DiscoveryRelationTypesRequest,
    DiscoveryTriplesExportRequest,
    DiscoveryTriplesExportResponse,
    GraphAnalysis,
    GraphClear,
    GraphCreate,
    GraphData,
    GraphDelete,
    GraphDetail,
    GraphEdge,
    GraphInfo,
    GraphKpis,
    GraphNode,
    GraphOverview,
    GraphPack,
    GraphUpdate,
    IndividualCreate,
    IndividualDelete,
    NetworkNodeInstancesRequest,
    NetworkNodePropertiesRequest,
    NetworkSchema,
    NetworkSchemaEdge,
    NetworkSchemaNode,
    UpdateDataPropertyRequest,
    UpdateObjectPropertyRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.discovery_triples_export import (
    serialize_discovery_triples,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphProtectedError,
    GraphQuerySpecError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.primary.graph_query__primary_adapter__schemas import (  # noqa: E501
    GraphColumnsResponse,
    GraphFacetsRequest,
    GraphFacetsResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphSearchResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (  # noqa: E501
    GraphQueryTripleStoreAdapter,
    resolve_fts_backend,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.service import (
    CountCache,
    GraphQueryService,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.service import (
    NEXUS_GRAPH_URI,
    SCHEMA_GRAPH_URI,
    GraphService,
    _detect_rdf_format,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import CacheExpiredError, CacheNotFoundError
from naas_abi_core.services.cache.CacheService import CacheService

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# Shared FS-backed cache for Composer query results (page rows + count). The FS tier is shared
# across API workers and survives restarts; a TTL bounds staleness and the Composer's "always
# refresh" tick (`force_refresh`) bypasses it. TTL is env-overridable.
_QUERY_CACHE = CacheFactory.CacheFS_find_storage(subpath="nexus/graph-query")
_QUERY_CACHE_TTL = datetime.timedelta(
    seconds=int(os.environ.get("NEXUS_QUERY_CACHE_TTL_SECONDS", "300"))
)


class _QueryResultCache(CountCache):
    """Adapts the naas-abi-core CacheService (get/set_json, TTL checked at read) to the query
    service's ``fetch``/``store`` cache port. A cache failure must never break a query."""

    def __init__(self, cache: CacheService, ttl: datetime.timedelta) -> None:
        self._cache = cache
        self._ttl = ttl

    def fetch(self, key: str) -> dict | None:
        try:
            return self._cache.get(key, ttl=self._ttl)
        except (CacheNotFoundError, CacheExpiredError):
            return None
        except Exception:  # noqa: BLE001 - cache is best-effort, degrade to a live query
            return None

    def store(self, key: str, value: dict) -> None:
        try:
            self._cache.set_json(key, value)
        except Exception:  # noqa: BLE001
            pass


class GraphFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


# ── Converters ────────────────────────────────────────────────────────────────


def _node_to_schema(node) -> GraphNode:
    return GraphNode(
        id=node.id,
        workspace_id=node.workspace_id,
        type=node.type,
        label=node.label,
        properties=node.properties,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _edge_to_schema(edge) -> GraphEdge:
    return GraphEdge(
        id=edge.id,
        workspace_id=edge.workspace_id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        source_label=edge.source_label,
        target_label=edge.target_label,
        type=edge.type,
        properties=edge.properties,
        created_at=edge.created_at,
        updated_at=edge.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/list")
async def list_graphs(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[GraphPack]:
    """List all graphs available in the triple store and nexus ontology graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        graphs = await graph_service.list_graphs(workspace_id=workspace_id)
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        GraphPack(
            role_label=pack.role_label,
            graphs=[
                GraphInfo(id=g.id, uri=g.uri, label=g.label, role_label=g.role_label)
                for g in pack.graphs
            ],
        )
        for pack in graphs
    ]


@router.get("/roles")
async def list_graph_roles(
    workspace_id: str = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[str]:
    """List distinct knowledge graph role labels used in the workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        roles = await graph_service.list_graph_roles(workspace_id=workspace_id)
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return roles


@router.post("/create")
async def create_graph(
    payload: GraphCreate,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphInfo:
    """Create a new named graph. Label is required; slug is derived from label."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        graph = await graph_service.create_graph(
            workspace_id=payload.workspace_id,
            label=payload.label,
            description=payload.description,
            user_id=current_user.id,
            role_label=payload.role_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphInfo(
        id=graph.id,
        uri=graph.uri,
        label=graph.label,
        role_label=graph.role_label,
    )


@router.get("/detail")
async def get_graph_detail(
    workspace_id: str = Query(..., description="Workspace ID"),
    uri: str = Query(..., description="Graph URI"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphDetail:
    """Full metadata for one graph (label, description, role) — used to pre-fill the edit form."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        graph = await graph_service.get_graph(workspace_id=workspace_id, graph_uri=uri)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphDetail(
        id=graph.id,
        uri=graph.uri,
        label=graph.label,
        description=graph.description,
        role_label=graph.role_label,
    )


@router.post("/update")
async def update_graph(
    payload: GraphUpdate,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphDetail:
    """Update a graph's label, description and role in place (URI/id is preserved)."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        graph = await graph_service.update_graph(
            workspace_id=payload.workspace_id,
            graph_uri=payload.uri,
            label=payload.label,
            description=payload.description,
            role_label=payload.role_label,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphDetail(
        id=graph.id,
        uri=graph.uri,
        label=graph.label,
        description=graph.description,
        role_label=graph.role_label,
    )


@router.post("/clear")
async def clear_graph(
    payload: GraphClear,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.clear_graph(workspace_id=payload.workspace_id, graph_uri=payload.uri)
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "cleared"}


@router.post("/cache/clear")
async def clear_graph_cache(
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, bool]:
    """Clear all filesystem graph caches (KPIs, network schema, BFO buckets, …).

    Forces the next request to rebuild from the triple store. Safe to call at any
    time; triggered by the sidebar Refresh button.
    """
    await graph_service.clear_cache()
    return {"success": True}


@router.post("/delete")
async def delete_graph(
    payload: GraphDelete,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.delete_graph(workspace_id=payload.workspace_id, graph_uri=payload.uri)
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/nodes")
async def create_individual(
    payload: IndividualCreate,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphNode:
    """Insert a new individual into the given named graph."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        node = await graph_service.create_individual(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            label=payload.label,
            class_uri=payload.class_uri,
            properties=payload.properties,
            relations=[(r.predicate_uri, r.other_uri) for r in payload.relations],
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _node_to_schema(node)


@router.post("/nodes/delete")
async def delete_individual(
    payload: IndividualDelete,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Delete an individual: remove every triple where it is subject or object in the graph."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.delete_individual(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/nodes/data-property/add")
async def add_data_property(
    payload: AddDataPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Insert a single data property triple on an individual."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.add_data_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            predicate_uri=payload.predicate_uri,
            value=payload.value,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "added"}


@router.post("/nodes/data-property/delete")
async def delete_data_property(
    payload: DeleteDataPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Delete a single data property triple from an individual."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.delete_data_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            predicate_uri=payload.predicate_uri,
            value=payload.value,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/nodes/data-property/update")
async def update_data_property(
    payload: UpdateDataPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Replace a data property value for an individual (delete old triple, insert new)."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.update_data_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            predicate_uri=payload.predicate_uri,
            old_value=payload.old_value,
            new_value=payload.new_value,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "updated"}


@router.post("/nodes/object-property/add")
async def add_object_property(
    payload: AddObjectPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Insert a single object property triple on an individual."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.add_object_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            predicate_uri=payload.predicate_uri,
            other_uri=payload.other_uri,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "added"}


@router.post("/nodes/object-property/delete")
async def delete_object_property(
    payload: DeleteObjectPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Delete a single object property triple from an individual."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.delete_object_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            predicate_uri=payload.predicate_uri,
            other_uri=payload.other_uri,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/nodes/object-property/update")
async def update_object_property(
    payload: UpdateObjectPropertyRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Replace an object property triple for an individual (delete old triple, insert new)."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        await graph_service.update_object_property(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            individual_uri=payload.individual_uri,
            old_predicate_uri=payload.old_predicate_uri,
            old_other_uri=payload.old_other_uri,
            new_predicate_uri=payload.new_predicate_uri,
            new_other_uri=payload.new_other_uri,
        )
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "updated"}


@router.get("/overview")
async def get_graph_overview(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI (URL-encoded)"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphOverview:
    """Get overview of a given graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        overview = await graph_service.get_graph_overview(
            workspace_id=workspace_id, graph_uri=graph_uri, limit=limit
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphOverview(
        kpis=overview.kpis,
        instances_by_class=overview.instances_by_class,
    )


@router.get("/kpis")
async def get_graph_kpis(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI (URL-encoded)"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphKpis:
    """Return Individuals / Relations / Properties KPI counts for a graph (cached 5 min)."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        kpis = await graph_service.get_graph_kpis(workspace_id=workspace_id, graph_uri=graph_uri)
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphKpis(
        individuals=kpis.individuals,
        relations=kpis.relations,
        properties=kpis.properties,
        classes=kpis.classes,
    )


@router.get("/network/schema")
async def get_network_schema(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI (URL-encoded)"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> NetworkSchema:
    """Return class-level nodes and edges for the network schema view (cached 5 min)."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        schema = await graph_service.get_network_schema(
            workspace_id=workspace_id, graph_uri=graph_uri
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return NetworkSchema(
        nodes=[
            NetworkSchemaNode(
                class_uri=n.class_uri,
                class_label=n.class_label,
                count=n.count,
                bfo_parent_iri=n.bfo_parent_iri,
            )
            for n in schema.nodes
        ],
        edges=[
            NetworkSchemaEdge(
                source_class_uri=e.source_class_uri,
                target_class_uri=e.target_class_uri,
                relation_uri=e.relation_uri,
                relation_label=e.relation_label,
                count=e.count,
            )
            for e in schema.edges
        ],
    )


@router.get("/network")
async def get_graph_network(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI (URL-encoded)"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphData:
    """Get all nodes and edges for a given graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        network = await graph_service.get_graph_network(
            workspace_id=workspace_id, graph_uri=graph_uri, limit=limit
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphData(
        nodes=[_node_to_schema(n) for n in network.nodes],
        edges=[_edge_to_schema(e) for e in network.edges],
    )


@router.get("/network/search")
async def search_graph_network(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI (URL-encoded)"),
    query: str = Query(..., min_length=1, description="Search term matched against node labels"),
    limit: int = Query(default=200, le=2000),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphData:
    """Search nodes by label within a graph. Returns matching individuals and their edges."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        result = await graph_service.search_network(
            workspace_id=workspace_id,
            graph_uri=graph_uri,
            search_query=query,
            limit=limit,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphData(
        nodes=[_node_to_schema(n) for n in result.nodes],
        edges=[_edge_to_schema(e) for e in result.edges],
    )


_EXPORT_FORMAT_META: dict[str, tuple[str, str, str]] = {
    "ttl": ("turtle", "text/turtle", ".ttl"),
    "owl": ("xml", "application/rdf+xml", ".owl"),
    "nt": ("nt", "application/n-triples", ".nt"),
}


@router.get("/export")
async def export_graph(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI to export"),
    format: str = Query("ttl", description="Serialization format: ttl, owl, nt"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> StreamingResponse:
    """Export all triples from a named graph.

    Fetches triples in batches of 10 000 and loops until the graph is fully
    exhausted, then returns the serialized document in the requested format.
    Supported formats: ttl (Turtle), owl (RDF/XML), nt (N-Triples).
    """
    await require_workspace_access(current_user.id, workspace_id)
    rdflib_format, media_type, ext = _EXPORT_FORMAT_META.get(format, _EXPORT_FORMAT_META["ttl"])
    try:
        content, triple_count, named_individual_count = await graph_service.export_graph_as_ttl(
            workspace_id=workspace_id,
            graph_uri=graph_uri,
            format=rdflib_format,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    graph_name = graph_uri.rstrip("/").split("/")[-1] or "graph"
    filename = f"{graph_name}{ext}"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Triple-Count": str(triple_count),
            "X-Named-Individual-Count": str(named_individual_count),
            "Access-Control-Expose-Headers": "X-Triple-Count, X-Named-Individual-Count, Content-Disposition",
        },
    )


@router.post("/analyze")
async def analyze_graph_file(
    workspace_id: str = Form(..., description="Workspace ID"),
    file: UploadFile = File(..., description="RDF file to analyse (.ttl, .owl, .rdf, .nt, .n3)"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphAnalysis:
    """Parse an uploaded RDF file and return triple counts broken down by OWL type category.

    No data is persisted. The file is analysed in-memory only.
    """
    await require_workspace_access(current_user.id, workspace_id)
    content = await file.read()
    fmt = _detect_rdf_format(file.filename or "")
    try:
        analysis = await graph_service.analyze_graph_file(content=content, fmt=fmt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc
    return GraphAnalysis(
        total_triples=analysis.total_triples,
        total_subjects=analysis.total_subjects,
        named_individuals_subjects=analysis.named_individuals_subjects,
        named_individuals_triples=analysis.named_individuals_triples,
        classes_subjects=analysis.classes_subjects,
        classes_triples=analysis.classes_triples,
        object_properties_subjects=analysis.object_properties_subjects,
        object_properties_triples=analysis.object_properties_triples,
        datatype_properties_subjects=analysis.datatype_properties_subjects,
        datatype_properties_triples=analysis.datatype_properties_triples,
        restrictions_subjects=analysis.restrictions_subjects,
        restrictions_triples=analysis.restrictions_triples,
        unknown_subjects=analysis.unknown_subjects,
        unknown_triples=analysis.unknown_triples,
    )


@router.post("/import")
async def import_graph_file(
    workspace_id: str = Form(..., description="Workspace ID"),
    graph_uri: str = Form(..., description="Target named graph URI"),
    file: UploadFile = File(..., description="RDF file to import (.ttl, .owl, .rdf, .nt, .n3)"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, object]:
    """Import OWL NamedIndividual triples from an uploaded RDF file into *graph_uri*.

    Only triples whose subject is declared as ``owl:NamedIndividual`` are inserted.
    Returns ``{"status": "imported", "count": N}`` where N is the number of triples inserted.
    """
    await require_workspace_access(current_user.id, workspace_id)
    content = await file.read()
    fmt = _detect_rdf_format(file.filename or "")
    try:
        count = await graph_service.import_individuals_to_graph(
            workspace_id=workspace_id,
            content=content,
            fmt=fmt,
            graph_uri=graph_uri,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to import file: {exc}") from exc
    return {"status": "imported", "count": count}


# ── Discovery endpoints ──────────────────────────────────────────────────────


@router.get("/discovery/classes")
async def discovery_classes(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryClass]:
    """List RDF classes that have NamedIndividuals in the given graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        classes = await graph_service.discover_classes(
            workspace_id=workspace_id, graph_uri=graph_uri
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryClass(uri=c.uri, label=c.label, count=c.count) for c in classes]


@router.get("/discovery/classes/all")
async def discovery_classes_all(
    workspace_id: str = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryClass]:
    """List RDF classes aggregated across all workspace graphs."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        classes = await graph_service.discover_all_classes(workspace_id=workspace_id)
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryClass(uri=c.uri, label=c.label, count=c.count) for c in classes]


@router.get("/discovery/class-meta")
async def discovery_class_meta(
    workspace_id: str = Query(..., description="Workspace ID"),
    class_uri: str = Query(..., description="Class URI"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> DiscoveryClassMeta:
    """Return class label and BFO bucket metadata for a class IRI."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        meta = await graph_service.discover_class_meta(
            workspace_id=workspace_id, class_uri=class_uri
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DiscoveryClassMeta(
        class_uri=meta.class_uri,
        class_label=meta.class_label,
        bfo_parent_iri=meta.bfo_parent_iri,
        bfo_parent_label=meta.bfo_parent_label,
    )


@router.get("/discovery/class-datatype-properties")
async def discovery_class_datatype_properties(
    workspace_id: str = Query(..., description="Workspace ID"),
    class_uri: str = Query(..., description="Class URI"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryProperty]:
    """List datatype/annotation properties allowed for instances of a class."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        properties = await graph_service.discover_class_datatype_properties(
            workspace_id=workspace_id, class_uri=class_uri
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryProperty(uri=p.uri, label=p.label, kind=p.kind) for p in properties]


@router.get("/discovery/class-object-properties")
async def discovery_class_object_properties(
    workspace_id: str = Query(..., description="Workspace ID"),
    class_uri: str = Query(..., description="Class URI"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryClassObjectProperty]:
    """List object properties allowed for a class with schema-derived range options."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        properties = await graph_service.discover_class_object_properties(
            workspace_id=workspace_id, class_uri=class_uri
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        DiscoveryClassObjectProperty(
            uri=p.uri,
            label=p.label,
            range_options=[
                DiscoveryRangeOption(uri=r.uri, label=r.label, kind=r.kind) for r in p.range_options
            ],
        )
        for p in properties
    ]


@router.post("/discovery/relation-targets")
async def discovery_relation_targets(
    payload: DiscoveryRelationTargetsRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryRelationTarget]:
    """List individuals that can be used as object-property range values."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        targets = await graph_service.discover_relation_targets(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            range_class_uris=payload.range_class_uris,
            individual_uris=payload.individual_uris,
            search=payload.search,
            limit=payload.limit,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        DiscoveryRelationTarget(
            uri=t.uri,
            label=t.label,
            class_uri=t.class_uri,
            class_label=t.class_label,
        )
        for t in targets
    ]


@router.post("/discovery/properties")
async def discovery_properties(
    payload: DiscoveryPropertiesRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryProperty]:
    """List datatype/annotation properties used by instances of the given classes."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        properties = await graph_service.discover_properties(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            class_uris=payload.class_uris,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryProperty(uri=p.uri, label=p.label, kind=p.kind) for p in properties]


@router.post("/discovery/instances")
async def discovery_instances(
    payload: DiscoveryInstancesRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryInstance]:
    """Search instances matching selected classes / properties / global search query."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        instances = await graph_service.discover_instances(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            class_uris=payload.class_uris,
            property_uris=payload.property_uris,
            search=payload.search,
            limit=payload.limit,
            offset=payload.offset,
            enrich=payload.enrich,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        DiscoveryInstance(
            uri=i.uri,
            label=i.label,
            class_uri=i.class_uri,
            class_label=i.class_label,
            properties=i.properties,
            object_properties=i.object_properties,
            domain_relations_count=i.domain_relations_count,
            range_relations_count=i.range_relations_count,
            properties_count=i.properties_count,
            bfo_bucket_uri=i.bfo_bucket_uri,
            bfo_bucket_label=i.bfo_bucket_label,
        )
        for i in instances
    ]


@router.post("/discovery/instance-detail")
async def discovery_instance_detail(
    payload: DiscoveryInstanceDetailRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> DiscoveryInstanceDetail:
    """Fetch full detail for a single instance: all data properties and relations."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        detail = await graph_service.discover_instance_detail(
            workspace_id=payload.workspace_id,
            graph_uris=payload.graph_uris,
            instance_uri=payload.instance_uri,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DiscoveryInstanceDetail(
        uri=detail.uri,
        label=detail.label,
        class_uri=detail.class_uri,
        class_label=detail.class_label,
        data_properties=[
            DiscoveryDataPropertyItem(
                predicate_uri=dp.predicate_uri,
                predicate_label=dp.predicate_label,
                value=dp.value,
            )
            for dp in detail.data_properties
        ],
        relations=[
            DiscoveryInspectorRelationItem(
                role=r.role,
                predicate_uri=r.predicate_uri,
                predicate_label=r.predicate_label,
                other_uri=r.other_uri,
                other_label=r.other_label,
            )
            for r in detail.relations
        ],
    )


@router.post("/discovery/relation-types")
async def discovery_relation_types(
    payload: DiscoveryRelationTypesRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryRelationType]:
    """List object-property relation types found for selected/visible instances."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        relation_types = await graph_service.discover_relation_types(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            instance_uris=payload.instance_uris,
            graph_level=payload.graph_level,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryRelationType(uri=r.uri, label=r.label, count=r.count) for r in relation_types]


@router.post("/discovery/relations")
async def discovery_relations(
    payload: DiscoveryRelationsRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryRelationRow]:
    """List concrete relation rows (domain → predicate → range) for selected instances."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        relations = await graph_service.discover_relations(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            instance_uris=payload.instance_uris,
            relation_uris=payload.relation_uris,
            limit=payload.limit,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        DiscoveryRelationRow(
            relation_uri=r.relation_uri,
            relation_label=r.relation_label,
            domain_uri=r.domain_uri,
            domain_label=r.domain_label,
            domain_class_uri=r.domain_class_uri,
            domain_class_label=r.domain_class_label,
            range_uri=r.range_uri,
            range_label=r.range_label,
            range_class_uri=r.range_class_uri,
            range_class_label=r.range_class_label,
            role=r.role,
        )
        for r in relations
    ]


@router.post("/discovery/triples-export")
async def discovery_triples_export(
    payload: DiscoveryTriplesExportRequest,
    current_user: User = Depends(get_current_user_required),
) -> DiscoveryTriplesExportResponse:
    """Serialize discovery preview triples with rdflib (Turtle groups by subject URI)."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    rows = [t.model_dump() for t in payload.triples]
    fmt = payload.format  # type: ignore[arg-type]
    try:
        content, filename, media_type = serialize_discovery_triples(rows, fmt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DiscoveryTriplesExportResponse(
        content=content,
        filename=filename,
        media_type=media_type,
    )


# ── Network node endpoints ──────────────────────────────────────────────────


@router.post("/network/node-properties")
async def network_node_properties(
    payload: NetworkNodePropertiesRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryProperty]:
    """Return all data properties available for instances of a given class in the network view."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        properties = await graph_service.discover_properties(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            class_uris=[payload.class_uri],
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [DiscoveryProperty(uri=p.uri, label=p.label, kind=p.kind) for p in properties]


@router.post("/network/node-instances")
async def network_node_instances(
    payload: NetworkNodeInstancesRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[DiscoveryInstance]:
    """Return instances of a given class with the selected data properties for the network table view."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    try:
        instances = await graph_service.discover_instances(
            workspace_id=payload.workspace_id,
            graph_uri=payload.graph_uri,
            class_uris=[payload.class_uri],
            property_uris=payload.property_uris,
            search="",
            limit=payload.limit,
            enrich=payload.enrich,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        DiscoveryInstance(
            uri=i.uri,
            label=i.label,
            class_uri=i.class_uri,
            class_label=i.class_label,
            properties=i.properties,
            object_properties=i.object_properties,
            domain_relations_count=i.domain_relations_count,
            range_relations_count=i.range_relations_count,
            properties_count=i.properties_count,
            bfo_bucket_uri=i.bfo_bucket_uri,
            bfo_bucket_label=i.bfo_bucket_label,
        )
        for i in instances
    ]


@router.get("/network/parents")
async def get_network_parents(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_names: list[str] = Query(default=[], alias="graph_names"),
    node_iris: list[str] = Query(default=[], alias="node_iris"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphData:
    """Return parent class nodes for given frontier node IRIs.

    Handles both individuals (returns rdf:type class + edge) and
    classes (returns rdfs:subClassOf parents from schema graph + edges).
    Call once per progressive expansion level.
    """
    await require_workspace_access(current_user.id, workspace_id)
    try:
        result = await graph_service.get_network_parents(
            workspace_id=workspace_id,
            graph_names=graph_names,
            node_iris=node_iris,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphData(
        nodes=[_node_to_schema(n) for n in result.nodes],
        edges=[_edge_to_schema(e) for e in result.edges],
    )


# ── Backend-driven query endpoint (Explore rework, AUDIT §7b) ──────────────────


def _build_graph_query_service(graph_service: GraphService) -> GraphQueryService:
    """Wire a GraphQueryService over the configured triple store for this request."""
    triple_store = graph_service._get_triple_store()
    store = GraphQueryTripleStoreAdapter(triple_store, fts_backend=resolve_fts_backend(triple_store))

    async def _owned_graphs(workspace_id: str) -> set[str]:
        packs = await graph_service.list_graphs(workspace_id)
        return {g.uri for pack in packs for g in pack.graphs}

    # schema/nexus are global system graphs every workspace may read.
    system_graphs = {str(SCHEMA_GRAPH_URI), str(NEXUS_GRAPH_URI)}
    cache = _QueryResultCache(_QUERY_CACHE, _QUERY_CACHE_TTL)
    return GraphQueryService(
        store, owned_graphs=_owned_graphs, system_graphs=system_graphs,
        count_cache=cache, page_cache=cache, columns_cache=cache,
    )


@router.post("/query")
async def graph_query(
    payload: GraphQueryRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphQueryResponse:
    """Compile a ViewQuerySpec to one SPARQL query and return columns + rows + page + count."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _build_graph_query_service(graph_service)
    try:
        result = await service.run_query(
            spec=payload.spec.to_domain(),
            workspace_id=payload.workspace_id,
            cursor=payload.cursor,
            limit=payload.limit,
            include_sparql=payload.include_sparql,
            force_count_refresh=payload.force_count_refresh,
            force_refresh=payload.force_refresh,
        )
    except GraphAccessError as exc:  # workspace does not own a requested graph
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GraphQuerySpecError as exc:  # malformed / guard-exceeded spec
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphQueryResponse.from_result(result)


@router.post("/query/facets")
async def graph_query_facets(
    payload: GraphFacetsRequest,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphFacetsResponse:
    """Distinct values + counts for one column under the other columns' filters (Excel dropdown)."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _build_graph_query_service(graph_service)
    try:
        result = await service.facets(
            spec=payload.spec.to_domain(),
            workspace_id=payload.workspace_id,
            target_column_id=payload.target_column_id,
            search=payload.search,
            limit=payload.limit,
        )
    except GraphAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GraphQuerySpecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphFacetsResponse.from_domain(result)


@router.get("/columns")
async def graph_columns(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: list[str] = Query(..., description="Named graph URI(s)"),
    class_uri: list[str] = Query(..., description="Anchor class URI(s)"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphColumnsResponse:
    """Discover selectable columns (ontology ∪ data) for an anchored class + type inference."""
    await require_workspace_access(current_user.id, workspace_id)
    service = _build_graph_query_service(graph_service)
    try:
        cols = await service.discover_columns(
            workspace_id=workspace_id, graph_uris=graph_uri, class_uris=class_uri
        )
    except GraphAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GraphQuerySpecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphColumnsResponse.from_domain(class_uri, cols)


@router.get("/search")
async def graph_search(
    workspace_id: str = Query(..., description="Workspace ID"),
    q: str = Query(..., min_length=1, description="Free-text query"),
    graph_uri: list[str] = Query(default=[], description="Optional named graph URI(s); default = all owned"),
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphSearchResponse:
    """Google-like entity search: classes ∪ individuals across owned graphs, each tagged with kind."""
    await require_workspace_access(current_user.id, workspace_id)
    service = _build_graph_query_service(graph_service)
    try:
        hits = await service.search_entities(
            workspace_id=workspace_id, graph_uris=graph_uri, query=q, limit=limit
        )
    except GraphAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GraphQuerySpecError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphSearchResponse.from_domain(q, hits)
