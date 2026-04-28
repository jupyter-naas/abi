"""Graph FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (  # noqa: E501
    get_graph_service,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__schemas import (  # noqa: E501
    GraphClear,
    GraphCreate,
    GraphData,
    GraphDelete,
    GraphEdge,
    GraphInfo,
    GraphPack,
    GraphNode,
    GraphOverview,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphProtectedError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

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
        await graph_service.clear_graph(workspace_id=payload.workspace_id, graph_id=payload.id)
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
        await graph_service.delete_graph(workspace_id=payload.workspace_id, graph_id=payload.id)
    except GraphProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.get("/{graph_id}/overview")
async def get_graph_overview(
    graph_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphOverview:
    """Get overview of a given graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        overview = await graph_service.get_graph_overview(
            workspace_id=workspace_id, graph_id=graph_id, limit=limit
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphOverview(
        kpis=overview.kpis,
        instances_by_class=overview.instances_by_class,
    )


@router.get("/{graph_id}/network")
async def get_graph_network(
    graph_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphData:
    """Get all nodes and edges for a given graph."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        network = await graph_service.get_graph_network(
            workspace_id=workspace_id, graph_id=graph_id, limit=limit
        )
    except GraphServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphData(
        nodes=[_node_to_schema(n) for n in network.nodes],
        edges=[_edge_to_schema(e) for e in network.edges],
    )
