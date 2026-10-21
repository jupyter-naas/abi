"""HTTP routes for workspace Maps layouts, mounted under ``/api/maps/layouts``.

Reading (list, get, feed) is for everybody who sees the workspace's maps;
creating, editing, deleting, hiding, recoloring and previewing layouts is for
its admins (the IAM actions of the ``layout`` type say so). Every SPARQL query
runs through the workspace-scoped graph store, narrowed to the layout's graphs,
so a layout only ever reads what the caller may read. Feed layers
(``feed_type=geojson_url``) are fetched by the web proxy at
``/api/maps/custom/{id}``, which reads the record from here. Stored feeds
(``object_storage``) are served by ``/api/maps/feed-layers/{id}/data``; their
logo by ``/{id}/logo`` here.
"""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_released,
)
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
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.objects import (
    get_maps_cache,
    get_maps_objects,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.workspace_defaults import (
    graph_feed_ids,
    maps_workspace_defaults,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.dependencies import (
    get_maps_feed_layer_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.postgres import (
    PostgresMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    BUILTIN_LAYOUT_IDS,
    FEED_SPARQL,
    MapsLayout,
    MapsLayoutNotFoundError,
    MapsLayoutPolicyError,
    MapsLayoutValidationError,
    legacy_group_label,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import (
    MAX_LOGO_BYTES,
    MapsObjectMissingError,
    MapsObjectStorePort,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.factory import (
    postgres_maps_access,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.postgres import (
    PostgresMapsSettingsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.storage_keys import image_content_type
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

router = APIRouter()

# The logo key a (workspace, feed) resolves to: logos load on every map view.
LOGO_PATH_TTL = timedelta(seconds=60)

_service = MapsLayoutService(
    PostgresMapsLayoutStore(), PostgresMapsSettingsStore(), postgres_maps_access()
)
PREVIEW_PINS = 50


def get_maps_layout_service() -> MapsLayoutService:
    return _service


class LayoutIn(BaseModel):
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="MapPin", max_length=48)
    color: str = "#2563eb"
    query: str = ""
    graphs: list[str] = Field(default_factory=list, max_length=50)
    order: int = 100
    feed_type: str = FEED_SPARQL
    feed_url: str = Field(default="", max_length=500)
    # Sidebar group label. ``category`` is the pre-``group`` slug, read when no group is sent.
    group: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=48)
    logo_url: str = Field(default="", max_length=500)
    basemap_id: str = Field(default="", max_length=48)
    meta_label: str = Field(default="", max_length=120)
    fit_max_zoom: int | None = None


class PreviewIn(LayoutIn):
    workspace_id: str


class VisibilityIn(BaseModel):
    hidden: bool


class FeedsVisibilityIn(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=1000)
    hidden: bool


class ColorIn(BaseModel):
    color: str | None


def layout_seed_revisions(request: Request) -> dict[str, int]:
    return maps_seed_registry(request.app).layout_revisions()


def layout_seeds(request: Request) -> list[MapsLayout]:
    return list(maps_seed_registry(request.app).layouts.values())


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
    if isinstance(exc, MapsLayoutPolicyError):
        return HTTPException(status_code=409, detail=str(exc))
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
        feed_type=body.feed_type,
        feed_url=body.feed_url.strip(),
        group=body.group.strip() or legacy_group_label(body.category),
        logo_url=body.logo_url.strip(),
        basemap_id=body.basemap_id.strip(),
        meta_label=body.meta_label.strip(),
        fit_max_zoom=body.fit_max_zoom,
    )


@router.get("", dependencies=[guard("ListLayouts", literal="-")])
async def list_layouts(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
    defaults: WorkspaceMapsDefaults = Depends(maps_workspace_defaults),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    listed = await service.list(
        workspace_id,
        seeds=layout_seeds(request),
        revisions=layout_seed_revisions(request),
        enabled_feeds=defaults.feeds,
        extra_feed_ids=graph_feed_ids(request),
    )
    can_edit = await authz.allowed(
        "UpdateLayout", user=current_user, workspace=workspace_id, id="-"
    )
    return {
        "layouts": [layout.to_dict() for layout in listed.layouts],
        "hidden": sorted(listed.hidden),
        "colors": listed.colors,
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
        return {"errors": errors, "count": 0, "type": "FeatureCollection", "features": []}
    try:
        store = await _scoped_store(current_user.id, body.workspace_id, layout.graphs)
        payload = await service.feed(layout, store)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        "errors": [],
        "count": min(payload["count"], PREVIEW_PINS),
        "type": "FeatureCollection",
        "features": payload["features"][:PREVIEW_PINS],
    }


@router.post(
    "/feed-visibility",
    dependencies=[guard("SetLayoutVisibility", literal="-")],
)
async def set_feeds_visibility(
    body: FeedsVisibilityIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """Switch several feeds off or on at once (Settings → Maps bulk action)."""
    try:
        hidden = await service.set_feeds_hidden(
            workspace_id, body.ids, body.hidden, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"hidden_feeds": sorted(hidden)}


@router.get(
    "/{layout_id}/logo",
    dependencies=[declares("GetLayout")],
)
async def layout_logo(
    layout_id: str,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_released),
    service: MapsLayoutService = Depends(get_maps_layout_service),
    objects: MapsObjectStorePort = Depends(get_maps_objects),
    cache: MapsCache = Depends(get_maps_cache),
) -> Response:
    """The feed's logo, read from object storage at the key its record names."""
    # Decided by IAM at every request (in process, no database connection held);
    # only what the layout resolves to is cached.
    await authz.require("GetLayout", user=current_user, workspace=workspace_id, id=layout_id)

    async def resolve() -> dict[str, str]:
        return {"logo_path": (await service.get(workspace_id, layout_id)).logo_path}

    try:
        resolved = await cache.json_or_load(
            f"nexus:maps:logo:{workspace_id}:{layout_id}", LOGO_PATH_TTL, resolve
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    logo_path = resolved["logo_path"]
    content_type = image_content_type(logo_path) if logo_path else None
    if not content_type:
        raise HTTPException(status_code=404, detail="This feed has no stored logo")
    try:
        content = await run_in_threadpool(objects.read, logo_path)
    except MapsObjectMissingError as exc:
        raise HTTPException(status_code=404, detail="Logo not published") from exc
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=502, detail="Logo is too large")
    headers = {
        "Cache-Control": "private, max-age=3600",
        "ETag": f'"{sha256(content).hexdigest()[:32]}"',
    }
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type=content_type, headers=headers)


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


@router.get(
    "/{layout_id}",
    dependencies=[guard("GetLayout", id="layout_id")],
)
async def get_layout(
    layout_id: str,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """One layer record (the web feed proxy reads ``feed_url`` from here)."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return (await service.get(workspace_id, layout_id)).to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put(
    "/{layout_id}/color",
    dependencies=[guard("UpdateLayout", id="layout_id")],
)
async def set_layout_color(
    layout_id: str,
    body: ColorIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """Default pin / group-by-country color of any layer; null resets a built-in."""
    try:
        colors = await service.set_color(
            workspace_id, layout_id, body.color, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"colors": colors}


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


@router.put(
    "/{layout_id}/feed-visibility",
    dependencies=[guard("SetLayoutVisibility", id="layout_id")],
)
async def set_feed_visibility(
    layout_id: str,
    body: VisibilityIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsLayoutService = Depends(get_maps_layout_service),
) -> dict[str, Any]:
    """Switch a whole feed (every layer drawn from it) off or on in this workspace."""
    try:
        hidden = await service.set_feed_hidden(
            workspace_id, layout_id, body.hidden, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"hidden_feeds": sorted(hidden)}


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
    layers: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
) -> dict[str, str]:
    """Delete a feed and every layer on it."""
    try:
        await layers.delete_feed(workspace_id, layout_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"message": "Layout deleted"}
