from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureKey, settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    BASELINE_ROLES,
    KNOWN_FEATURE_KEYS,
    PINNED_FEATURES,
    InvalidFeatureOverridesError,
    effective_workspace_overrides,
    enabled_feature_catalog,
    resolve_role_baseline,
    validate_workspace_feature_overrides,
    workspace_features,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import avatar_store, user_drive_profile
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (
    ALLOWED_AVATAR_EXTENSIONS,
    MAX_AVATAR_SIZE,
    _delete_old_avatar,
    _get_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
    issue_and_send_invite_sign_in,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationMemberRecord,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationDomainAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationPermissionError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceUpdateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceMemberAlreadyExistsError,
    WorkspaceService,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import resolve_stored_asset_url
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
public_router = APIRouter()


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def get_workspace_service_for_org_invite(
    db: AsyncSession = Depends(get_db),
) -> WorkspaceService:
    return WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))


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


class OrganizationBranding(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    current_user_role: str | None = None


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool | None = None
    show_powered_by: bool | None = None
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool | None = None
    default_theme: str | None = None


class OrganizationMember(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    service_line: str | None = None
    country: str | None = None
    interest: str | None = None
    user_created: bool = False
    sign_in_email_sent: bool = False
    workspace_member_id: str | None = None


class OrganizationMemberAccount(BaseModel):
    """The member's platform account (read-only here)."""

    user_id: str
    email: str | None = None
    name: str | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrganizationMemberProfile(BaseModel):
    """What this organization set; null fields show the account value."""

    name: str | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    service_line: str | None = None
    country: str | None = None
    interest: str | None = None


class OrganizationMemberWorkspace(BaseModel):
    id: str
    name: str
    slug: str
    role: str
    source: str


class OrganizationMemberDetails(BaseModel):
    member: OrganizationMember
    account: OrganizationMemberAccount
    organization_profile: OrganizationMemberProfile
    workspaces: list[OrganizationMemberWorkspace]


class OrganizationMemberInvite(BaseModel):
    email: str = Field(..., min_length=1)
    # Owners come from the config only (organizations[].owner_email).
    role: str = Field(default="member", pattern=r"^(admin|member)$")
    # Account name, used only when the invite creates the account (users.name).
    name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_id: str | None = Field(default=None, min_length=1)
    workspace_role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")
    # Member profile in this organization (Organization Settings > Users > Create user).
    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)


class OrganizationMemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|member)$")
    # No name: a member's full name is always their account name (users.name).
    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)


class OrganizationMemberWorkspacesUpdate(BaseModel):
    workspace_ids: list[str] = Field(default_factory=list)
    workspace_role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")


class OrganizationRoleFeaturesUpdate(BaseModel):
    role_baseline: dict[str, list[FeatureKey]]


class OrganizationWorkspacesBulkUpdate(BaseModel):
    """One property set on several workspaces at once (only the group for now)."""

    workspace_ids: list[str] = Field(..., min_length=1, max_length=500)
    # Blank clears the group (the workspaces list under "Others").
    workspace_group: str = Field(..., max_length=100)


class WorkspaceFeatureOverridesUpdate(BaseModel):
    # None drops the saved overrides: the deployment config applies again.
    overrides: dict[FeatureKey, bool] | None = None


class OrganizationDomain(BaseModel):
    id: str
    organization_id: str
    domain: str
    is_verified: bool
    verification_token: str | None = None
    created_at: datetime | None = None
    verified_at: datetime | None = None


class OrganizationDomainCreate(BaseModel):
    domain: str = Field(
        ..., min_length=3, max_length=255, pattern=r"^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$"
    )


class BillingInfo(BaseModel):
    plan: str
    usage: dict | None = None


class BillingUpgrade(BaseModel):
    plan: str


def _to_schema(row: OrganizationRecord) -> Organization:
    return Organization(**row.__dict__)


def _to_branding(row: OrganizationRecord) -> OrganizationBranding:
    return OrganizationBranding(
        id=row.id,
        name=row.name,
        slug=row.slug,
        logo_url=row.logo_url,
        logo_rectangle_url=row.logo_rectangle_url,
        logo_emoji=row.logo_emoji,
        primary_color=row.primary_color or "#22c55e",
        accent_color=row.accent_color,
        background_color=row.background_color,
        font_family=row.font_family,
        font_url=row.font_url,
        login_card_max_width=row.login_card_max_width,
        login_card_padding=row.login_card_padding,
        login_card_color=row.login_card_color,
        login_text_color=row.login_text_color,
        login_input_color=row.login_input_color,
        login_border_radius=row.login_border_radius,
        login_bg_image_url=row.login_bg_image_url,
        show_terms_footer=row.show_terms_footer,
        show_powered_by=row.show_powered_by,
        login_footer_text=row.login_footer_text,
        secondary_logo_url=row.secondary_logo_url,
        show_logo_separator=row.show_logo_separator,
        default_theme=row.default_theme,
    )


async def get_org_role(user_id: str, org_id: str, service: OrganizationService) -> str | None:
    return await service.get_organization_role(user_id=user_id, org_id=org_id)


async def require_org_access(user_id: str, org_id: str, service: OrganizationService) -> str:
    try:
        return await service.require_organization_access(user_id=user_id, org_id=org_id)
    except OrganizationPermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this organization",
        ) from exc


ORG_LOGO_UPLOAD_DIR = Path("uploads") / "org-logos"
ORG_LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


@public_router.get("/slug/{slug}/branding")
async def get_organization_branding(
    slug: str,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationBranding:
    row = await service.get_organization_by_slug(slug=slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_branding(row)


@router.get("")
async def list_organizations(
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[Organization]:
    rows = await service.list_organizations(user_id=current_user.id)
    return [_to_schema(row) for row in rows]


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    role = await require_org_access(current_user.id, org_id, service)
    row = await service.get_organization(org_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return Organization(**row.__dict__, current_user_role=role)


@router.post("")
async def create_organization(
    org: OrganizationCreate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    try:
        row = await service.create_organization(
            name=org.name,
            slug=org.slug,
            owner_id=current_user.id,
            logo_url=org.logo_url,
            logo_rectangle_url=org.logo_rectangle_url,
            logo_emoji=org.logo_emoji,
            primary_color=org.primary_color,
            accent_color=org.accent_color,
            background_color=org.background_color,
            font_family=org.font_family,
            font_url=org.font_url,
            login_card_max_width=org.login_card_max_width,
            login_card_padding=org.login_card_padding,
            login_card_color=org.login_card_color,
            login_text_color=org.login_text_color,
            login_input_color=org.login_input_color,
            login_border_radius=org.login_border_radius,
            login_bg_image_url=org.login_bg_image_url,
            show_terms_footer=org.show_terms_footer,
            show_powered_by=org.show_powered_by,
            login_footer_text=org.login_footer_text,
            secondary_logo_url=org.secondary_logo_url,
            show_logo_separator=org.show_logo_separator,
            default_theme=org.default_theme,
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except OrganizationSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Slug already exists") from exc

    return _to_schema(row)


@router.patch("/{org_id}")
async def update_organization(
    org_id: str,
    updates: OrganizationUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update organization branding")

    row = await service.update_organization(
        org_id=org_id,
        updates=OrganizationUpdateInput(
            **updates.model_dump(exclude_unset=True),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            set_fields=set(updates.model_dump(exclude_unset=True).keys()) | {"updated_at"},
        ),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_schema(row)


@router.post("/{org_id}/upload-logo-square")
async def upload_org_logo_square(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update organization branding")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"org-{org_id}-square{ext}"
    filepath = ORG_LOGO_UPLOAD_DIR / filename
    with open(filepath, "wb") as file_handle:
        file_handle.write(contents)

    org = await service.get_organization(org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.logo_url and org.logo_url.startswith("/uploads/org-logos/"):
        old = ORG_LOGO_UPLOAD_DIR / os.path.basename(org.logo_url)
        old.unlink(missing_ok=True)

    updated = await service.update_organization(
        org_id=org_id,
        updates=OrganizationUpdateInput(
            logo_url=f"/uploads/org-logos/{filename}",
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            set_fields={"logo_url", "updated_at"},
        ),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"logo_url": updated.logo_url}


@router.post("/{org_id}/upload-logo-rectangle")
async def upload_org_logo_rectangle(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update organization branding")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"org-{org_id}-rectangle{ext}"
    filepath = ORG_LOGO_UPLOAD_DIR / filename
    with open(filepath, "wb") as file_handle:
        file_handle.write(contents)

    org = await service.get_organization(org_id=org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.logo_rectangle_url and org.logo_rectangle_url.startswith("/uploads/org-logos/"):
        old = ORG_LOGO_UPLOAD_DIR / os.path.basename(org.logo_rectangle_url)
        old.unlink(missing_ok=True)

    updated = await service.update_organization(
        org_id=org_id,
        updates=OrganizationUpdateInput(
            logo_rectangle_url=f"/uploads/org-logos/{filename}",
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            set_fields={"logo_rectangle_url", "updated_at"},
        ),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"logo_rectangle_url": updated.logo_rectangle_url}


def _workspace_payload(
    ws: OrganizationWorkspaceRecord,
    *,
    org_logo_url: str | None,
    org_logo_rect_url: str | None,
    organization_override: dict[str, list[str]] | None = None,
) -> dict:
    flags = settings.feature_flags
    overrides, overrides_source = effective_workspace_overrides(
        flags,
        workspace_slug=ws.slug,
        workspace_id=ws.id,
        workspace_override=ws.feature_overrides,
    )
    return {
        "id": ws.id,
        "name": ws.name,
        "slug": ws.slug,
        "owner_id": ws.owner_id,
        "organization_id": ws.organization_id,
        "created_at": ws.created_at,
        "updated_at": ws.updated_at,
        "logo_url": resolve_stored_asset_url(ws.logo_url),
        "logo_emoji": ws.logo_emoji,
        "workspace_group": ws.workspace_group,
        "organization_logo_url": resolve_stored_asset_url(org_logo_url),
        "organization_logo_rectangle_url": resolve_stored_asset_url(org_logo_rect_url),
        # Features on for at least one role, after the overrides.
        "features": workspace_features(
            roles=BASELINE_ROLES,
            feature_flags_config=flags,
            workspace_slug=ws.slug,
            workspace_id=ws.id,
            organization_id=ws.organization_id,
            organization_override=organization_override,
            workspace_override=ws.feature_overrides,
        ),
        "feature_overrides": overrides,
        "feature_overrides_source": overrides_source,
    }


async def _org_role_override(
    org_id: str, service: OrganizationService
) -> dict[str, list[str]] | None:
    stored = await service.get_role_features(org_id=org_id)
    return stored.role_baseline if stored is not None else None


async def _org_workspace_payloads(
    org_id: str,
    service: OrganizationService,
    workspaces: list[OrganizationWorkspaceRecord],
) -> list[dict]:
    org = await service.get_organization(org_id=org_id)
    organization_override = await _org_role_override(org_id, service)
    return [
        _workspace_payload(
            ws,
            org_logo_url=org.logo_url if org else None,
            org_logo_rect_url=org.logo_rectangle_url if org else None,
            organization_override=organization_override,
        )
        for ws in workspaces
    ]


async def _require_org_admin(
    user_id: str, org_id: str, service: OrganizationService, action: str
) -> None:
    role = await require_org_access(user_id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail=f"Only admins can {action}")


@router.get("/{org_id}/workspaces")
async def list_org_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[dict]:
    role = await require_org_access(current_user.id, org_id, service)

    # Org owners/admins manage the full org catalog; members only see workspaces
    # they already belong to.
    if role in ("owner", "admin"):
        workspaces = await service.list_all_workspaces(org_id=org_id)
    else:
        workspaces = await service.list_workspaces(org_id=org_id, user_id=current_user.id)
    return await _org_workspace_payloads(org_id, service, workspaces)


@router.post("/{org_id}/workspaces/bulk-update")
async def bulk_update_org_workspaces(
    org_id: str,
    body: OrganizationWorkspacesBulkUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
) -> dict:
    """Set the group of several workspaces of this organization at once."""
    await _require_org_admin(current_user.id, org_id, service, "edit workspaces")
    org_workspaces = {ws.id: ws for ws in await service.list_all_workspaces(org_id=org_id)}
    requested = list(dict.fromkeys(body.workspace_ids))
    unknown = sorted(set(requested) - set(org_workspaces))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Workspaces not in this organization: {', '.join(unknown)}",
        )
    for workspace_id in requested:
        await workspace_service.update_workspace(
            workspace_id=workspace_id,
            updates=WorkspaceUpdateInput(workspace_group=body.workspace_group),
        )
    refreshed = [
        ws for ws in await service.list_all_workspaces(org_id=org_id) if ws.id in set(requested)
    ]
    return {
        "updated": len(requested),
        "workspaces": await _org_workspace_payloads(org_id, service, refreshed),
    }


@router.get("/{org_id}/workspace-seed-catalog")
async def get_org_workspace_seed_catalog(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    """Instance catalog for the create-workspace picker (agents, apps, …)."""
    await _require_org_admin(current_user.id, org_id, service, "view workspace seed catalog")
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
        build_workspace_seed_catalog,
    )

    catalog = build_workspace_seed_catalog()
    return {
        key: [{"id": option.id, "label": option.label, "kind": option.kind} for option in options]
        for key, options in catalog.items()
    }


@router.get("/{org_id}/workspace-features")
async def get_org_workspace_features(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    """What the workspace features modal needs: the catalog and the role defaults."""
    await _require_org_admin(current_user.id, org_id, service, "view workspace features")
    flags = settings.feature_flags
    role_baseline = resolve_role_baseline(
        flags,
        organization_id=org_id,
        organization_override=await _org_role_override(org_id, service),
    )
    catalog = enabled_feature_catalog(flags)
    return {
        "catalog": catalog,
        "pinned": [key for key in PINNED_FEATURES if key in catalog],
        "roles": list(BASELINE_ROLES),
        "role_baseline": {
            role_name: [key for key in role_baseline.get(role_name, []) if key in catalog]
            for role_name in BASELINE_ROLES
        },
    }


@router.put("/{org_id}/workspaces/{workspace_id}/features")
async def update_org_workspace_features(
    org_id: str,
    workspace_id: str,
    body: WorkspaceFeatureOverridesUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
) -> dict:
    """Save a workspace's feature overrides; ``overrides: null`` restores the config ones."""
    await _require_org_admin(current_user.id, org_id, service, "edit workspace features")
    org_workspaces = {ws.id: ws for ws in await service.list_all_workspaces(org_id=org_id)}
    if workspace_id not in org_workspaces:
        raise HTTPException(status_code=404, detail="Workspace not found in this organization")
    overrides = None
    if body.overrides is not None:
        try:
            overrides = validate_workspace_feature_overrides(settings.feature_flags, body.overrides)
        except InvalidFeatureOverridesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    await workspace_service.set_workspace_feature_overrides(
        workspace_id=workspace_id, overrides=overrides
    )
    refreshed = [
        ws for ws in await service.list_all_workspaces(org_id=org_id) if ws.id == workspace_id
    ]
    return (await _org_workspace_payloads(org_id, service, refreshed))[0]


@router.get("/{org_id}/member-workspaces")
async def list_org_member_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can list member workspaces")
    workspaces = await service.list_all_workspaces(org_id=org_id)
    memberships = await service.list_workspace_memberships(org_id=org_id)
    return {
        "workspaces": await _org_workspace_payloads(org_id, service, workspaces),
        "memberships": [
            {
                "user_id": row.user_id,
                "workspace_id": row.workspace_id,
                "role": row.role,
            }
            for row in memberships
        ],
    }


@router.put("/{org_id}/members/{user_id}/workspaces")
async def sync_org_member_workspaces(
    org_id: str,
    user_id: str,
    body: OrganizationMemberWorkspacesUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can assign workspaces")

    member = await service.adapter.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    org_workspaces = await service.list_all_workspaces(org_id=org_id)
    org_workspace_by_id = {ws.id: ws for ws in org_workspaces}
    desired_ids = set(body.workspace_ids)
    unknown = sorted(desired_ids - set(org_workspace_by_id))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Workspaces not in this organization: {', '.join(unknown)}",
        )

    memberships = await service.list_workspace_memberships(org_id=org_id)
    current_ids = {row.workspace_id for row in memberships if row.user_id == user_id}

    added: list[str] = []
    removed: list[str] = []
    skipped_owner: list[str] = []

    for workspace_id in sorted(desired_ids - current_ids):
        if await workspace_service.adapter.is_workspace_member(
            workspace_id=workspace_id, user_id=user_id
        ):
            continue
        await workspace_service.adapter.add_workspace_member(
            workspace_id=workspace_id,
            user_id=user_id,
            role=body.workspace_role,
        )
        added.append(workspace_id)

    for workspace_id in sorted(current_ids - desired_ids):
        workspace = org_workspace_by_id.get(workspace_id)
        if workspace is not None and workspace.owner_id == user_id:
            skipped_owner.append(workspace_id)
            continue
        removed_ok = await workspace_service.remove_workspace_member(
            workspace_id=workspace_id, user_id=user_id
        )
        if removed_ok:
            removed.append(workspace_id)

    refreshed = [
        {
            "user_id": row.user_id,
            "workspace_id": row.workspace_id,
            "role": row.role,
        }
        for row in await service.list_workspace_memberships(org_id=org_id)
        if row.user_id == user_id
    ]
    return {
        "user_id": user_id,
        "workspace_ids": [row["workspace_id"] for row in refreshed],
        "memberships": refreshed,
        "added": added,
        "removed": removed,
        "skipped_owner": skipped_owner,
    }


@router.get("/{org_id}/roles/features")
async def get_org_role_features(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can view role features")
    flags = settings.feature_flags
    stored = await service.get_role_features(org_id=org_id)
    organization_override = stored.role_baseline if stored is not None else None
    role_baseline = resolve_role_baseline(
        flags,
        organization_id=org_id,
        organization_override=organization_override,
    )
    return {
        "enabled_features": list(flags.enabled_features),
        "role_baseline": {
            role_name: list(role_baseline.get(role_name, [])) for role_name in BASELINE_ROLES
        },
        "known_features": list(KNOWN_FEATURE_KEYS),
        "roles": list(BASELINE_ROLES),
        "persistence": "database" if stored is not None else "deployment",
        "updated_at": stored.updated_at.isoformat() if stored and stored.updated_at else None,
        "updated_by": stored.updated_by if stored else None,
        "note": (
            "GET merges deployment nexus_config.feature_flags with a durable "
            "per-organization overlay in organization_role_features. PUT upserts "
            "that row for this organization only and never replaces the "
            "deployment baseline."
        ),
    }


@router.put("/{org_id}/roles/features")
async def update_org_role_features(
    org_id: str,
    body: OrganizationRoleFeaturesUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update role features")

    allowed_roles = set(BASELINE_ROLES)
    unknown_roles = sorted(set(body.role_baseline) - allowed_roles)
    if unknown_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown roles: {', '.join(unknown_roles)}",
        )
    missing_roles = sorted(allowed_roles - set(body.role_baseline))
    if missing_roles:
        raise HTTPException(
            status_code=400,
            detail=(
                "role_baseline must include all baseline roles "
                f"({', '.join(BASELINE_ROLES)}); missing: {', '.join(missing_roles)}"
            ),
        )

    known = set(KNOWN_FEATURE_KEYS)
    enabled = set(settings.feature_flags.enabled_features) or known
    cleaned: dict[str, list[FeatureKey]] = {}
    for role_name in BASELINE_ROLES:
        features = body.role_baseline[role_name]
        invalid = sorted({f for f in features if f not in known})
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown features for {role_name}: {', '.join(invalid)}",
            )
        disabled = sorted({f for f in features if f not in enabled})
        if disabled:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Features not enabled in deployment catalog for {role_name}: "
                    f"{', '.join(disabled)}"
                ),
            )
        cleaned[role_name] = list(features)

    await service.upsert_role_features(
        org_id=org_id,
        role_baseline={role_name: list(feats) for role_name, feats in cleaned.items()},
        updated_by=current_user.id,
        now=datetime.now(UTC).replace(tzinfo=None),
    )
    return await get_org_role_features(org_id, current_user, service)


@router.get("/{org_id}/members")
async def list_org_members(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationMember]:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can list organization members")
    rows = await service.list_members(org_id=org_id)
    return [OrganizationMember(**row.__dict__) for row in rows]


async def _sync_member_drive(
    db: AsyncSession, object_storage: ObjectStorageService, user_id: str
) -> None:
    """Refresh org_member.json and .USER.md in the member's drive (best effort)."""
    await db.flush()
    await user_drive_profile.sync_user_drive_profile_safely(
        db, object_storage, user_id, datetime.now(UTC)
    )


@router.get("/{org_id}/members/{user_id}")
async def get_org_member_details(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMemberDetails:
    """One member: their account, their profile in this org and their workspaces here."""
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can view member details")
    details = await service.get_member_details(org_id=org_id, user_id=user_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Member not found")
    workspaces = await service.get_member_workspace_access(
        org_id=org_id, user_id=user_id, organization_role=details.member.role
    )
    return OrganizationMemberDetails(
        member=OrganizationMember(**details.member.__dict__),
        account=OrganizationMemberAccount(**details.account.__dict__),
        organization_profile=OrganizationMemberProfile(**details.organization_profile.__dict__),
        workspaces=[
            OrganizationMemberWorkspace(
                id=w.workspace_id, name=w.name, slug=w.slug, role=w.role, source=w.source
            )
            for w in workspaces
        ],
    )


async def _find_org_member(
    service: OrganizationService, *, org_id: str, user_id: str
) -> OrganizationMemberRecord | None:
    """Existing membership row, for resending an invite to a current member."""
    members = await service.list_members(org_id=org_id)
    return next((m for m in members if m.user_id == user_id), None)


@router.post("/{org_id}/members/invite")
async def invite_org_member(
    org_id: str,
    invite: OrganizationMemberInvite,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
    auth_service: AuthService = Depends(get_auth_service),
    email_service: EmailService | None = Depends(_get_email_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can invite members")

    email = invite.email.lower().strip()
    await check_rate_limit(
        get_rate_limit_identifier(request, current_user.id),
        "/api/organizations/members/invite",
    )
    await check_rate_limit(f"email:{email}", "/api/organizations/members/invite")

    workspace_member_id: str | None = None
    if invite.workspace_id:
        org_workspaces = await service.list_all_workspaces(org_id=org_id)
        if invite.workspace_id not in {ws.id for ws in org_workspaces}:
            raise HTTPException(
                status_code=400,
                detail="workspace_id must belong to this organization",
            )

    _user, user_created = await auth_service.ensure_user_for_invite(email, name=invite.name)

    try:
        member = await service.invite_member(
            org_id=org_id,
            email=email,
            role=invite.role,
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except OrganizationMemberAlreadyExistsError as exc:
        # Re-inviting is how an admin resends an invite that never arrived, so
        # keep the membership as-is and fall through to issue a fresh challenge
        # rather than rejecting the only retry path they have.
        member = await _find_org_member(service, org_id=org_id, user_id=exc.user_id)
        if member is None:
            raise HTTPException(status_code=400, detail="User is already a member") from exc

    if member is None:
        raise HTTPException(status_code=500, detail="Failed to create or find user for invite")

    profile = {
        "organization": invite.organization,
        "job_title": invite.job_title,
        "bio": invite.bio,
        "service_line": invite.service_line,
        "country": invite.country,
        "interest": invite.interest,
    }
    if any(value is not None for value in profile.values()):
        member = (
            await service.update_member_profile(
                org_id=org_id, user_id=member.user_id, name=None, **profile
            )
            or member
        )

    if invite.workspace_id:
        try:
            ws_member = await workspace_service.invite_workspace_member(
                workspace_id=invite.workspace_id,
                email=email,
                role=invite.workspace_role,
            )
        except WorkspaceMemberAlreadyExistsError:
            ws_member = None
        if ws_member is not None:
            workspace_member_id = ws_member.id

    sign_in_email_sent = await issue_and_send_invite_sign_in(
        auth_service,
        email,
        email_service=email_service or _get_email_service(request),
    )

    await _sync_member_drive(db, object_storage, member.user_id)
    return OrganizationMember(
        **member.__dict__,
        user_created=user_created,
        sign_in_email_sent=sign_in_email_sent,
        workspace_member_id=workspace_member_id,
    )


@router.patch("/{org_id}/members/{user_id}")
async def update_org_member(
    org_id: str,
    user_id: str,
    updates: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update members")

    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if updates.role is not None:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if member.role == "owner":
            raise HTTPException(status_code=400, detail="Cannot change the organization owner role")
        member = await service.update_member_role(
            org_id=org_id, user_id=user_id, role=updates.role
        )
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")

    profile_touched = any(
        field is not None
        for field in (
            updates.organization,
            updates.job_title,
            updates.bio,
            updates.service_line,
            updates.country,
            updates.interest,
        )
    )
    if profile_touched:
        # Profile in this organization only: the account (users.*) and the
        # member's profile in other organizations are left untouched.
        member = await service.update_member_profile(
            org_id=org_id,
            user_id=user_id,
            name=None,
            organization=updates.organization,
            job_title=updates.job_title,
            bio=updates.bio,
            service_line=updates.service_line,
            country=updates.country,
            interest=updates.interest,
        )
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")

    await _sync_member_drive(db, object_storage, user_id)
    return OrganizationMember(**member.__dict__)


@router.post("/{org_id}/members/{user_id}/avatar")
async def upload_org_member_avatar(
    org_id: str,
    user_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update members")

    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_AVATAR_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    # In the member's own drive as avatar_org_<org_id>.<ext>, one per organization,
    # the previous one archived (avatar_store). The account shows it when it has
    # no picture of its own.
    saved = avatar_store.save_avatar(
        object_storage,
        user_id,
        content,
        ext,
        datetime.now(UTC),
        basename=avatar_store.org_avatar_basename(org_id),
    )
    avatar_url = avatar_store.org_avatar_url(user_id, org_id, saved.digest)
    previous_avatar = await service.set_member_avatar(
        org_id=org_id, user_id=user_id, avatar=avatar_url
    )
    # A picture from before the drive layout: its file is no longer used.
    _delete_old_avatar(object_storage, previous_avatar)
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    await _sync_member_drive(db, object_storage, user_id)
    return OrganizationMember(**member.__dict__)


@router.delete("/{org_id}/members/{user_id}/avatar")
async def remove_org_member_avatar(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update members")

    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    previous_avatar = await service.set_member_avatar(org_id=org_id, user_id=user_id, avatar=None)
    avatar_store.remove_avatar(
        object_storage,
        user_id,
        datetime.now(UTC),
        basename=avatar_store.org_avatar_basename(org_id),
    )
    _delete_old_avatar(object_storage, previous_avatar)
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    await _sync_member_drive(db, object_storage, user_id)
    return OrganizationMember(**member.__dict__)


@router.delete("/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can remove members")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    member = await service.get_organization_role(user_id=user_id, org_id=org_id)
    if member == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the organization owner")

    removed = await service.remove_member(org_id=org_id, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    await _sync_member_drive(db, object_storage, user_id)
    return {"message": "Member removed successfully"}


@router.get("/{org_id}/domains")
async def list_org_domains(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationDomain]:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can list organization domains")
    rows = await service.list_domains(org_id=org_id)
    return [
        OrganizationDomain(
            id=row.id,
            organization_id=row.organization_id,
            domain=row.domain,
            is_verified=row.is_verified,
            verification_token=row.verification_token if not row.is_verified else None,
            created_at=row.created_at,
            verified_at=row.verified_at,
        )
        for row in rows
    ]


@router.post("/{org_id}/domains")
async def add_org_domain(
    org_id: str,
    domain_data: OrganizationDomainCreate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDomain:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can add domains")

    try:
        row = await service.add_domain(
            org_id=org_id,
            domain=domain_data.domain,
            now=datetime.now(UTC).replace(tzinfo=None),
            verification_token=secrets.token_urlsafe(32),
        )
    except OrganizationDomainAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Domain already registered") from exc

    return OrganizationDomain(**row.__dict__)


@router.post("/{org_id}/domains/{domain_id}/verify")
async def verify_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDomain:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can verify domains")

    domain = await service.get_domain(org_id=org_id, domain_id=domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    if domain.is_verified:
        raise HTTPException(status_code=400, detail="Domain already verified")

    verified = await service.verify_domain(
        org_id=org_id,
        domain_id=domain_id,
        verified_at=datetime.now(UTC).replace(tzinfo=None),
    )
    if verified is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    return OrganizationDomain(
        id=verified.id,
        organization_id=verified.organization_id,
        domain=verified.domain,
        is_verified=verified.is_verified,
        verification_token=None,
        created_at=verified.created_at,
        verified_at=verified.verified_at,
    )


@router.delete("/{org_id}/domains/{domain_id}")
async def delete_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can delete domains")

    deleted = await service.delete_domain(org_id=org_id, domain_id=domain_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"message": "Domain removed successfully"}


@router.get("/{org_id}/billing")
async def get_org_billing(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> BillingInfo:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can manage billing")
    raise HTTPException(
        status_code=501,
        detail="Billing functionality is not yet implemented. This feature will be available in a future release.",
    )


@router.post("/{org_id}/billing/upgrade")
async def upgrade_org_plan(
    org_id: str,
    upgrade: BillingUpgrade,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can manage billing")

    raise HTTPException(
        status_code=501,
        detail="Billing upgrades are not yet implemented. Please contact support@naas.ai to discuss enterprise plans.",
    )


@router.post("/{org_id}/billing/payment-method")
async def add_payment_method(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can manage billing")

    raise HTTPException(
        status_code=501,
        detail="Payment method management is not yet implemented. Billing features are coming soon.",
    )
