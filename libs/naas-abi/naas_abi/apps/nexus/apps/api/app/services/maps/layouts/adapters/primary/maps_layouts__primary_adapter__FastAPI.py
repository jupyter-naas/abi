"""HTTP routes for workspace Maps layouts, mounted under ``/api/maps/layouts``.

Reading (list, feed) is for everybody who sees the workspace's maps; creating,
editing, deleting, hiding and previewing layouts is for its admins (the IAM
actions of the ``layout`` type say so). Every query runs through the
workspace-scoped graph store, narrowed to the layout's graphs, so a layout only
ever reads what the caller may read.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphQuerySpecError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (  # noqa: E501
    GraphQueryTripleStoreAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.postgres import (
    PostgresMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    BUILTIN_LAYOUT_IDS,
    MapsLayout,
    MapsLayoutNotFoundError,
    MapsLayoutValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from pydantic import BaseModel, Field

router = APIRouter()

_service = MapsLayoutService(PostgresMapsLayoutStore())
PREVIEW_PINS = 50


def get_maps_layout_service() -> MapsLayoutService:
    return _service


class LayoutIn(BaseModel):
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="MapPin", max_length=48)
    color: str = "#2563eb"
    query: str
    graphs: list[str] = Field(default_factory=list, max_length=50)
    order: int = 100


class PreviewIn(LayoutIn):
    workspace_id: str


class VisibilityIn(BaseModel):
    hidden: bool


def _reserved(request: Request) -> set[str]:
    """Built-in layout ids plus graph layers registered by modules."""
    catalog = getattr(request.app.state, "maps_catalog", None)
    return set(BUILTIN_LAYOUT_IDS) | set(getattr(catalog, "layers", {}) or {})


def _layout_scope(scope: GraphAccessScope, graphs: list[str] | tuple[str, ...]) -> GraphAccessScope:
    """Read-only: the layout's graphs the workspace may read, or all readable ones."""
    readable = scope.readable & frozenset(graphs) if graphs else scope.readable
    return GraphAccessScope(scope.workspace_id, readable, frozenset())


async def _scoped_store(
    user_id: str, workspace_id: str, graphs: list[str] | tuple[str, ...]
) -> IGraphQueryStore:
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (  # noqa: E501
        workspace_graph_service,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
        WorkspaceGraphStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    graph = await workspace_graph_service(
        ServiceRegistry.instance().graph, user_id, workspace_id, feature=None
    )
    assert graph.access_scope is not None
    scope = _layout_scope(graph.access_scope, graphs)
    return GraphQueryTripleStoreAdapter(WorkspaceGraphStore(graph._get_catalog_store(), scope))


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, MapsLayoutValidationError):
        return HTTPException(status_code=422, detail={"errors": exc.errors})
    if isinstance(exc, MapsLayoutNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, GraphAccessError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, GraphQuerySpecError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, GraphServiceUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=f"Layout query failed: {exc}")


def _layout(layout_id: str, body: LayoutIn) -> MapsLayout:
    return MapsLayout(
        id=layout_id,
        title=body.title.strip(),
        description=body.description.strip(),
        icon=body.icon,
        color=body.color,
        query=body.query,
        graphs=tuple(body.graphs),
        order=body.order,
    )


@router.get("", dependencies=[guard("ListLayouts", literal="-")])
async def list_layouts(
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    listed = await service.list(workspace_id)
    can_edit = await authz.allowed(
        "UpdateLayout", user=current_user, workspace=workspace_id, id="-"
    )
    return {
        "layouts": [layout.to_dict() for layout in listed.layouts],
        "hidden": sorted(listed.hidden),
        "can_edit": can_edit,
    }


@router.post("/preview", dependencies=[declares("PreviewLayout"), declares("triple_store:Query")])
async def preview_layout(
    body: PreviewIn,
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """Run an unsaved layout: its validation errors, or its pin count and first pins."""
    await authz.require("PreviewLayout", user=current_user, workspace=body.workspace_id, id="-")
    layout = _layout("preview", body)
    errors = service.validate(layout)
    if errors:
        return {"errors": errors, "count": 0, "pins": []}
    try:
        store = await _scoped_store(current_user.id, body.workspace_id, layout.graphs)
        payload = await service.feed(layout, store)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"errors": [], "count": payload["count"], "pins": payload["pins"][:PREVIEW_PINS]}


@router.get(
    "/{layout_id}/feed",
    dependencies=[guard("GetLayout", id="layout_id"), declares("triple_store:Query")],
)
async def layout_feed(
    layout_id: str,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    try:
        layout = await service.get(workspace_id, layout_id)
        store = await _scoped_store(current_user.id, workspace_id, layout.graphs)
        return await service.feed(layout, store)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put(
    "/{layout_id}/visibility",
    dependencies=[guard("SetLayoutVisibility", id="layout_id")],
)
async def set_layout_visibility(
    layout_id: str,
    body: VisibilityIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """Hide or show any layout (built-in or custom) in this workspace."""
    try:
        hidden = await service.set_hidden(
            workspace_id, layout_id, body.hidden, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"hidden": sorted(hidden)}


@router.put("/{layout_id}", dependencies=[guard("UpdateLayout", id="layout_id")])
async def save_layout(
    layout_id: str,
    body: LayoutIn,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    try:
        saved = await service.save(
            workspace_id,
            _layout(layout_id, body),
            user_id=current_user.id,
            reserved=_reserved(request),
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return saved.to_dict()


@router.delete("/{layout_id}", dependencies=[guard("DeleteLayout", id="layout_id")])
async def delete_layout(
    layout_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, str]:
    try:
        await service.delete(workspace_id, layout_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"message": "Layout deleted"}
