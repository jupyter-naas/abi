from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    get_workspace_role,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import deprecated_encrypt
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
    issue_and_send_invite_sign_in,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
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
    resolve_public_module_asset_url,
)
from naas_abi_core.services.email.EmailService import EmailService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


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
    if not raw:
        return raw
    if raw.startswith(("http://", "https://", "/uploads/")):
        return raw
    try:
        return resolve_public_module_asset_url(raw, abi_module_path=None)
    except Exception:
        return raw


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
    overrides = await _load_org_role_overrides(
        [row.organization_id for row in rows], org_service
    )
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
            )
        )
    except WorkspaceSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Slug already exists") from exc
    return _to_schema(
        record,
        "owner",
        organization_override=await _load_org_role_override(
            record.organization_id, org_service
        ),
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
        organization_override=await _load_org_role_override(
            record.organization_id, org_service
        ),
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


@router.post("/{workspace_id}/upload-logo")
async def upload_workspace_logo(
    workspace_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
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
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    unique_filename = f"{workspace_id}-{os.urandom(4).hex()}{ext}"
    file_path = UPLOAD_DIR / unique_filename
    with open(file_path, "wb") as file_handle:
        file_handle.write(content)

    logo_url = f"/uploads/logos/{unique_filename}"
    updated_workspace = await service.update_workspace_logo(
        workspace_id=workspace_id, logo_url=logo_url
    )
    if updated_workspace is None:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.logo_url and workspace.logo_url.startswith("/uploads/logos/"):
        old_file = UPLOAD_DIR / os.path.basename(workspace.logo_url)
        old_file.unlink(missing_ok=True)

    return {
        "logo_url": logo_url,
        "filename": unique_filename,
    }
