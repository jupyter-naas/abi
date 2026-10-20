from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    get_workspace_role,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import deprecated_encrypt
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (
    _get_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    is_safe_drive_id,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
    issue_and_send_invite_sign_in,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationMemberAlreadyExistsError,
    OrganizationService,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces import logo_store
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.resource_access import (
    router as resource_access_router,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.background_image import (
    MAX_BACKGROUND_IMAGE_BYTES,
    MAX_ZOOM,
    MIN_ZOOM,
    BackgroundImageError,
    WorkspaceBackgroundImage,
    background_image_url,
    fetch_image_url,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
    WorkspaceCreateInput,
    WorkspaceMemberRecord,
    WorkspaceRecord,
    WorkspaceUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceMemberAlreadyExistsError,
    WorkspaceService,
    WorkspaceSlugAlreadyExistsError,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import (
    resolve_stored_asset_url,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
router.include_router(resource_access_router)


def get_workspace_service(db: AsyncSession = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def _get_email_service(request: Request) -> EmailService | None:
    service = getattr(request.app.state, "email_service", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule

        service = ABIModule.get_instance().engine.services.email
        request.app.state.email_service = service
        return service
    except Exception:
        return None


class Workspace(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    organization_id: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    background_image_url: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    description: str | None = None
    workspace_group: str | None = None
    platform_drive_enabled: bool = False
    system_drive_enabled: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    organization_logo_url: str | None = None
    organization_logo_rectangle_url: str | None = None
    current_user_role: str | None = None
    feature_flags: dict[str, bool] = Field(default_factory=dict)


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    organization_id: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    background_image_url: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    description: str | None = Field(default=None, max_length=200)
    workspace_group: str | None = Field(default=None, max_length=100)


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    background_image_url: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    description: str | None = Field(default=None, max_length=200)
    workspace_group: str | None = Field(default=None, max_length=100)
    platform_drive_enabled: bool | None = None
    system_drive_enabled: bool | None = None


class WorkspaceMember(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    source: str = "workspace"


class WorkspaceMemberInvite(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)


class InferenceServer(BaseModel):
    id: str
    workspace_id: str
    name: str
    type: str
    endpoint: str
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InferenceServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern=r"^(ollama|abi|vllm|llamacpp|custom)$")
    endpoint: str = Field(..., min_length=1)
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


class InferenceServerUpdate(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    description: str | None = None
    enabled: bool | None = None
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


async def _load_org_role_override(
    org_id: str | None,
    org_service: OrganizationService,
) -> dict[str, list[str]] | None:
    if not org_id:
        return None
    stored = await org_service.get_role_features(org_id=org_id)
    if stored is None:
        return None
    return stored.role_baseline


async def _load_org_role_overrides(
    org_ids: list[str | None],
    org_service: OrganizationService,
) -> dict[str, dict[str, list[str]] | None]:
    unique = sorted({org_id for org_id in org_ids if org_id})
    if not unique:
        return {}
    rows = await asyncio.gather(
        *[org_service.get_role_features(org_id=org_id) for org_id in unique]
    )
    return {
        org_id: (row.role_baseline if row is not None else None)
        for org_id, row in zip(unique, rows, strict=True)
    }


def _workspace_public_asset_url(raw: str | None) -> str | None:
    """Rewrite module asset paths (``src/external/…/assets/public/…``) to API URLs."""
    return resolve_stored_asset_url(raw)


def _to_schema(
    record: WorkspaceRecord,
    current_user_role: str | None,
    *,
    organization_override: dict[str, list[str]] | None = None,
) -> Workspace:
    role = current_user_role or "member"
    return Workspace(
        id=record.id,
        name=record.name,
        slug=record.slug,
        owner_id=record.owner_id,
        organization_id=record.organization_id,
        logo_url=_workspace_public_asset_url(record.logo_url),
        logo_emoji=record.logo_emoji,
        primary_color=record.primary_color,
        accent_color=record.accent_color,
        background_color=record.background_color,
        background_image_url=_workspace_public_asset_url(record.background_image_url),
        sidebar_color=record.sidebar_color,
        font_family=record.font_family,
        description=record.description,
        workspace_group=record.workspace_group,
        platform_drive_enabled=record.platform_drive_enabled,
        system_drive_enabled=record.system_drive_enabled,
        created_at=record.created_at,
        updated_at=record.updated_at,
        organization_logo_url=record.organization_logo_url,
        organization_logo_rectangle_url=record.organization_logo_rectangle_url,
        current_user_role=current_user_role,
        feature_flags=build_feature_flags(
            role=role,
            feature_flags_config=settings.feature_flags,
            workspace_slug=record.slug,
            workspace_id=record.id,
            organization_id=record.organization_id,
            organization_override=organization_override,
            workspace_override=record.feature_overrides,
        ),
    )


@router.get("")
async def list_workspaces(
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> list[Workspace]:
    rows = await service.list_workspaces(user_id=current_user.id)
    roles = await asyncio.gather(
        *[service.get_workspace_role(user_id=current_user.id, workspace_id=row.id) for row in rows]
    )
    overrides = await _load_org_role_overrides([row.organization_id for row in rows], org_service)
    return [
        _to_schema(
            row,
            role,
            organization_override=overrides.get(row.organization_id or ""),
        )
        for row, role in zip(rows, roles, strict=False)
    ]


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    role = await require_workspace_access(current_user.id, workspace_id)
    row = await service.get_workspace(workspace_id=workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_schema(
        row,
        role,
        organization_override=await _load_org_role_override(row.organization_id, org_service),
    )


@router.get("/slug/{slug}")
async def get_workspace_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    row = await service.get_workspace_by_slug(slug=slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    role = await require_workspace_access(current_user.id, row.id)
    return _to_schema(
        row,
        role,
        organization_override=await _load_org_role_override(row.organization_id, org_service),
    )


@router.post("")
async def create_workspace(
    workspace: WorkspaceCreate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    if workspace.organization_id:
        # Only the organization's owners and admins add workspaces to it.
        org_role = await org_service.get_organization_role(
            user_id=current_user.id, org_id=workspace.organization_id
        )
        if org_role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Only organization owners and admins can create workspaces",
            )
    try:
        record = await service.create_workspace(
            WorkspaceCreateInput(
                name=workspace.name,
                slug=workspace.slug,
                owner_id=current_user.id,
                organization_id=workspace.organization_id,
                logo_url=workspace.logo_url,
                logo_emoji=workspace.logo_emoji,
                primary_color=workspace.primary_color,
                accent_color=workspace.accent_color,
                background_color=workspace.background_color,
                background_image_url=workspace.background_image_url,
                sidebar_color=workspace.sidebar_color,
                font_family=workspace.font_family,
                description=workspace.description,
                workspace_group=workspace.workspace_group,
            )
        )
    except WorkspaceSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Slug already exists") from exc
    return _to_schema(
        record,
        "owner",
        organization_override=await _load_org_role_override(record.organization_id, org_service),
    )


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    role = await require_workspace_access(current_user.id, workspace_id)
    if role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the workspace owner can delete the workspace"
        )
    deleted = await service.delete_workspace(workspace_id=workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    updates: WorkspaceUpdate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    role = await require_workspace_access(current_user.id, workspace_id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update workspace settings")

    record = await service.update_workspace(
        workspace_id=workspace_id,
        updates=WorkspaceUpdateInput(**updates.model_dump(exclude_unset=True)),
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_schema(
        record,
        role,
        organization_override=await _load_org_role_override(record.organization_id, org_service),
    )


@router.get("/{workspace_id}/stats")
async def get_workspace_stats(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, workspace_id)
    stats = await service.get_workspace_stats(workspace_id=workspace_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "nodes": stats.nodes,
        "edges": stats.edges,
        "conversations": stats.conversations,
        "agents": stats.agents,
    }


@router.get("/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceMember]:
    await require_workspace_access(current_user.id, workspace_id)
    rows = await service.list_workspace_members(workspace_id=workspace_id)
    return [
        WorkspaceMember(
            id=row.id,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.role,
            email=row.email,
            name=row.name,
            created_at=row.created_at,
            source=row.source,
        )
        for row in rows
    ]


async def _find_workspace_member(
    service: WorkspaceService, *, workspace_id: str, user_id: str
) -> WorkspaceMemberRecord | None:
    """Existing membership row, for resending an invite to a current member."""
    members = await service.list_workspace_members(workspace_id=workspace_id)
    return next((m for m in members if m.user_id == user_id), None)


@router.post("/{workspace_id}/members/invite")
async def invite_workspace_member(
    workspace_id: str,
    invite: WorkspaceMemberInvite,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService | None = Depends(_get_email_service),
) -> dict[str, object]:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can invite members")

    email = invite.email.lower().strip()
    await check_rate_limit(
        get_rate_limit_identifier(request, current_user.id),
        "/api/workspaces/members/invite",
    )
    await check_rate_limit(f"email:{email}", "/api/workspaces/members/invite")
    _user, user_created = await auth_service.ensure_user_for_invite(email, name=invite.name)

    already_member = False
    try:
        member = await service.invite_workspace_member(
            workspace_id=workspace_id,
            email=email,
            role=invite.role,
        )
    except WorkspaceMemberAlreadyExistsError as exc:
        # Re-inviting is how an admin resends an invite that never arrived, so
        # keep the membership as-is and fall through to issue a fresh challenge
        # rather than rejecting the only retry path they have.
        member = await _find_workspace_member(
            service, workspace_id=workspace_id, user_id=exc.user_id
        )
        if member is None:
            raise HTTPException(status_code=400, detail="User is already a member") from exc
        already_member = True

    if member is None:
        raise HTTPException(status_code=500, detail="Failed to create or find user for invite")

    # The organization is the people directory (Org > Users): make sure someone
    # invited straight into a workspace shows up there too.
    workspace = await service.get_workspace(workspace_id=workspace_id)
    if workspace is not None and workspace.organization_id:
        try:
            await org_service.invite_member(
                org_id=workspace.organization_id,
                email=email,
                role="member",
                now=datetime.now(UTC).replace(tzinfo=None),
            )
        except OrganizationMemberAlreadyExistsError:
            pass

    sign_in_email_sent = await issue_and_send_invite_sign_in(
        auth_service,
        email,
        email_service=email_service or _get_email_service(request),
    )

    return {
        "status": "already_member" if already_member else "invited",
        "member_id": member.id,
        "user_created": user_created,
        "sign_in_email_sent": sign_in_email_sent,
    }


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can remove members")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    removed = await service.remove_workspace_member(workspace_id=workspace_id, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "removed"}


@router.patch("/{workspace_id}/members/{user_id}")
async def update_workspace_member(
    workspace_id: str,
    user_id: str,
    updates: dict,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can update members")
    if "role" in updates:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        workspace = await service.get_workspace(workspace_id=workspace_id)
        if workspace is not None and workspace.owner_id == user_id:
            raise HTTPException(status_code=400, detail="Cannot change the workspace owner role")

    changed = await service.update_workspace_member(
        workspace_id=workspace_id,
        user_id=user_id,
        updates=updates,
    )
    if updates.get("role") in ["admin", "member", "viewer"] and not changed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "updated"}


@router.get("/{workspace_id}/servers")
async def list_inference_servers(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[InferenceServer]:
    await require_workspace_access(current_user.id, workspace_id)
    servers = await service.list_inference_servers(workspace_id=workspace_id)
    return [InferenceServer(**server.__dict__) for server in servers]


@router.post("/{workspace_id}/servers")
async def create_inference_server(
    workspace_id: str,
    server_data: InferenceServerCreate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> InferenceServer:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can add servers")

    server = await service.create_inference_server(
        workspace_id=workspace_id,
        name=server_data.name,
        server_type=server_data.type,
        endpoint=server_data.endpoint,
        description=server_data.description,
        enabled=server_data.enabled,
        api_key=deprecated_encrypt(server_data.api_key) if server_data.api_key else None,
        health_path=server_data.health_path,
        models_path=server_data.models_path,
    )
    return InferenceServer(**server.__dict__)


@router.patch("/{workspace_id}/servers/{server_id}")
async def update_inference_server(
    workspace_id: str,
    server_id: str,
    updates: InferenceServerUpdate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> InferenceServer:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can update servers")

    api_key = None
    if updates.api_key is not None:
        api_key = deprecated_encrypt(updates.api_key) if updates.api_key else None

    server = await service.update_inference_server(
        workspace_id=workspace_id,
        server_id=server_id,
        name=updates.name,
        endpoint=updates.endpoint,
        description=updates.description,
        enabled=updates.enabled,
        api_key=api_key,
        health_path=updates.health_path,
        models_path=updates.models_path,
    )
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    return InferenceServer(**server.__dict__)


@router.delete("/{workspace_id}/servers/{server_id}")
async def delete_inference_server(
    workspace_id: str,
    server_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can delete servers")

    deleted = await service.delete_inference_server(workspace_id=workspace_id, server_id=server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"status": "deleted"}


UPLOAD_DIR = Path("uploads/logos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_FILE_SIZE = 5 * 1024 * 1024


LOGO_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


@router.post("/{workspace_id}/upload-logo")
async def upload_workspace_logo(
    workspace_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    """Store the logo in the workspace drive (``logo_store``); the previous one is archived."""
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can upload logos")

    workspace = await service.get_workspace(workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    saved = logo_store.save_logo(object_storage, workspace_id, content, ext, datetime.now(UTC))
    logo_url = logo_store.logo_url(workspace_id, saved.digest)
    if logo_url != workspace.logo_url:
        updated_workspace = await service.update_workspace_logo(
            workspace_id=workspace_id, logo_url=logo_url
        )
        if updated_workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        _delete_legacy_logo(workspace.logo_url)

    return {"logo_url": logo_url, "filename": saved.key, "changed": saved.changed}


@router.get("/{workspace_id}/logo")
async def get_workspace_logo(
    workspace_id: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    """The workspace logo from its drive. Public: ``<img>`` tags cannot send a bearer token."""
    if not is_safe_drive_id(workspace_id):
        raise HTTPException(status_code=404, detail="Logo not found")
    stored = logo_store.read_logo(object_storage, workspace_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    headers = {"Cache-Control": "private, max-age=86400"}
    if stored.extension == ".svg":
        # An uploaded SVG must never run script on our origin.
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        headers["X-Content-Type-Options"] = "nosniff"
    return Response(
        content=stored.content,
        media_type=LOGO_MIME_TYPES.get(stored.extension, "application/octet-stream"),
        headers=headers,
    )


@router.delete("/{workspace_id}/logo")
async def remove_workspace_logo(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    """Archive the logo in the workspace drive and clear it."""
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can remove logos")
    workspace = await service.get_workspace(workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await service.update_workspace_logo(workspace_id=workspace_id, logo_url=None)
    logo_store.remove_logo(object_storage, workspace_id, datetime.now(UTC))
    _delete_legacy_logo(workspace.logo_url)
    return {"status": "ok"}


def _delete_legacy_logo(previous: str | None) -> None:
    """Logos from before the drive layout lived on local disk under uploads/logos/."""
    if previous and previous.startswith("/uploads/logos/"):
        (UPLOAD_DIR / os.path.basename(previous)).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Home desk wallpaper (workspace drive .home/): stage → preview → commit.
# ---------------------------------------------------------------------------


class BackgroundImageDraft(BaseModel):
    draft: str


class BackgroundImageCurrent(BaseModel):
    background_image_url: str


class BackgroundImageCommit(BaseModel):
    """What to show and how: a new ``draft``, or the ``current`` wallpaper
    re-framed. Plus the framing set in the preview (focal point %, zoom)."""

    draft: str | None = None
    current: str | None = None
    x: float = Field(default=50.0, ge=0, le=100)
    y: float = Field(default=50.0, ge=0, le=100)
    zoom: float = Field(default=MIN_ZOOM, ge=MIN_ZOOM, le=MAX_ZOOM)


async def _require_workspace_admin(user: User, workspace_id: str) -> str:
    role = await require_workspace_access(user.id, workspace_id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can change the background image")
    return role


def _image_response(raw, *, cache: str) -> Response:
    return Response(
        content=raw.content,
        media_type=raw.media_type,
        headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{workspace_id}/background-image/draft")
async def stage_background_image(
    workspace_id: str,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None, max_length=2048),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> BackgroundImageDraft:
    """Upload a local file or download ``url`` into ``.home/tmp`` for preview."""
    await _require_workspace_admin(current_user, workspace_id)
    if (file is None) == (not url):
        raise HTTPException(status_code=400, detail="Send either a file or a url")
    background = WorkspaceBackgroundImage(files_service, workspace_id)
    try:
        if file is not None:
            content = await file.read(MAX_BACKGROUND_IMAGE_BYTES + 1)
        else:
            content = await fetch_image_url(url or "")
        draft = background.stage(content)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # network errors from the remote host
        if url and file is None:
            raise HTTPException(status_code=400, detail="Could not download the image") from exc
        raise
    return BackgroundImageDraft(draft=draft)


@router.get("/{workspace_id}/background-image/draft/{name}")
async def preview_background_image_draft(
    workspace_id: str,
    name: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> Response:
    await _require_workspace_admin(current_user, workspace_id)
    try:
        raw = WorkspaceBackgroundImage(files_service, workspace_id).read_draft(name)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _image_response(raw, cache="no-store")


@router.delete("/{workspace_id}/background-image/draft")
async def discard_background_image_draft(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> dict:
    await _require_workspace_admin(current_user, workspace_id)
    WorkspaceBackgroundImage(files_service, workspace_id).discard()
    return {"message": "Draft discarded"}


@router.post("/{workspace_id}/background-image")
async def commit_background_image(
    workspace_id: str,
    payload: BackgroundImageCommit,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    files_service: FilesService = Depends(get_files_service),
) -> Workspace:
    """Point the workspace at the new draft (moved to ``.home/background-img``, old
    files cleaned up) or at the current wallpaper with new framing."""
    role = await _require_workspace_admin(current_user, workspace_id)
    if (payload.draft is None) == (payload.current is None):
        raise HTTPException(status_code=400, detail="Send either a draft or the current image")
    background = WorkspaceBackgroundImage(files_service, workspace_id)
    try:
        if payload.draft is not None:
            name = background.commit(payload.draft)
        else:
            # Re-framing the wallpaper already in place: nothing moves.
            name = payload.current or ""
            background.read_current(name)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = await service.update_workspace(
        workspace_id=workspace_id,
        updates=WorkspaceUpdateInput(
            background_image_url=background_image_url(
                workspace_id, name, x=payload.x, y=payload.y, zoom=payload.zoom
            )
        ),
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_schema(
        record,
        role,
        organization_override=await _load_org_role_override(record.organization_id, org_service),
    )


@router.delete("/{workspace_id}/background-image")
async def remove_background_image(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    files_service: FilesService = Depends(get_files_service),
) -> Workspace:
    """Remove the desk wallpaper: the file moves to ``.home/archives``, the pointer is cleared."""
    role = await _require_workspace_admin(current_user, workspace_id)
    WorkspaceBackgroundImage(files_service, workspace_id).remove(datetime.now(UTC))
    record = await service.update_workspace(
        workspace_id=workspace_id,
        updates=WorkspaceUpdateInput(background_image_url=""),
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_schema(
        record,
        role,
        organization_override=await _load_org_role_override(record.organization_id, org_service),
    )


@router.get("/{workspace_id}/background-image/current")
async def get_current_background_image(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    files_service: FilesService = Depends(get_files_service),
) -> BackgroundImageCurrent:
    """The wallpaper the home desk should show.

    The URL on the workspace row is the pointer. When that pointer is empty
    but a file is still committed under ``.home/background-img`` (a restart
    used to clear the column), point the workspace at the file again.
    """
    await require_workspace_access(current_user.id, workspace_id)
    record = await service.get_workspace(workspace_id=workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if record.background_image_url:
        return BackgroundImageCurrent(background_image_url=record.background_image_url)
    name = WorkspaceBackgroundImage(files_service, workspace_id).current_name()
    if not name:
        raise HTTPException(status_code=404, detail="No background image")
    url = background_image_url(workspace_id, name)
    await service.update_workspace(
        workspace_id=workspace_id,
        updates=WorkspaceUpdateInput(background_image_url=url),
    )
    return BackgroundImageCurrent(background_image_url=url)


@router.get("/{workspace_id}/background-image")
async def get_background_image(
    workspace_id: str,
    v: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> Response:
    """The committed wallpaper. ``v`` is its file name, so the URL changes on every commit."""
    await require_workspace_access(current_user.id, workspace_id)
    try:
        raw = WorkspaceBackgroundImage(files_service, workspace_id).read_current(v)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _image_response(raw, cache="private, max-age=31536000, immutable")
