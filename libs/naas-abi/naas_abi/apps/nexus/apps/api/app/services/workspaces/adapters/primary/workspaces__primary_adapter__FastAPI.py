from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
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
    MEMBERSHIPS,
    ROLE_NAMES,
    MembershipDenied,
    UnknownUserError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.roles import (
    KEEP,
    ROLES_BATCH_MAX,
    HeldRolesView,
    MemberRolesInput,
    RoleChange,
    RoleOptionsView,
    RoleRefView,
    change_roles,
    held_roles,
    role_groups_of,
    role_options,
    roles_of_batch,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    RESEND_LIMIT,
    check_invitation_mail_quota,
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
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
    PeopleServicePort,
    UserStatus,
    added_result,
    capability_group_items,
    get_people_service,
    people_errors,
    people_status,
    workspace_grant,
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
    WorkspaceService,
    WorkspaceSlugAlreadyExistsError,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import (
    resolve_stored_asset_url,
)
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
router.include_router(resource_access_router)


# The workspace invite routes' counters (per inviting user, per address).
_INVITE_LIMIT = "/api/workspaces/members/invite"


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
    created_at: datetime | None = None
    updated_at: datetime | None = None
    organization_name: str | None = None
    organization_slug: str | None = None
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
    # The workspace's first admin (#1585): joins "<W> admins" and "<W> workspace".
    # Defaults to the creator; in an organization, one of its people.
    admin_id: str | None = None
    # Deprecated: read as ``admin_id`` when that is not given (owner is no longer
    # assigned).
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


class MemberRoleView(BaseModel):
    """A group the member is in (``kind`` "group") or a policy attached to them
    (``kind`` "policy", at ``scope``), bearing on the workspace."""

    kind: str
    id: str
    name: str
    scope: str | None = None
    # The workspace's own group, shown for an admin who reaches it otherwise.
    implied: bool = False


class WorkspaceMember(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    source: str = "workspace"
    # Their IAM principal, which the access pages link to (an account linked from
    # the old login has another id there).
    principal_id: str | None = None
    # "invited" until their first sign-in, then "active".
    status: str = "active"
    # Workspace · Level (#1585): their level ("member", "viewer"), one choice for every
    # workspace; ``role`` "admin" when they administer this one. None: a role of
    # before, held directly.
    level: str | None = None
    # Users › Role: their groups and policies that bear on the workspace.
    roles: list[MemberRoleView] = Field(default_factory=list)
    # Users › Joined: for a membership made before IAM kept its date (or by the access
    # move itself), the access move's date: they joined before it (``created_at`` None).
    joined_before: datetime | None = None


class MemberProfileInput(BaseModel):
    """What the invite sets about the person in the workspace's organization."""

    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)


class WorkspaceAccessInput(BaseModel):
    """What a person is given in the workspace (#1589): their level (None: keep
    theirs; someone with none is a Member), whether they administer it, and the
    capability groups (ids) they join. ``role`` is the body of before, read when
    ``level`` and ``admin`` are absent (owner is refused)."""

    level: str | None = Field(default=None, pattern=r"^(viewer|member)$")
    admin: bool | None = None
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    role: str | None = Field(default=None, pattern=r"^(owner|admin|member|viewer)$")
    # Customer policies are no longer attached to a person (#1589): refused.
    policy_ids: list[str] = Field(default_factory=list, max_length=20)


class WorkspaceMemberInvite(WorkspaceAccessInput):
    email: str = Field(..., min_length=3, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # The identity provider to invite through; by default the one the email's
    # domain routes to, else the default provider.
    provider: str | None = Field(default=None, min_length=1, max_length=32)
    profile: MemberProfileInput | None = None


class WorkspaceMemberAdd(WorkspaceAccessInput):
    """Someone of the organization's directory, added to the workspace; ``notify``:
    and sent an invitation (Invite user's "Invite & send invitation")."""

    user_id: str = Field(..., min_length=1, max_length=255)
    notify: bool = True


class WorkspaceMemberChange(BaseModel):
    """A member's level (it applies in every workspace they work in) and whether
    they administer this workspace; ``role``, the body of before."""

    level: str | None = Field(default=None, pattern=r"^(viewer|member)$")
    admin: bool | None = None
    role: str | None = None


class WorkspaceMemberCandidate(BaseModel):
    user_id: str
    name: str | None = None
    email: str
    avatar: str | None = None
    status: str
    org_role: str | None = None


class WorkspaceMemberCandidates(BaseModel):
    items: list[WorkspaceMemberCandidate]


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
        created_at=record.created_at,
        updated_at=record.updated_at,
        organization_name=record.organization_name,
        organization_slug=record.organization_slug,
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
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> list[Workspace]:
    rows = await service.list_workspaces(user_id=current_user.id)
    view = getattr(request.state, "nexus_view", None)
    if view is not None:
        # A view (services/view_as) is of one workspace: the person's others are not part of it.
        rows = [row for row in rows if row.id == view.workspace_id]
    roles = await service.effective_roles(current_user.id, rows)
    flags = await _feature_flags(current_user, list(rows)) or {}
    return [
        _to_schema(row, role, feature_flags=flags.get(row.id))
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
    return _to_schema(row, role, feature_flags=flags.get(row.id))


@router.get("/slug/{slug}", dependencies=[declares("GetWorkspace")])
async def get_workspace_by_slug(
    slug: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    org_service: OrganizationService = Depends(get_organization_service),
) -> Workspace:
    row = await service.get_workspace_by_slug(slug=slug)
    view = getattr(request.state, "nexus_view", None)
    if row is None or (view is not None and row.id != view.workspace_id):
        # A view (services/view_as) is of one workspace: another is not found.
        raise HTTPException(status_code=404, detail="Workspace not found")
    # The slug names the workspace: a caller who cannot see it learns nothing of it.
    await authz.require("GetWorkspace", user=current_user, workspace=row.id)
    role = await service.get_workspace_role(current_user.id, row.id)
    flags = await _feature_flags(current_user, [row]) or {}
    return _to_schema(row, role, feature_flags=flags.get(row.id))


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
    # A workspace is created with an admin (#1585): the one named, else the creator.
    admin_id = workspace.admin_id or workspace.owner_id or current_user.id
    if not workspace.organization_id and admin_id != current_user.id:
        raise HTTPException(
            status_code=400, detail="A personal workspace belongs to the user who creates it"
        )
    if workspace.organization_id and admin_id != current_user.id:
        # One of the organization's people (its directory: its members and those
        # of its workspaces), never anyone of the platform.
        if not await org_service.in_directory(workspace.organization_id, admin_id):
            raise HTTPException(
                status_code=400,
                detail="The workspace admin must be a person of the organization",
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
                owner_id=admin_id,
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
        raise HTTPException(status_code=400, detail="Workspace admin is not a known user") from exc
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
    role = (
        "admin"
        if admin_id == current_user.id
        else await service.get_workspace_role(current_user.id, record.id)
    )
    return _to_schema(
        record,
        role,
        feature_flags=flags.get(record.id),
    )


@router.delete(
    "/{workspace_id}",
    dependencies=[declares("DeleteOrganizationWorkspace"), declares("DeleteWorkspace")],
)
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, str]:
    # Owner is no longer assigned (#1585): a workspace of an organization is deleted
    # by the organization's admins (DeleteOrganizationWorkspace, on the organization);
    # one in none by the platform admin (DeleteWorkspace, which no role holds).
    container = await authz.AUTHZ.container_of(workspace_id)
    if container is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    org_id = org_of(container)
    if org_id:
        await authz.require(
            "DeleteOrganizationWorkspace",
            user=current_user,
            org=org_id,
            denied="Only the organization's admins can delete its workspaces",
        )
    else:
        await authz.require(
            "DeleteWorkspace",
            user=current_user,
            workspace=workspace_id,
            denied="Only the platform administrators can delete this workspace",
        )
    deleted = await service.delete_workspace(workspace_id=workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}


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
    # The drive flags of earlier versions are gone: Platform Files and System Files are
    # IAM's (``GET /api/files/views``). An older client sending them is ignored.
    changes = updates.model_dump(exclude_unset=True)
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
    (General › Features writes one per feature, ``/feature-access``; Access › Policies).
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
    roles: bool = Query(True, description="With each one's Role; false: the list alone."),
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceMember]:
    """The workspace's members, with their Role here (``roles=false``: without it,
    read then a page at a time from ``GET …/members/roles``)."""
    rows = await service.list_workspace_members(workspace_id=workspace_id, with_roles=roles)
    moved_at = await _access_moved_at(db)
    return [_member_view(row, moved_at=moved_at) for row in rows]


async def _access_moved_at(db: AsyncSession) -> datetime | None:
    """When the access move (``access_model_v1``) was applied, or None."""
    from sqlalchemy import text

    try:
        async with db.begin_nested():  # a failed read leaves the request's transaction usable
            row = (
                await db.execute(
                    text("SELECT applied_at FROM iam_migrations WHERE name = :name"),
                    {"name": "access_model_v1"},
                )
            ).first()
    except Exception:  # no such table: a store from before the moves
        return None
    if row is None or row[0] is None:
        return None
    at = row[0]
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _member_view(
    row: WorkspaceMemberRecord, *, moved_at: datetime | None = None
) -> WorkspaceMember:
    joined, before = row.created_at, None
    if joined is not None and joined.tzinfo is None:
        joined = joined.replace(tzinfo=UTC)
    if moved_at is not None and (joined is None or joined <= moved_at):
        joined, before = None, moved_at
    return WorkspaceMember(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=row.role,
        email=row.email,
        name=row.name,
        created_at=joined,
        joined_before=before,
        source=row.source,
        principal_id=row.principal_id,
        status=row.status,
        level=row.level,
        roles=[
            MemberRoleView(kind=r.kind, id=r.id, name=r.name, scope=r.scope, implied=r.implied)
            for r in row.roles
        ],
    )


@router.get(
    "/{workspace_id}/members/role-options",
    dependencies=[guard("ListWorkspaceMembers", literal="-")],
)
async def member_role_options(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> RoleOptionsView:
    """What a member's Role here may hold, as the caller may give it: the levels, the
    workspace's own and admins groups, the other groups the caller lists here
    (capability groups, groups an admin made), and the policies the caller may attach
    here. What is managed elsewhere (the organization's people and admins) is not
    offered."""
    container = await authz.AUTHZ.container_of(workspace_id)
    if container is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    groups = await role_groups_of(container)
    return await role_options(current_user, container, groups, listed_at=container)


@router.get(
    "/{workspace_id}/members/roles",
    dependencies=[guard("ListWorkspaceMembers", literal="-")],
)
async def members_roles(
    workspace_id: str,
    principal: list[str] = Query(default_factory=list, max_length=ROLES_BATCH_MAX),
) -> dict[str, list[RoleRefView]]:
    """Workspace › Users › Role of the people asked by their IAM id (a page of them)."""
    container = await authz.AUTHZ.container_of(workspace_id)
    if container is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await roles_of_batch(container, principal)


async def _member_row(
    service: WorkspaceService, workspace_id: str, user_id: str
) -> tuple[WorkspaceMemberRecord, str]:
    rows = await service.list_workspace_members(workspace_id=workspace_id, with_roles=False)
    row = next((m for m in rows if m.user_id == user_id), None)
    container = await authz.AUTHZ.container_of(workspace_id)
    if row is None or not row.principal_id or container is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return row, container


@router.get(
    "/{workspace_id}/members/{user_id}/roles",
    dependencies=[guard("ListWorkspaceMembers", literal="-")],
)
async def member_roles(
    workspace_id: str,
    user_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> HeldRolesView:
    """What a member holds here, as a change of their Role starts from (``PUT``): the
    groups bearing on the workspace and the policies attached to them there, but what
    is managed elsewhere (their organization's people and admins) and what follows
    their groups."""
    row, container = await _member_row(service, workspace_id, user_id)
    return await held_roles(container, str(row.principal_id), await role_groups_of(container))


@router.put(
    "/{workspace_id}/members/{user_id}/roles",
    dependencies=[
        guard("UpdateWorkspaceMember", id="user_id", denied="Only admins can update members")
    ],
)
async def set_member_roles(
    workspace_id: str,
    user_id: str,
    body: MemberRolesInput,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> WorkspaceMember:
    """Make a member's Role here the groups and policies asked (``plan_role_change``):
    their level (one choice for every workspace they work in), whether they administer
    the workspace, the other groups, the policies attached here. Each change is made as
    the caller, so IAM decides; the workspace's own group never moves here."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own access")
    row, container = await _member_row(service, workspace_id, user_id)
    groups = await role_groups_of(container)

    async def seats(change: RoleChange, held: set[str]) -> set[str]:
        with people_errors(_member_denied):
            if change.admin is False:
                await people.set_workspace_admin(
                    user_id=user_id, workspace_id=workspace_id, admin=False, by=current_user
                )
            if change.level not in (KEEP, None):
                await people.set_level(
                    user_id=user_id, level=str(change.level), by=current_user, where=[container]
                )
            if change.admin is True:
                await people.set_workspace_admin(
                    user_id=user_id, workspace_id=workspace_id, admin=True, by=current_user
                )
        return set()

    held, _ = await MEMBERSHIPS.held_at(container, str(row.principal_id))
    await change_roles(
        user=current_user,
        scope=container,
        principal_id=str(row.principal_id),
        body=body,
        groups=groups,
        reaches_otherwise=row.source == "organization" or bool(held & groups.elsewhere),
        attach_at=container,
        seats=seats,
    )
    row, _ = await _member_row(service, workspace_id, user_id)
    return _member_view(row)


async def _find_workspace_member(
    service: WorkspaceService, *, workspace_id: str, user_id: str
) -> WorkspaceMemberRecord | None:
    members = await service.list_workspace_members(workspace_id=workspace_id)
    return next((m for m in members if m.user_id == user_id and m.source == "workspace"), None)


async def _added_member(
    service: WorkspaceService, *, workspace_id: str, user: Any, role: str
) -> WorkspaceMember:
    """The member just added, as the members list shows them."""
    row = await _find_workspace_member(service, workspace_id=workspace_id, user_id=user.id)
    if row is not None:
        return _member_view(row)
    return WorkspaceMember(
        id=f"member-{workspace_id}-{user.id}",
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
        email=user.email,
        name=user.name,
        status=people_status(user.status),
    )


def _grant_of(organization_id: str | None, workspace_id: str, body: WorkspaceAccessInput) -> Any:
    if body.policy_ids:
        raise HTTPException(
            status_code=400,
            detail="Policies are no longer attached to a person: name capability groups",
        )
    try:
        return workspace_grant(
            organization_id,
            workspace_id,
            level=body.level,
            admin=body.admin,
            role=body.role,
            capabilities=body.capabilities,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _role_shown(grant: Any) -> str:
    """The role the members list shows for someone just given ``grant``."""
    if grant.workspaces and grant.workspaces[0].admin:
        return "admin"
    return grant.level or "member"


@router.get(
    "/{workspace_id}/capability-groups",
    dependencies=[
        guard("InviteWorkspaceMember", literal="-", denied="Only admins can add members")
    ],
)
async def list_workspace_capability_groups(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    """The capability groups a person may join from this workspace: its
    organization's, then the platform's (the platform's alone for a workspace in no
    organization). The model's own groups are not listed."""
    workspace = await service.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"items": await capability_group_items(workspace.organization_id)}


@router.get(
    "/{workspace_id}/members/candidates",
    dependencies=[
        guard("InviteWorkspaceMember", literal="-", denied="Only admins can add members")
    ],
)
async def list_workspace_member_candidates(
    workspace_id: str,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=10, ge=1),
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> WorkspaceMemberCandidates:
    """People of the workspace's organization to add, by name or email: at least
    two characters, at most twenty answers, never anyone outside the organization's
    directory nor already in the workspace (nothing for a workspace in none)."""
    found = await service.member_candidates(workspace_id, q, people=people, limit=limit)
    return WorkspaceMemberCandidates(
        items=[WorkspaceMemberCandidate(**candidate.__dict__) for candidate in found]
    )


@router.post(
    "/{workspace_id}/members",
    status_code=201,
    dependencies=[
        guard("InviteWorkspaceMember", literal="-", denied="Only admins can add members")
    ],
)
async def add_workspace_member(
    workspace_id: str,
    body: WorkspaceMemberAdd,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> dict[str, object]:
    """Add someone of the organization's directory to the workspace ("<W>
    workspace"), with their level, whether they administer it and capability
    groups, now, and with ``notify`` send them an invitation. Nobody outside the
    directory is found (404, as for an unknown id); someone already in the workspace
    is a 409. No org role is granted. The notice counts as an invitation mail: the
    inviting user's, the address's and the organization's day limits apply to it."""
    if body.notify:
        await check_rate_limit(get_rate_limit_identifier(request, current_user.id), _INVITE_LIMIT)
    entry = await service.directory_entry(workspace_id, body.user_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="User not found")
    if workspace_id in entry.workspace_ids or entry.org_wide:
        raise HTTPException(status_code=409, detail="Already a member of this workspace")
    person = await people.get(body.user_id)
    if person is None:
        raise HTTPException(status_code=404, detail="User not found")
    workspace = await service.get_workspace(workspace_id)
    if body.notify:
        await check_rate_limit(f"email:{person.email.lower()}", _INVITE_LIMIT)
        await check_invitation_mail_quota(
            workspace.organization_id if workspace else None, workspace_id
        )
    grant = _grant_of(workspace.organization_id if workspace else None, workspace_id, body)
    with people_errors(_member_denied):
        user = await people.add_existing(
            user_id=body.user_id, grant=grant, by=current_user, notify=body.notify
        )
    member = await _added_member(
        service, workspace_id=workspace_id, user=user, role=_role_shown(grant)
    )
    # Whether the notice (or, to someone who never signed in, the invitation) went.
    return {"member": member.model_dump(mode="json"), "sign_in_email_sent": user.sign_in_email_sent}


def _profile_of(profile: Any) -> dict[str, str]:
    if profile is None:
        return {}
    return {key: value for key, value in profile.model_dump().items() if value is not None}


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
    people: PeopleServicePort = Depends(get_people_service),
) -> dict[str, object]:
    """Create the person's platform account, or link the one their email has, and
    put them in this workspace only (level, admin, capability groups): no org role.
    The answer is the same either way."""
    email = invite.email.lower().strip()
    await check_rate_limit(get_rate_limit_identifier(request, current_user.id), _INVITE_LIMIT)
    await check_rate_limit(f"email:{email}", _INVITE_LIMIT)
    workspace = await service.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    grant = _grant_of(workspace.organization_id, workspace_id, invite)
    await check_invitation_mail_quota(workspace.organization_id, workspace_id)
    with people_errors(_member_denied):
        result = await people.create_or_link(
            email=email,
            name=invite.name,
            provider=invite.provider,
            grant=grant,
            by=current_user,
            profile=_profile_of(invite.profile),
            organization_id=workspace.organization_id,
        )
    member = await _added_member(
        service, workspace_id=workspace_id, user=result.user, role=_role_shown(grant)
    )
    return added_result(result, member)


@router.post(
    "/{workspace_id}/members/{user_id}/resend",
    dependencies=[
        guard("InviteWorkspaceMember", literal="-", denied="Only admins can invite members")
    ],
)
async def resend_workspace_member_invite(
    workspace_id: str,
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> dict[str, bool]:
    """Send an invited member their sign-in mail again; 409 once they signed in.
    Once a window for one person, then the invite limits (inviting user, address,
    the organization's day of mail)."""
    if await _find_workspace_member(service, workspace_id=workspace_id, user_id=user_id) is None:
        raise HTTPException(status_code=404, detail="Member not found")
    workspace = await service.get_workspace(workspace_id)
    user = await people.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if people_status(user.status) != UserStatus.INVITED:
        raise HTTPException(status_code=409, detail="This member has already signed in")
    # The person's own limit first: a refused resend spends nothing else.
    await check_rate_limit(f"invitation:{user_id}", RESEND_LIMIT, limit=1)
    await check_rate_limit(get_rate_limit_identifier(request, current_user.id), _INVITE_LIMIT)
    await check_rate_limit(f"email:{user.email.lower()}", _INVITE_LIMIT)
    await check_invitation_mail_quota(
        workspace.organization_id if workspace else None, workspace_id
    )
    with people_errors(_member_denied):
        sent = await people.resend(user_id=user_id, by=current_user)
    return {"sign_in_email_sent": sent}


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
    body: WorkspaceMemberChange,
    current_user: User = Depends(get_current_user_required),
    service: WorkspaceService = Depends(get_workspace_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> dict[str, object]:
    """Change a member's level (#1589: one choice, applying in every workspace they
    work in; this workspace's admins may change it, audited) and whether they
    administer this workspace. ``{role}``, the body of before, is still read."""
    if body.level is not None or body.admin is not None:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own access")
        if (
            await _find_workspace_member(service, workspace_id=workspace_id, user_id=user_id)
            is None
        ):
            raise HTTPException(status_code=404, detail="Member not found")
        if body.level == "viewer" and body.admin:
            raise HTTPException(
                status_code=400,
                detail="A workspace admin is a Member: a Viewer administers nothing",
            )
        container = await authz.AUTHZ.container_of(workspace_id)
        with people_errors(_member_denied):
            if body.admin is False:
                await people.set_workspace_admin(
                    user_id=user_id, workspace_id=workspace_id, admin=False, by=current_user
                )
            if body.level is not None:
                await people.set_level(
                    user_id=user_id,
                    level=body.level,
                    by=current_user,
                    where=[container] if container else [],
                )
            if body.admin:
                await people.set_workspace_admin(
                    user_id=user_id, workspace_id=workspace_id, admin=True, by=current_user
                )
        row = await _find_workspace_member(service, workspace_id=workspace_id, user_id=user_id)
        return {
            "status": "updated",
            "level": row.level if row else body.level,
            "admin": bool(row and row.role in ("admin", "owner")),
        }
    updates = body.model_dump(exclude_none=True)
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
    """Store the logo in Workspace Files (``logo_store``); the previous one is archived."""
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
    """Archive the logo in Workspace Files and clear it."""
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
# Home desk wallpaper (Workspace Files .home/): stage → preview → commit.
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
