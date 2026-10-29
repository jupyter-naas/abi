from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import deprecated_encrypt
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    enabled_feature_catalog,
    offered_features,
)
from naas_abi.apps.nexus.apps.api.app.core.workspace_config_seeds import workspace_seed_rows
from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import catalog_seed_rows
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    seed_workspace_agents,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (
    _get_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    is_safe_drive_id,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.iam import authz, placements, user_features
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    ROLE_NAMES,
    MembershipDenied,
    UnknownUserError,
)
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.mail import send_added_notice
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    NoProviderError,
    OrgInvitationExistsError,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.views import (
    PROVIDER_FAILURES,
    invite_result,
    provider_failure,
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
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
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
    new_workspace_id,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    LastOwnerError,
    WorkspaceMemberAlreadyExistsError,
    WorkspaceService,
    WorkspaceSlugAlreadyExistsError,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import (
    resolve_stored_asset_url,
)
from naas_abi_core import logger
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
router.include_router(resource_access_router)


def _member_denied(role: str) -> HTTPException:
    """IAM refused a change of roles: the owner role is the owner's alone (bug c)."""
    if role == "owner":
        return HTTPException(
            status_code=403, detail="Only owners can grant, change or remove an owner"
        )
    return HTTPException(status_code=403, detail="You do not have permission to change this member")


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


class WorkspaceCatalogSeedInput(BaseModel):
    default_agent: str | None = None
    agents: list[str] | None = None
    apps: list[str] | None = None
    ontologies: list[str] | None = None
    maps: dict[str, Any] | None = None


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    organization_id: str | None = None
    owner_id: str | None = None
    catalog_seed: WorkspaceCatalogSeedInput | None = None
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
    owner_id: str | None = None
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
    role: str = Field(default="member", pattern=r"^(owner|admin|member|viewer)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # The identity provider to invite through; by default the one the email's
    # domain routes to, else the default provider.
    provider: str | None = Field(default=None, min_length=1, max_length=32)
    # Customer policies the new member gets at this workspace beside the role
    # (no role brings a feature: "Features of member", say).
    policy_ids: list[str] = Field(default_factory=list, max_length=20)


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


def _workspace_public_asset_url(raw: str | None) -> str | None:
    """Rewrite module asset paths (``src/external/…/assets/public/…``) to API URLs."""
    return resolve_stored_asset_url(raw)


async def _feature_flags(
    user: Any, records: list[WorkspaceRecord]
) -> dict[str, dict[str, bool]] | None:
    """What the user may use in each workspace: IAM's ``UseFeature`` (the
    policies granting features); None without IAM."""
    return await user_features.user_feature_flags(
        user,
        [(r.organization_id, r.id) for r in records],
        enabled_feature_catalog(settings.feature_flags),
    )


def _to_schema(
    record: WorkspaceRecord,
    current_user_role: str | None,
    *,
    feature_flags: dict[str, bool] | None = None,
) -> Workspace:
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
        # No role brings a feature: without IAM's answer, none is shown.
        feature_flags=feature_flags
        if feature_flags is not None
        else dict.fromkeys(KNOWN_FEATURE_KEYS, False),
    )


@router.get("", dependencies=[declares("ListWorkspaces")])
async def list_workspaces(
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> list[Workspace]:
    rows = await service.list_workspaces(user_id=current_user.id)
    roles = await service.effective_roles(current_user.id, rows)
    flags = await _feature_flags(current_user, list(rows)) or {}
    return [
        _to_schema(
            row,
            role,
            feature_flags=flags.get(row.id),
        )
        for row, role in zip(rows, roles, strict=False)
    ]


@router.get("/{workspace_id}", dependencies=[guard("GetWorkspace")])
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    role = await service.get_workspace_role(current_user.id, workspace_id)
    row = await service.get_workspace(workspace_id=workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    flags = await _feature_flags(current_user, [row]) or {}
    return _to_schema(
        row,
        role,
        feature_flags=flags.get(row.id),
    )


@router.get("/slug/{slug}", dependencies=[declares("GetWorkspace")])
async def get_workspace_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    row = await service.get_workspace_by_slug(slug=slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # The slug names the workspace: a caller who cannot see it learns nothing of it.
    await authz.require("GetWorkspace", user=current_user, workspace=row.id)
    role = await service.get_workspace_role(current_user.id, row.id)
    flags = await _feature_flags(current_user, [row]) or {}
    return _to_schema(
        row,
        role,
        feature_flags=flags.get(row.id),
    )


async def _undo_create(service: WorkspaceService, record: WorkspaceRecord) -> None:
    """Remove a workspace whose creation failed half-way: its placements, then
    its uncommitted row and its IAM container (and so its attachments)."""
    try:
        await placements.forget_workspace(record.id)
    except Exception:  # noqa: BLE001 - the original failure is what is raised
        logger.exception(f"Could not forget the placements of workspace {record.id}")
    try:
        await service.abandon_workspace(record)
    except Exception:  # noqa: BLE001 - the original failure is what is raised
        logger.exception(f"Could not remove workspace {record.id} after a failed create")


@router.post("", dependencies=[declares("CreateWorkspace")])
async def create_workspace(
    workspace: WorkspaceCreate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    registry: ServiceRegistry = Depends(get_service_registry),
) -> Workspace:
    # The create is checked on the new workspace's own name, in the organization
    # the body names (never taken on its say-so): only the organization's owners
    # and admins add workspaces to it. A workspace without one is the caller's
    # personal workspace, at the platform, which every user may create.
    workspace_id = new_workspace_id()
    await authz.require(
        "CreateWorkspace",
        user=current_user,
        org=workspace.organization_id or None,
        id=workspace_id,
        denied="Only organization owners and admins can create workspaces",
    )
    owner_id = workspace.owner_id or current_user.id
    if not workspace.organization_id and owner_id != current_user.id:
        raise HTTPException(
            status_code=400, detail="A personal workspace belongs to the user who creates it"
        )
    if workspace.organization_id and owner_id != current_user.id:
        member_role = await org_service.get_organization_role(
            user_id=owner_id, org_id=workspace.organization_id
        )
        if member_role is None:
            raise HTTPException(
                status_code=400,
                detail="Workspace owner must be a member of the organization",
            )
    catalog_seed = (
        workspace.catalog_seed.model_dump(exclude_none=True)
        if workspace.catalog_seed is not None
        else None
    )
    try:
        record = await service.create_workspace(
            WorkspaceCreateInput(
                name=workspace.name,
                slug=workspace.slug,
                owner_id=owner_id,
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
                catalog_seed=catalog_seed,
                id=workspace_id,
            )
        )
    except WorkspaceSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Slug already exists") from exc
    except UnknownUserError as exc:
        raise HTTPException(status_code=400, detail="Workspace owner is not a known user") from exc
    # What IAM derives from the new workspace: the kernel resources its roles
    # reach (drives, caches, drafts). Failing undoes the workspace: never
    # placements without it. Its catalog seed installs; it grants nothing.
    try:
        await service.adapter.db.flush()
        await placements.place_new_workspace(service.adapter.db, record.id)
    except Exception as exc:
        await _undo_create(service, record)
        if isinstance(exc, iam_runtime.IAMUnavailableError):
            raise HTTPException(status_code=503, detail="Access control is unavailable") from exc
        raise
    await seed_workspace_agents(
        workspace_id=record.id,
        current_user=current_user,
        agent_service=registry.agents,
    )
    flags = await _feature_flags(current_user, [record]) or {}
    return _to_schema(
        record,
        "owner",
        feature_flags=flags.get(record.id),
    )


@router.delete(
    "/{workspace_id}",
    dependencies=[
        guard("DeleteWorkspace", denied="Only the workspace owner can delete the workspace")
    ],
)
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    deleted = await service.delete_workspace(workspace_id=workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}


# Drives reach beyond the workspace: the system drive is the whole object store
# and the platform drive is shared by every workspace. Anyone can create and own
# a workspace, so only a platform superadmin may flip these.
_DRIVE_FLAGS = frozenset({"platform_drive_enabled", "system_drive_enabled"})


@router.patch(
    "/{workspace_id}",
    dependencies=[guard("UpdateWorkspace", denied="Only admins can update workspace settings")],
)
async def update_workspace(
    workspace_id: str,
    updates: WorkspaceUpdate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    changes = updates.model_dump(exclude_unset=True)
    if changes.keys() & _DRIVE_FLAGS and not current_user.is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a platform superadmin can enable or disable workspace drives",
        )
    role = await service.get_workspace_role(current_user.id, workspace_id)

    if "owner_id" in changes:
        existing = await service.get_workspace(workspace_id=workspace_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if existing.organization_id:
            member_role = await org_service.get_organization_role(
                user_id=changes["owner_id"], org_id=existing.organization_id
            )
            if member_role is None:
                raise HTTPException(
                    status_code=400,
                    detail="Workspace owner must be a member of the organization",
                )

    try:
        record = await service.update_workspace(
            workspace_id=workspace_id,
            updates=WorkspaceUpdateInput(**changes),
            by=current_user,
        )
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc
    except UnknownUserError as exc:
        raise HTTPException(status_code=400, detail="Workspace owner is not a known user") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    flags = await _feature_flags(current_user, [record]) or {}
    return _to_schema(
        record,
        role,
        feature_flags=flags.get(record.id),
    )


@router.get(
    "/{workspace_id}/configuration",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def get_workspace_configuration(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> dict:
    """Features and config preseeding (Settings > General).

    ``seeds`` lists what ``nexus_config.organizations[].workspaces[]`` preloads
    for this workspace slug, read from the loaded config on each call.
    ``features`` are the deployment's enabled ones; who uses each is a policy's
    (Roles & permissions).
    """
    record = await service.get_workspace(workspace_id=workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "organization_id": record.organization_id,
        "features": offered_features(settings.feature_flags),
        "seeds": catalog_seed_rows(record.catalog_seed)
        + workspace_seed_rows(settings.organizations, record.slug),
    }


@router.get(
    "/{workspace_id}/resources",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view what the workspace has",
        )
    ],
)
async def get_workspace_resources(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """What the caller may use in the workspace, as IAM decides it, for
    workspace settings (which pages it shows, General).

    ``features`` are the deployment's enabled features the caller holds there
    (``nexus:UseFeature``); ``modules`` each module with something the caller
    may use there, with how many of its agents, apps, workflows and pipelines
    (``authz.filter_scopes``); ``totals`` add them up, and ``unavailable`` names
    the kinds a source did not answer for (discovery, the jobs), whose totals
    may be short."""
    from naas_abi.apps.nexus.apps.api.app.services.modules import scopes as module_scopes

    record = await service.get_workspace(workspace_id=workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    unavailable: set[str] = set()
    gathered = await module_scopes.gather(unavailable)
    usable = set(
        await authz.filter_scopes(
            module_scopes.item_scopes(gathered),
            user=current_user,
            workspace=workspace_id,
            scope_of=lambda scope: scope,
        )
    )
    modules = module_scopes.counted(gathered, usable)
    flags = (await _feature_flags(current_user, [record]) or {}).get(record.id, {})
    return {
        "organization_id": record.organization_id,
        "features": [
            key for key in enabled_feature_catalog(settings.feature_flags) if flags.get(key)
        ],
        "modules": modules,
        "totals": {
            plural: sum(entry[plural] for entry in modules)
            for plural in module_scopes.PLURAL.values()
        },
        # Kinds a source did not answer for: their totals may be short.
        "unavailable": sorted(unavailable),
    }


@router.get("/{workspace_id}/stats", dependencies=[guard("GetWorkspaceStats")])
async def get_workspace_stats(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, Any]:
    stats = await service.get_workspace_stats(workspace_id=workspace_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "nodes": stats.nodes,
        "edges": stats.edges,
        "conversations": stats.conversations,
        "agents": stats.agents,
    }


@router.get("/{workspace_id}/members", dependencies=[guard("ListWorkspaceMembers", literal="-")])
async def list_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceMember]:
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


@router.post(
    "/{workspace_id}/members/invite",
    dependencies=[
        guard("InviteWorkspaceMember", literal="-", denied="Only admins can invite members")
    ],
)
async def invite_workspace_member(
    workspace_id: str,
    invite: WorkspaceMemberInvite,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    email_service: EmailService | None = Depends(_get_email_service),
    invites: InvitationService = Depends(invites_runtime.get_invitation_service),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    email = invite.email.lower().strip()
    await check_rate_limit(
        get_rate_limit_identifier(request, current_user.id),
        "/api/workspaces/members/invite",
    )
    await check_rate_limit(f"email:{email}", "/api/workspaces/members/invite")

    # Someone with no account yet is invited through an identity provider (see
    # the organization invite); someone who has one is added directly.
    existing_user = await invites.persistence.user_id_by_email(email)
    if existing_user is None:
        workspace = await service.get_workspace(workspace_id)
        organization = (
            await get_organization_service(db).get_organization(workspace.organization_id)
            if workspace is not None and workspace.organization_id
            else None
        )
        try:
            outcome = await invites.invite(
                email=email,
                name=invite.name,
                provider=invite.provider,
                organization_id=workspace.organization_id if workspace else None,
                org_role=None,
                workspace_id=workspace_id,
                workspace_role=invite.role,
                invited_by=current_user.id,
                inviter_name=current_user.name,
                organization_name=organization.name if organization else None,
                workspace_name=workspace.name if workspace else None,
                policy_ids=invite.policy_ids,
                may_renew_org_invitation=bool(
                    workspace is not None
                    and workspace.organization_id
                    and await authz.allowed(
                        "InviteOrganizationMember",
                        user=current_user,
                        org=workspace.organization_id,
                        id="-",
                    )
                ),
            )
        except OrgInvitationExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except NoProviderError as exc:
            # Nobody is signed up here: without an identity provider there is
            # nowhere for the person to sign in.
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PROVIDER_FAILURES as exc:
            raise provider_failure(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return invite_result(outcome)

    workspace = await service.get_workspace(workspace_id)
    # The policies the invitation carries, checked and attached as the inviting
    # person before anything is made (IAM refuses one they may not attach or do
    # not hold): a refusal leaves no membership behind.
    carried: tuple[str, ...] = ()
    if invite.policy_ids:
        try:
            carried = await invites.attach_policies(
                user_id=existing_user,
                organization_id=workspace.organization_id if workspace else None,
                workspace_id=workspace_id,
                policy_ids=invite.policy_ids,
                by=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    already_member = False
    try:
        member = await service.invite_workspace_member(
            workspace_id=workspace_id,
            email=email,
            role=invite.role,
            by=current_user,
        )
    except MembershipDenied as exc:
        if carried:
            await invites.detach_policies(
                user_id=existing_user,
                organization_id=workspace.organization_id if workspace else None,
                workspace_id=workspace_id,
                policy_ids=carried,
            )
        raise _member_denied(str(exc)) from exc
    except WorkspaceMemberAlreadyExistsError as exc:
        # Re-inviting is how an admin resends the notice that never arrived, so
        # keep the membership as-is and send it again rather than rejecting the
        # only retry path they have.
        member = await _find_workspace_member(
            service, workspace_id=workspace_id, user_id=exc.user_id
        )
        if member is None:
            raise HTTPException(status_code=400, detail="User is already a member") from exc
        already_member = True

    if member is None:
        raise HTTPException(status_code=500, detail="Failed to create or find user for invite")

    # The organization is the people directory (Org > Users): someone added
    # straight into a workspace shows up there too, as a member. Done as ``api``
    # for no user, after the workspace-level check above.
    if workspace is not None and workspace.organization_id:
        try:
            await org_service.invite_member(
                org_id=workspace.organization_id,
                email=email,
                role="member",
                now=datetime.now(UTC).replace(tzinfo=None),
                by=None,
            )
        except OrganizationMemberAlreadyExistsError:
            pass

    sign_in_email_sent = await send_added_notice(
        email,
        inviter_name=current_user.name,
        workspace_name=workspace.name if workspace else None,
        workspace_role=invite.role,
        email_service=email_service or _get_email_service(request),
    )

    return {
        "status": "already_member" if already_member else "invited",
        "member_id": member.id,
        "user_created": False,
        "sign_in_email_sent": sign_in_email_sent,
    }


@router.delete(
    "/{workspace_id}/members/{user_id}",
    dependencies=[
        guard("RemoveWorkspaceMember", id="user_id", denied="Only admins can remove members")
    ],
)
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    try:
        removed = await service.remove_workspace_member(
            workspace_id=workspace_id, user_id=user_id, by=current_user
        )
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=400, detail="A workspace needs an owner") from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "removed"}


@router.patch(
    "/{workspace_id}/members/{user_id}",
    dependencies=[
        guard("UpdateWorkspaceMember", id="user_id", denied="Only admins can update members")
    ],
)
async def update_workspace_member(
    workspace_id: str,
    user_id: str,
    updates: dict,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    if "role" in updates and user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    try:
        changed = await service.update_workspace_member(
            workspace_id=workspace_id,
            user_id=user_id,
            updates=updates,
            by=current_user,
        )
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=400, detail="A workspace needs an owner") from exc
    if updates.get("role") in ROLE_NAMES and not changed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "updated"}


@router.get("/{workspace_id}/servers", dependencies=[guard("ListServers", literal="-")])
async def list_inference_servers(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[InferenceServer]:
    servers = await service.list_inference_servers(workspace_id=workspace_id)
    return [InferenceServer(**server.__dict__) for server in servers]


@router.post(
    "/{workspace_id}/servers",
    dependencies=[guard("CreateServer", literal="-", denied="Only admins can add servers")],
)
async def create_inference_server(
    workspace_id: str,
    server_data: InferenceServerCreate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> InferenceServer:
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


@router.patch(
    "/{workspace_id}/servers/{server_id}",
    dependencies=[guard("UpdateServer", id="server_id", denied="Only admins can update servers")],
)
async def update_inference_server(
    workspace_id: str,
    server_id: str,
    updates: InferenceServerUpdate,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> InferenceServer:
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


@router.delete(
    "/{workspace_id}/servers/{server_id}",
    dependencies=[guard("DeleteServer", id="server_id", denied="Only admins can delete servers")],
)
async def delete_inference_server(
    workspace_id: str,
    server_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
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


@router.post(
    "/{workspace_id}/upload-logo",
    dependencies=[guard("UpdateWorkspaceTheme", denied="Only admins can upload logos")],
)
async def upload_workspace_logo(
    workspace_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    """Store the logo in the workspace drive (``logo_store``); the previous one is archived."""
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
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
        headers["X-Content-Type-Options"] = "nosniff"
    return Response(
        content=stored.content,
        media_type=LOGO_MIME_TYPES.get(stored.extension, "application/octet-stream"),
        headers=headers,
    )


@router.delete(
    "/{workspace_id}/logo",
    dependencies=[guard("UpdateWorkspaceTheme", denied="Only admins can remove logos")],
)
async def remove_workspace_logo(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    """Archive the logo in the workspace drive and clear it."""
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
    # None when the workspace has no wallpaper.
    background_image_url: str | None = None


class BackgroundImageCommit(BaseModel):
    """What to show and how: a new ``draft``, or the ``current`` wallpaper
    re-framed. Plus the framing set in the preview (focal point %, zoom)."""

    draft: str | None = None
    current: str | None = None
    x: float = Field(default=50.0, ge=0, le=100)
    y: float = Field(default=50.0, ge=0, le=100)
    zoom: float = Field(default=MIN_ZOOM, ge=MIN_ZOOM, le=MAX_ZOOM)


_BACKGROUND_DENIED = "Only admins can change the background image"


def _image_response(raw, *, cache: str) -> Response:
    return Response(
        content=raw.content,
        media_type=raw.media_type,
        headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/{workspace_id}/background-image/draft",
    dependencies=[guard("UpdateWorkspaceTheme", denied=_BACKGROUND_DENIED)],
)
async def stage_background_image(
    workspace_id: str,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None, max_length=2048),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> BackgroundImageDraft:
    """Upload a local file or download ``url`` into ``.home/tmp`` for preview."""
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


@router.get(
    "/{workspace_id}/background-image/draft/{name}",
    dependencies=[guard("UpdateWorkspaceTheme", denied=_BACKGROUND_DENIED)],
)
async def preview_background_image_draft(
    workspace_id: str,
    name: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> Response:
    try:
        raw = WorkspaceBackgroundImage(files_service, workspace_id).read_draft(name)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _image_response(raw, cache="no-store")


@router.delete(
    "/{workspace_id}/background-image/draft",
    dependencies=[guard("UpdateWorkspaceTheme", denied=_BACKGROUND_DENIED)],
)
async def discard_background_image_draft(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> dict:
    WorkspaceBackgroundImage(files_service, workspace_id).discard()
    return {"message": "Draft discarded"}


@router.post(
    "/{workspace_id}/background-image",
    dependencies=[guard("UpdateWorkspaceTheme", denied=_BACKGROUND_DENIED)],
)
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
    role = await service.get_workspace_role(current_user.id, workspace_id)
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
        feature_flags=(await _feature_flags(current_user, [record]) or {}).get(record.id),
    )


@router.delete(
    "/{workspace_id}/background-image",
    dependencies=[guard("UpdateWorkspaceTheme", denied=_BACKGROUND_DENIED)],
)
async def remove_background_image(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
    files_service: FilesService = Depends(get_files_service),
) -> Workspace:
    """Remove the desk wallpaper: the file moves to ``.home/archives``, the pointer is cleared."""
    role = await service.get_workspace_role(current_user.id, workspace_id)
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
        feature_flags=(await _feature_flags(current_user, [record]) or {}).get(record.id),
    )


@router.get("/{workspace_id}/background-image/current", dependencies=[guard("GetWorkspace")])
async def get_current_background_image(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    files_service: FilesService = Depends(get_files_service),
) -> BackgroundImageCurrent:
    """The wallpaper the home desk should show.

    The URL on the workspace row is the pointer. When that pointer is empty
    but a file is still committed under ``.home/background-img`` (a restart
    used to clear the column), point the workspace at the file again. No
    wallpaper at all is ``background_image_url: null``, not a 404.
    """
    record = await service.get_workspace(workspace_id=workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if record.background_image_url:
        return BackgroundImageCurrent(background_image_url=record.background_image_url)
    name = WorkspaceBackgroundImage(files_service, workspace_id).current_name()
    if not name:
        return BackgroundImageCurrent(background_image_url=None)
    url = background_image_url(workspace_id, name)
    await service.update_workspace(
        workspace_id=workspace_id,
        updates=WorkspaceUpdateInput(background_image_url=url),
    )
    return BackgroundImageCurrent(background_image_url=url)


@router.get("/{workspace_id}/background-image", dependencies=[guard("GetWorkspace")])
async def get_background_image(
    workspace_id: str,
    v: str,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
) -> Response:
    """The committed wallpaper. ``v`` is its file name, so the URL changes on every commit."""
    try:
        raw = WorkspaceBackgroundImage(files_service, workspace_id).read_current(v)
    except BackgroundImageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _image_response(raw, cache="private, max-age=31536000, immutable")
