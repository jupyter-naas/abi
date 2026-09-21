"""Maps catalog and read-only feeds using Nexus membership and graph policies."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (
    get_graph_service,
    workspace_graph_service,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
from naas_abi.apps.nexus.apps.api.app.services.maps.service import GraphMapLayer, MapsCatalog
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/maps/layers", tags=["Maps"])


async def scoped_graph(
    workspace_id: str = Query(..., min_length=1),
    user: User = Depends(get_current_user_required),
    graph: GraphService = Depends(get_graph_service),
) -> GraphService:
    return await workspace_graph_service(graph, user.id, workspace_id)


@router.get("")
async def layers(request: Request, response: Response, graph: GraphService = Depends(scoped_graph)):
    response.headers["Cache-Control"] = "no-store"
    return {"layers": request.app.state.maps_catalog.list_layers(graph.access_scope)}


@router.get("/{layer_id}")
async def feed(
    layer_id: str, request: Request, response: Response, graph: GraphService = Depends(scoped_graph)
):
    response.headers["Cache-Control"] = "no-store"
    catalog = request.app.state.maps_catalog
    if layer_id not in catalog.layers:
        raise HTTPException(404, "Map layer not found")
    try:
        return await run_in_threadpool(
            catalog.feed, layer_id, graph.access_scope, graph._get_triple_store()
        )
    except GraphAccessError as exc:
        raise HTTPException(403, str(exc)) from exc


def register_map_layer(app, layer: GraphMapLayer):
    if not hasattr(app.state, "maps_catalog"):
        app.state.maps_catalog = MapsCatalog()
        app.include_router(router)
    app.state.maps_catalog.register(layer)
