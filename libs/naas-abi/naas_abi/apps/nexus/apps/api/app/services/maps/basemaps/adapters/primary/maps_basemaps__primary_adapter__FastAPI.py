"""HTTP routes for workspace Maps basemaps, mounted under ``/api/maps/basemaps``.

Reading (list, preview) is for everybody who sees the workspace's maps;
creating, editing, deleting, hiding and uploading previews is for its admins
(the IAM actions of the ``basemap`` type say so) — the same model as
``/api/maps/layouts``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.workspace_defaults import (
    maps_workspace_defaults,
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
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults
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


def basemap_seed_revisions(request: Request) -> dict[str, int]:
    return maps_seed_registry(request.app).basemap_revisions()


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


@router.get("", dependencies=[guard("ListBasemaps", literal="-")])
async def list_basemaps(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
    defaults: WorkspaceMapsDefaults = Depends(maps_workspace_defaults),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    listed = await service.list(
        workspace_id,
        seeds=basemap_seeds(request),
        revisions=basemap_seed_revisions(request),
        enabled_custom=defaults.custom_basemaps,
    )
    can_edit = await authz.allowed(
        "UpdateBasemap", user=current_user, workspace=workspace_id, id="-"
    )
    return {
        "basemaps": [basemap.to_dict() for basemap in listed.basemaps],
        "hidden": sorted(listed.hidden),
        "can_edit": can_edit,
    }


@router.get("/{basemap_id}/preview", dependencies=[guard("GetBasemap", id="basemap_id")])
async def get_basemap_preview(
    basemap_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> Response:
    try:
        preview = await service.get_preview(workspace_id, basemap_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return Response(
        content=preview.content, media_type=preview.content_type, headers=PREVIEW_HEADERS
    )


@router.put("/{basemap_id}/preview", dependencies=[guard("UpdateBasemap", id="basemap_id")])
async def upload_basemap_preview(
    basemap_id: str,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    """Replace the preview: raw image body, its type in ``Content-Type``."""
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


@router.put(
    "/{basemap_id}/visibility", dependencies=[guard("SetBasemapVisibility", id="basemap_id")]
)
async def set_basemap_visibility(
    basemap_id: str,
    body: VisibilityIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
    try:
        hidden = await service.set_hidden(
            workspace_id, basemap_id, body.hidden, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"hidden": sorted(hidden)}


@router.put("/{basemap_id}", dependencies=[guard("UpdateBasemap", id="basemap_id")])
async def save_basemap(
    basemap_id: str,
    body: BasemapIn,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, Any]:
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


@router.delete("/{basemap_id}", dependencies=[guard("DeleteBasemap", id="basemap_id")])
async def delete_basemap(
    basemap_id: str,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    service: MapsBasemapService = Depends(get_maps_basemap_service),
) -> dict[str, str]:
    try:
        await service.delete(workspace_id, basemap_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"message": "Basemap deleted"}
