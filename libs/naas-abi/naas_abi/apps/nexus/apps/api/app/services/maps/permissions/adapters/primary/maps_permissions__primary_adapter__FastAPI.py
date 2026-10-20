"""HTTP routes for Maps availability, mounted under ``/api/maps/permissions``.

Settings → Maps → Access: which workspaces may use each deployment layer /
basemap (seeds) and each custom one this workspace owns. Reading needs a
workspace owner or admin; changing follows ``permissions/service.py``
(deployment items and "every workspace" need a platform superadmin; custom
items only touch workspaces the actor administers).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    require_workspace_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.primary.maps_basemaps__primary_adapter__FastAPI import (  # noqa: E501
    get_maps_basemap_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary.maps_layouts__primary_adapter__FastAPI import (  # noqa: E501
    get_maps_layout_service,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.postgres import (
    PostgresWorkspaceDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.factory import (
    postgres_maps_access,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_BASEMAP,
    KIND_LAYOUT,
    MapsGrant,
    MapsPermissionError,
    MapsPermissionValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import WorkspaceDirectoryPort
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsActor,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import maps_seed_registry
from pydantic import BaseModel, Field

router = APIRouter()

_directory = PostgresWorkspaceDirectory()


def get_maps_access() -> MapsAccess:
    return postgres_maps_access()


def get_workspace_directory() -> WorkspaceDirectoryPort:
    return _directory


class GrantIn(BaseModel):
    all_workspaces: bool = False
    workspace_ids: list[str] = Field(default_factory=list, max_length=500)


def _grant_out(grant: MapsGrant) -> dict[str, Any]:
    return {
        "all_workspaces": grant.workspace_ids is None,
        "workspace_ids": sorted(grant.workspace_ids or ()),
    }


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, MapsPermissionValidationError):
        return HTTPException(status_code=422, detail={"errors": exc.errors})
    if isinstance(exc, MapsPermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Permission change failed: {exc}")


async def _items(
    request: Request,
    workspace_id: str,
    layouts: MapsLayoutService,
    basemaps: MapsBasemapService,
    superadmin: bool,
) -> list[dict[str, Any]]:
    """(kind, id, title, owner, editable) for the items this workspace can manage or sees."""
    registry = maps_seed_registry(request.app)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, item_id: str, title: str, owner: str, editable: bool) -> None:
        if (kind, item_id) in seen:
            return
        seen.add((kind, item_id))
        items.append(
            {"kind": kind, "item_id": item_id, "title": title, "owner": owner, "editable": editable}
        )

    listed_layouts = (await layouts.list(workspace_id)).layouts
    listed_basemaps = (await basemaps.list(workspace_id)).basemaps
    titles = {(KIND_LAYOUT, layout.id): layout.title for layout in listed_layouts}
    titles.update({(KIND_BASEMAP, b.id): b.title for b in listed_basemaps})

    # Deployment items: all seeds, even those this workspace may not use (so they can be re-enabled).
    for seed in registry.layouts.values():
        add(
            KIND_LAYOUT,
            seed.id,
            titles.get((KIND_LAYOUT, seed.id), seed.title),
            DEPLOYMENT,
            superadmin,
        )
    for basemap_seed in registry.basemaps.values():
        b = basemap_seed.basemap
        add(KIND_BASEMAP, b.id, titles.get((KIND_BASEMAP, b.id), b.title), DEPLOYMENT, superadmin)
    for layout in listed_layouts:
        if not layout.system:
            add(
                KIND_LAYOUT,
                layout.id,
                layout.title,
                layout.shared_from or workspace_id,
                not layout.shared_from,
            )
    for basemap in listed_basemaps:
        if not basemap.system:
            add(
                KIND_BASEMAP,
                basemap.id,
                basemap.title,
                basemap.shared_from or workspace_id,
                not basemap.shared_from,
            )
    return items


@router.get("")
async def list_permissions(
    request: Request,
    response: Response,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    layouts: MapsLayoutService = Depends(get_maps_layout_service),
    basemaps: MapsBasemapService = Depends(get_maps_basemap_service),
    access: MapsAccess = Depends(get_maps_access),
    directory: WorkspaceDirectoryPort = Depends(get_workspace_directory),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    superadmin = bool(getattr(current_user, "is_superadmin", False))
    items = await _items(request, workspace_id, layouts, basemaps, superadmin)
    policies = {
        KIND_LAYOUT: await access.policy(KIND_LAYOUT),
        KIND_BASEMAP: await access.policy(KIND_BASEMAP),
    }
    workspaces = await directory.administered(current_user.id, superadmin=superadmin)
    return {
        "superadmin": superadmin,
        "workspaces": [{"id": w.id, "name": w.name} for w in workspaces],
        "items": [
            {**item, **_grant_out(policies[item["kind"]].grant(item["item_id"], item["owner"]))}
            for item in items
        ],
    }


@router.put("/{kind}/{item_id}")
async def update_permission(
    kind: Literal["layout", "basemap"],
    item_id: str,
    body: GrantIn,
    request: Request,
    workspace_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
    layouts: MapsLayoutService = Depends(get_maps_layout_service),
    basemaps: MapsBasemapService = Depends(get_maps_basemap_service),
    access: MapsAccess = Depends(get_maps_access),
    directory: WorkspaceDirectoryPort = Depends(get_workspace_directory),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    superadmin = bool(getattr(current_user, "is_superadmin", False))
    items = await _items(request, workspace_id, layouts, basemaps, superadmin)
    item = next((i for i in items if i["kind"] == kind and i["item_id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No {kind} {item_id!r} in this workspace")
    if not item["editable"]:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only a platform superadmin can change deployment items"
                if item["owner"] == DEPLOYMENT
                else "Shared from another workspace: change its access there"
            ),
        )
    workspaces = await directory.administered(current_user.id, superadmin=superadmin)
    known = {w.id for w in workspaces}
    if superadmin:
        unknown = set(body.workspace_ids) - known
        if unknown:
            raise HTTPException(
                status_code=422,
                detail={"errors": ["unknown workspaces: " + ", ".join(sorted(unknown))]},
            )
    actor = MapsActor(current_user.id, superadmin, frozenset(known))
    try:
        grant = await access.update(
            kind,
            item_id,
            item["owner"],
            all_workspaces=body.all_workspaces,
            workspace_ids=set(body.workspace_ids),
            actor=actor,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {**item, **_grant_out(grant)}
