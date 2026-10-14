"""HTTP routes for map layers (views on feeds), mounted under ``/api/maps/feed-layers``.

Reading needs workspace access; creating, editing and deleting needs a
workspace owner or admin. Hiding uses ``/api/maps/layouts/{id}/visibility``
(one hidden set for every layer id).
"""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_released,
    require_workspace_access,
    require_workspace_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.objects import (
    get_maps_cache,
    get_maps_objects,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.cache import MapsCache
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.dependencies import (
    get_maps_feed_layer_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
    MapsFeedLayerNotFoundError,
    MapsFeedLayerPolicyError,
    MapsFeedLayerValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    BUILTIN_LAYOUT_IDS,
    MapsLayout,
    MapsLayoutNotFoundError,
    MapsLayoutPolicyError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.objects import (
    MapsObjectInvalidError,
    MapsObjectMissingError,
    MapsObjectStorePort,
    layer_features,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

router = APIRouter()

# Hot path (/data): a map opening fires many requests at once. Membership and
# what a layer resolves to are kept in the engine cache (MapsCache) briefly;
# layer writes here drop the layer's entry.
SOURCE_TTL = timedelta(seconds=30)


def _source_key(workspace_id: str, layer_id: str) -> str:
    return f"nexus:maps:source:{workspace_id}:{layer_id}"


class FeedLayerIn(BaseModel):
    feed_id: str = Field(max_length=48)
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=500)
    color: str = "#2563eb"
    icon: str = Field(default="", max_length=48)
    order: int = 100
    class_labels: list[str] = Field(default_factory=list, max_length=100)


def feed_layer_seed_revisions(request: Request) -> dict[str, int]:
    return maps_seed_registry(request.app).feed_layer_revisions()


def feed_layer_seeds(request: Request) -> list[MapsFeedLayer]:
    return list(maps_seed_registry(request.app).feed_layers.values())


def _reserved(request: Request) -> set[str]:
    catalog = getattr(request.app.state, "maps_catalog", None)
    return set(BUILTIN_LAYOUT_IDS) | set(getattr(catalog, "layers", {}) or {})


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, MapsFeedLayerValidationError):
        return HTTPException(status_code=422, detail={"errors": exc.errors})
    if isinstance(exc, MapsFeedLayerNotFoundError | MapsLayoutNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, MapsFeedLayerPolicyError | MapsLayoutPolicyError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Layer operation failed: {exc}")


@router.get("")
async def list_feed_layers(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    layers = await service.list(
        workspace_id,
        seeds=feed_layer_seeds(request),
        revisions=feed_layer_seed_revisions(request),
    )
    return {"layers": [layer.to_dict() for layer in layers]}


@router.get("/{layer_id}/data")
async def feed_layer_data(
    layer_id: str,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    all_features: bool = Query(
        False, alias="all", description="Every feature of the object, not only the layer's types"
    ),
    current_user=Depends(get_current_user_released),
    service: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
    objects: MapsObjectStorePort = Depends(get_maps_objects),
    cache: MapsCache = Depends(get_maps_cache),
) -> Response:
    """The layer's GeoJSON, read from object storage at the key its record names.

    ``all`` skips the layer's feature types (the map shares one load per object
    and filters in the browser; the member may read every layer of the feed
    anyway): the object is then sent as stored, without parsing it.
    Private data: revalidated on every load (``ETag``), never stored by caches.
    """
    await cache.member(
        current_user.id,
        workspace_id,
        lambda: require_workspace_access(current_user.id, workspace_id),
    )

    async def resolve() -> dict[str, Any]:
        layer, feed = await service.data_source(workspace_id, layer_id)
        return {"layer": layer.to_dict(), "feed": feed.to_dict()}

    try:
        source = await cache.json_or_load(_source_key(workspace_id, layer_id), SOURCE_TTL, resolve)
    except Exception as exc:
        raise _http_error(exc) from exc
    layer = MapsFeedLayer.from_dict(source["layer"])
    feed = MapsLayout.from_dict(source["feed"])
    try:
        raw = await run_in_threadpool(objects.read, layer.storage_path)
    except MapsObjectMissingError as exc:
        raise HTTPException(
            status_code=503, detail=f"Layer data not published: {layer.storage_path}"
        ) from exc
    class_labels = () if all_features else layer.class_labels
    digest = sha256(raw + "\n".join(class_labels).encode()).hexdigest()[:32]
    headers = {"Cache-Control": "private, no-cache", "ETag": f'"{digest}"'}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    if not class_labels:
        return Response(content=raw, media_type="application/geo+json", headers=headers)
    try:
        payload = layer_features(raw, class_labels)
    except MapsObjectInvalidError as exc:
        raise HTTPException(
            status_code=502, detail=f"Layer data is invalid ({layer.storage_path}): {exc}"
        ) from exc
    return JSONResponse(
        {**payload, "source": feed.title, "layer_title": layer.title}, headers=headers
    )


@router.get("/{layer_id}")
async def get_feed_layer(
    layer_id: str,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        return (await service.get(workspace_id, layer_id)).to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/{layer_id}")
async def save_feed_layer(
    layer_id: str,
    body: FeedLayerIn,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
    cache: MapsCache = Depends(get_maps_cache),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    cache.delete(_source_key(workspace_id, layer_id))
    layer = MapsFeedLayer(
        id=layer_id,
        feed_id=body.feed_id,
        title=body.title,
        description=body.description,
        color=body.color,
        icon=body.icon,
        order=body.order,
        class_labels=tuple(body.class_labels),
    )
    try:
        saved = await service.save(
            workspace_id, layer, user_id=current_user.id, reserved=_reserved(request)
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return saved.to_dict()


@router.delete("/{layer_id}")
async def delete_feed_layer(
    layer_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsFeedLayerService = Depends(get_maps_feed_layer_service),
    cache: MapsCache = Depends(get_maps_cache),
) -> dict[str, str]:
    await require_workspace_admin(current_user.id, workspace_id)
    cache.delete(_source_key(workspace_id, layer_id))
    try:
        await service.delete(workspace_id, layer_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"message": "Layer deleted"}
