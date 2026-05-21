"""Graph FastAPI primary adapter."""

from __future__ import annotations

import io
from dataclasses import asdict

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
    GraphAnalysis,
    GraphClear,
    GraphConfigUpdate,
    GraphCreate,
    GraphData,
    GraphDelete,
    GraphEdge,
    GraphInfo,
    GraphNode,
    GraphOverview,
    GraphPack,
    IndividualCreate,
    IndividualDelete,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphProtectedError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.port import (
    GraphConfigCreateInput,
    GraphConfigRecord,
    GraphConfigUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.service import (
    GraphService,
    _detect_rdf_format,
)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


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
    only_enabled: bool = Query(False, alias="only_enabled"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[GraphPack]:
    """List all graphs available in the triple store and nexus ontology graph.

    When ``workspace_id`` is provided, results carry the workspace's enable
    state. Graphs without a stored record are auto-persisted with
    ``enabled=True`` so the settings UI sees a stable catalog. Pass
    ``only_enabled=true`` to filter out disabled graphs (used by the sidebar).
    """
    await require_workspace_access(current_user.id, workspace_id)
    try:
        graph_packs = await graph_service.list_graphs(workspace_id=workspace_id)
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    enabled_by_uri: dict[str, bool] = await graph_service.get_enabled_states(workspace_id)

    # Auto-persist any newly discovered graphs for this workspace.
    all_graphs = [g for pack in graph_packs for g in pack.graphs]
    new_configs = [
        GraphConfigCreateInput(
            workspace_id=workspace_id,
            graph_uri=g.uri,
            name=g.label,
            enabled=True,
        )
        for g in all_graphs
        if g.uri not in enabled_by_uri
    ]
    if new_configs:
        try:
            created = await graph_service.create_workspace_configs(new_configs)
            for record in created:
                enabled_by_uri[record.graph_uri] = record.enabled
        except Exception:
            pass

    result: list[GraphPack] = []
    for pack in graph_packs:
        graphs_in_pack: list[GraphInfo] = []
        for g in pack.graphs:
            enabled = enabled_by_uri.get(g.uri, True)
            if only_enabled and not enabled:
                continue
            graphs_in_pack.append(
                GraphInfo(
                    id=g.id,
                    uri=g.uri,
                    label=g.label,
                    role_label=g.role_label,
                    enabled=enabled,
                )
            )
        if graphs_in_pack:
            result.append(GraphPack(role_label=pack.role_label, graphs=graphs_in_pack))
    return result


def _serialize_config(record: GraphConfigRecord) -> dict:
    data = asdict(record)
    data["created_at"] = record.created_at.isoformat()
    data["updated_at"] = record.updated_at.isoformat()
    return data


@router.get("/configs/{workspace_id}")
async def list_graph_configs(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> list[dict]:
    """List every stored graph config row for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    records = await graph_service.list_workspace_configs(workspace_id)
    return [_serialize_config(r) for r in records]


@router.patch("/configs/{workspace_id}/{graph_uri:path}")
async def update_graph_config(
    workspace_id: str,
    graph_uri: str,
    updates: GraphConfigUpdate,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict:
    """Update a graph config (e.g. enable/disable).

    Idempotent: if no row exists yet, one is created with the supplied
    values so the UI toggle can call PATCH without a prior POST.
    """
    await require_workspace_access(current_user.id, workspace_id)

    record = await graph_service.update_workspace_config(
        workspace_id=workspace_id,
        graph_uri=graph_uri,
        updates=GraphConfigUpdateInput(enabled=updates.enabled),
    )
    if record is None:
        try:
            graph_packs = await graph_service.list_graphs(workspace_id=workspace_id)
        except GraphServiceUnavailableError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        all_graphs = [g for pack in graph_packs for g in pack.graphs]
        match = next((g for g in all_graphs if g.uri == graph_uri), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Graph not found")
        enabled = True if updates.enabled is None else updates.enabled
        record = await graph_service.create_workspace_config(
            GraphConfigCreateInput(
                workspace_id=workspace_id,
                graph_uri=graph_uri,
                name=match.label,
                enabled=enabled,
            )
        )
    return _serialize_config(record)


@router.delete("/configs/{workspace_id}/{graph_uri:path}")
async def delete_graph_config(
    workspace_id: str,
    graph_uri: str,
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> dict[str, str]:
    """Delete a graph config (reverts to the default ``enabled=True``)."""
    await require_workspace_access(current_user.id, workspace_id)
    deleted = await graph_service.delete_workspace_config(workspace_id, graph_uri)
    if not deleted:
        raise HTTPException(status_code=404, detail="Graph config not found")
    return {"status": "deleted"}


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
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphInfo(id=graph.id, uri=graph.uri, label=graph.label)


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


@router.get("/export")
async def export_graph(
    workspace_id: str = Query(..., description="Workspace ID"),
    graph_uri: str = Query(..., description="Graph URI to export"),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> StreamingResponse:
    """Export all triples from a named graph as a TTL (Turtle) file.

    Fetches triples in batches of 10 000 and loops until the graph is fully
    exhausted, then returns the merged Turtle document with bound namespaces.
    """
    await require_workspace_access(current_user.id, workspace_id)
    try:
        ttl_content, triple_count = await graph_service.export_graph_as_ttl(
            workspace_id=workspace_id,
            graph_uri=graph_uri,
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    graph_name = graph_uri.rstrip("/").split("/")[-1] or "graph"
    filename = f"{graph_name}.ttl"

    return StreamingResponse(
        io.BytesIO(ttl_content.encode("utf-8")),
        media_type="text/turtle",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Triple-Count": str(triple_count),
            "Access-Control-Expose-Headers": "X-Triple-Count, Content-Disposition",
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
