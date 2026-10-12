"""HTTP routes for workspace Maps basemaps, mounted under ``/api/maps/basemaps``.

Reading (list, preview) needs workspace access; creating, editing, deleting,
hiding and uploading previews needs a workspace owner or admin — the same
model as ``/api/maps/layouts``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_workspace_role,
    require_workspace_access,
    require_workspace_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.postgres import (
    PostgresMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MAX_PREVIEW_BYTES,
    MapsBasemap,
    MapsBasemapNotFoundError,
    MapsBasemapPolicyError,
    MapsBasemapValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import (
    MapsBasemapService,
    SeedLike,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.factory import (
    postgres_maps_access,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.postgres import (
    PostgresMapsSettingsStore,
)
from pydantic import BaseModel, Field

router = APIRouter()

_service = MapsBasemapService(
    PostgresMapsBasemapStore(), PostgresMapsSettingsStore(), postgres_maps_access()
)

# Previews are images, but SVG is markup: never let one run or load anything.
PREVIEW_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "Cache-Control": "private, max-age=300",
}


def get_maps_basemap_service() -> MapsBasemapService:
    return _service


def basemap_seeds(request: Request) -> list[SeedLike]:
    return [
        (seed.basemap, seed.preview) for seed in maps_seed_registry(request.app).basemaps.values()
    ]


class BasemapIn(BaseModel):
    title: str = Field(max_length=80)
    category: str = "custom"
    order: int = 100
    renderer: dict[str, Any]


class VisibilityIn(BaseModel):
    hidden: bool


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, MapsBasemapValidationError):
        return HTTPException(status_code=422, detail={"errors": exc.errors})
    if isinstance(exc, MapsBasemapNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, MapsBasemapPolicyError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Basemap operation failed: {exc}")


@router.get("")
async def list_basemaps(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    listed = await service.list(workspace_id, seeds=basemap_seeds(request))
    role = await get_workspace_role(current_user.id, workspace_id)
    return {
        "basemaps": [basemap.to_dict() for basemap in listed.basemaps],
        "hidden": sorted(listed.hidden),
        "can_edit": role in ("owner", "admin"),
    }


@router.get("/{basemap_id}/preview")
async def get_basemap_preview(
    basemap_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> Response:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        preview = await service.get_preview(workspace_id, basemap_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return Response(
        content=preview.content, media_type=preview.content_type, headers=PREVIEW_HEADERS
    )


@router.put("/{basemap_id}/preview")
async def upload_basemap_preview(
    basemap_id: str,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    """Replace the preview: raw image body, its type in ``Content-Type``."""
    await require_workspace_admin(current_user.id, workspace_id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="Preview is too large")
    content = b""
    async for chunk in request.stream():
        content += chunk
        if len(content) > MAX_PREVIEW_BYTES:
            raise HTTPException(status_code=413, detail="Preview is too large")
    try:
        saved = await service.set_preview(
            workspace_id,
            basemap_id,
            request.headers.get("content-type", ""),
            content,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return saved.to_dict()


@router.put("/{basemap_id}/visibility")
async def set_basemap_visibility(
    basemap_id: str,
    body: VisibilityIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    try:
        hidden = await service.set_hidden(
            workspace_id, basemap_id, body.hidden, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"hidden": sorted(hidden)}


@router.put("/{basemap_id}")
async def save_basemap(
    basemap_id: str,
    body: BasemapIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    basemap = MapsBasemap(
        id=basemap_id,
        title=body.title,
        category=body.category,
        order=body.order,
        renderer=body.renderer,
    )
    try:
        saved = await service.save(workspace_id, basemap, user_id=current_user.id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return saved.to_dict()


@router.delete("/{basemap_id}")
async def delete_basemap(
    basemap_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, str]:
    await require_workspace_admin(current_user.id, workspace_id)
    try:
        await service.delete(workspace_id, basemap_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"message": "Basemap deleted"}
