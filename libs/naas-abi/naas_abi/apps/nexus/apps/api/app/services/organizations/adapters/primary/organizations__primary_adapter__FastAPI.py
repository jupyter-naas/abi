from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import offered_features
from naas_abi.apps.nexus.apps.api.app.services.auth import avatar_store, user_drive_profile
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    ALLOWED_AVATAR_EXTENSIONS,
    MAX_AVATAR_SIZE,
    _delete_old_avatar,
    _get_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MembershipDenied
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.mail import send_added_notice
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    NoProviderError,
    OwnerGrantRefusedError,
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
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationMemberRecord,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    LastOwnerError,
    OrganizationDomainAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
    new_org_id,
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
    role: str = Field(default="member", pattern=r"^(owner|admin|member)$")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_id: str | None = Field(default=None, min_length=1)
    workspace_role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")
    # The identity provider to invite through; by default the one the email's
    # domain routes to, else the default provider.
    provider: str | None = Field(default=None, min_length=1, max_length=32)
    # Customer policies the new member gets beside the roles: at ``workspace_id``
    # when given, else at the organization (no role brings a feature).
    policy_ids: list[str] = Field(default_factory=list, max_length=20)
    # Member profile in this organization (Organization Settings > Users > Create user).
    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)


class OrganizationMemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(owner|admin|member)$")
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


class OrganizationWorkspacesBulkUpdate(BaseModel):
    """One property set on several workspaces at once (only the group for now)."""

    workspace_ids: list[str] = Field(..., min_length=1, max_length=500)
    # Blank clears the group (the workspaces list under "Others").
    workspace_group: str = Field(..., max_length=100)


class OrganizationDomain(BaseModel):
    id: str
    organization_id: str
    domain: str
    is_verified: bool
    verification_token: str | None = None
    created_at: datetime | None = None
    verified_at: datetime | None = None
    # The identity provider logins of this domain go to; None: the default one.
    provider: str | None = None


class OrganizationDomainProviderUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,32}$")


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


def _member_denied(role: str) -> HTTPException:
    """IAM refused a change of roles: the owner role is the owner's alone (bug c)."""
    if role == "owner":
        return HTTPException(
            status_code=403, detail="Only owners can grant, change or remove an owner"
        )
    return HTTPException(status_code=403, detail="You do not have permission to change this member")


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


@router.get("", dependencies=[declares("ListOrganizations")])
async def list_organizations(
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[Organization]:
    rows = await service.list_organizations(user_id=current_user.id)
    return [_to_schema(row) for row in rows]


@router.get("/{org_id}", dependencies=[guard("GetOrganization", workspace=None, org="org_id")])
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    role = await service.get_organization_role(current_user.id, org_id)
    row = await service.get_organization(org_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return Organization(**row.__dict__, current_user_role=role)


@router.post("", dependencies=[declares("CreateOrganization")])
async def create_organization(
    org: OrganizationCreate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    # Checked on the new organization's own name.
    org_id = new_org_id()
    await authz.require("CreateOrganization", user=current_user, id=org_id)
    try:
        row = await service.create_organization(
            org_id=org_id,
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


@router.patch(
    "/{org_id}",
    dependencies=[
        guard(
            "UpdateOrganization",
            workspace=None,
            org="org_id",
            denied="Only admins can update organization branding",
        )
    ],
)
async def update_organization(
    org_id: str,
    updates: OrganizationUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
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


@router.post(
    "/{org_id}/upload-logo-square",
    dependencies=[
        guard(
            "UpdateOrganization",
            workspace=None,
            org="org_id",
            denied="Only admins can update organization branding",
        )
    ],
)
async def upload_org_logo_square(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
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


@router.post(
    "/{org_id}/upload-logo-rectangle",
    dependencies=[
        guard(
            "UpdateOrganization",
            workspace=None,
            org="org_id",
            denied="Only admins can update organization branding",
        )
    ],
)
async def upload_org_logo_rectangle(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
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
) -> dict:
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
        # The deployment's enabled features: a policy gives each.
        "features": offered_features(settings.feature_flags),
    }


async def _org_workspace_payloads(
    org_id: str,
    service: OrganizationService,
    workspaces: list[OrganizationWorkspaceRecord],
) -> list[dict]:
    org = await service.get_organization(org_id=org_id)
    return [
        _workspace_payload(
            ws,
            org_logo_url=org.logo_url if org else None,
            org_logo_rect_url=org.logo_rectangle_url if org else None,
        )
        for ws in workspaces
    ]


@router.get(
    "/{org_id}/workspaces",
    dependencies=[guard("GetOrganization", workspace=None, org="org_id")],
)
async def list_org_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[dict]:
    # Org owners/admins manage the full org catalog; members only see workspaces
    # they already belong to.
    if await authz.allowed("ListOrganizationCatalog", user=current_user, org=org_id):
        workspaces = await service.list_all_workspaces(org_id=org_id)
    else:
        workspaces = await service.list_workspaces(org_id=org_id, user_id=current_user.id)
    return await _org_workspace_payloads(org_id, service, workspaces)


@router.post(
    "/{org_id}/workspaces/bulk-update",
    dependencies=[
        guard(
            "UpdateOrganization",
            workspace=None,
            org="org_id",
            denied="Only admins can edit workspaces",
        )
    ],
)
async def bulk_update_org_workspaces(
    org_id: str,
    body: OrganizationWorkspacesBulkUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
) -> dict:
    """Set the group of several workspaces of this organization at once."""
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


@router.get(
    "/{org_id}/workspace-seed-catalog",
    dependencies=[
        guard(
            "ListOrganizationCatalog",
            workspace=None,
            org="org_id",
            denied="Only admins can view the workspace seed catalog",
        )
    ],
)
async def get_org_workspace_seed_catalog() -> dict:
    """Instance catalog for the create-workspace picker (agents, apps, …)."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
        build_workspace_seed_catalog,
    )

    catalog = build_workspace_seed_catalog()
    return {
        key: [{"id": option.id, "label": option.label, "kind": option.kind} for option in options]
        for key, options in catalog.items()
    }


@router.get(
    "/{org_id}/member-workspaces",
    dependencies=[
        guard(
            "ListOrganizationCatalog",
            workspace=None,
            org="org_id",
            denied="Only admins can list member workspaces",
        )
    ],
)
async def list_org_member_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:
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


@router.put(
    "/{org_id}/members/{user_id}/workspaces",
    dependencies=[
        guard(
            "UpdateOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can assign workspaces",
        )
    ],
)
async def sync_org_member_workspaces(
    org_id: str,
    user_id: str,
    body: OrganizationMemberWorkspacesUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
) -> dict:
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
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

    # Each change is the caller's, checked by IAM at the workspace it touches:
    # an org owner or admin reaches every workspace of the organization through
    # their org-wide role, and gives there no role that grants more than they
    # hold. The role granted is never ``owner`` (the schema), and a workspace
    # owner is never taken out.
    iam_memberships = workspace_service.memberships
    held = await iam_memberships.roles_of(user_id)
    to_add = sorted(desired_ids - current_ids)
    to_remove: list[str] = []
    for workspace_id in sorted(current_ids - desired_ids):
        if held.get(workspace_container(org_id, workspace_id)) == "owner":
            skipped_owner.append(workspace_id)
        else:
            to_remove.append(workspace_id)
    try:
        # Every right is checked before the first change, so a refusal of one
        # leaves the member's workspaces as they were.
        for workspace_id in to_add:
            await iam_memberships.check(
                user_id,
                body.workspace_role,
                workspace_container(org_id, workspace_id),
                by=current_user,
            )
        for workspace_id in to_remove:
            await iam_memberships.check(
                user_id, None, workspace_container(org_id, workspace_id), by=current_user
            )
        # IAM's GrantNotHeldError (what the role grants beyond what the caller
        # holds) is a 403 that names it, through the service handlers.
        for workspace_id in to_add:
            await iam_memberships.grant(
                user_id,
                body.workspace_role,
                workspace_container(org_id, workspace_id),
                by=current_user,
            )
            added.append(workspace_id)
        for workspace_id in to_remove:
            if await iam_memberships.revoke(
                user_id, workspace_container(org_id, workspace_id), by=current_user
            ):
                removed.append(workspace_id)
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc

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


@router.get(
    "/{org_id}/members",
    dependencies=[
        guard(
            "ListOrganizationMembers",
            org="org_id",
            literal="-",
            denied="Only admins can list organization members",
        )
    ],
)
async def list_org_members(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationMember]:
    rows = await service.list_members(org_id=org_id)
    return [OrganizationMember(**row.__dict__) for row in rows]


def _invite_profile(invite: OrganizationMemberInvite) -> dict[str, str]:
    """What the invite sets about the person in this organization."""
    profile = {
        "organization": invite.organization,
        "job_title": invite.job_title,
        "bio": invite.bio,
        "service_line": invite.service_line,
        "country": invite.country,
        "interest": invite.interest,
    }
    return {key: value for key, value in profile.items() if value is not None}


async def _sync_member_drive(
    db: AsyncSession, object_storage: ObjectStorageService, user_id: str
) -> None:
    """Refresh org_member.json and .USER.md in the member's drive (best effort)."""
    await db.flush()
    await user_drive_profile.sync_user_drive_profile_safely(
        db, object_storage, user_id, datetime.now(UTC)
    )


@router.get(
    "/{org_id}/members/{user_id}",
    dependencies=[
        guard(
            "ListOrganizationMembers",
            org="org_id",
            literal="-",
            denied="Only admins can view member details",
        )
    ],
)
async def get_org_member_details(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMemberDetails:
    """One member: their account, their profile in this org and their workspaces here."""
    details = await service.get_member_details(org_id=org_id, user_id=user_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Member not found")
    workspaces = await service.get_member_workspace_access(org_id=org_id, user_id=user_id)
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


@router.post(
    "/{org_id}/members/invite",
    dependencies=[
        guard(
            "InviteOrganizationMember",
            org="org_id",
            literal="-",
            denied="Only admins can invite members",
        )
    ],
)
async def invite_org_member(
    org_id: str,
    invite: OrganizationMemberInvite,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service_for_org_invite),
    email_service: EmailService | None = Depends(_get_email_service),
    invites: InvitationService = Depends(invites_runtime.get_invitation_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> OrganizationMember | dict[str, object]:
    # IAM decided who may invite (the guard) and decides what each role may
    # give (``by``); ``role`` only tells whether the caller may name an owner.
    role = await service.get_organization_role(current_user.id, org_id)
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

    # Someone with no account yet is invited through an identity provider: the
    # provider makes them exist, IAM holds the roles for their email, and the
    # first sign-in claims them. Someone who already has an account is added
    # directly.
    existing_user = await invites.persistence.user_id_by_email(email)
    if existing_user is None:
        org = await service.get_organization(org_id)
        workspace = (
            await workspace_service.get_workspace(invite.workspace_id)
            if invite.workspace_id
            else None
        )
        try:
            outcome = await invites.invite(
                email=email,
                name=invite.name,
                provider=invite.provider,
                organization_id=org_id,
                org_role=invite.role,
                workspace_id=invite.workspace_id,
                workspace_role=invite.workspace_role if invite.workspace_id else None,
                invited_by=current_user.id,
                inviter_name=current_user.name,
                organization_name=org.name if org else None,
                workspace_name=workspace.name if workspace else None,
                may_grant_owner=role == "owner",
                profile=_invite_profile(invite),
                policy_ids=invite.policy_ids,
            )
        except OwnerGrantRefusedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except NoProviderError as exc:
            # Nobody is signed up here: without an identity provider there is
            # nowhere for the person to sign in.
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PROVIDER_FAILURES as exc:
            raise provider_failure(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return invite_result(outcome)

    # The policies the invitation carries, checked and attached as the inviting
    # person before anything is made (IAM refuses one they may not attach or do
    # not hold): a refusal leaves no membership behind.
    carried: tuple[str, ...] = ()
    if invite.policy_ids:
        try:
            carried = await invites.attach_policies(
                user_id=existing_user,
                organization_id=org_id,
                workspace_id=invite.workspace_id,
                policy_ids=invite.policy_ids,
                by=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        member = await service.invite_member(
            org_id=org_id,
            email=email,
            role=invite.role,
            now=datetime.now(UTC).replace(tzinfo=None),
            by=current_user,
        )
    except MembershipDenied as exc:
        if carried:
            await invites.detach_policies(
                user_id=existing_user,
                organization_id=org_id,
                workspace_id=invite.workspace_id,
                policy_ids=carried,
            )
        raise _member_denied(str(exc)) from exc
    except OrganizationMemberAlreadyExistsError as exc:
        # Re-inviting is how an admin resends the notice that never arrived, so
        # keep the membership as-is and send it again rather than rejecting the
        # only retry path they have.
        member = await _find_org_member(service, org_id=org_id, user_id=exc.user_id)
        if member is None:
            raise HTTPException(status_code=400, detail="User is already a member") from exc

    if member is None:
        raise HTTPException(status_code=500, detail="Failed to create or find user for invite")

    profile = _invite_profile(invite)
    if profile:
        member = (
            await service.update_member_profile(
                org_id=org_id, user_id=member.user_id, name=None, **profile
            )
            or member
        )

    if invite.workspace_id:
        # An org admin puts people in the organization's workspaces whether or
        # not they belong to one (see ``sync_org_member_workspaces``): granted
        # by ``api`` after the org-level check, and never as ``owner`` (schema).
        try:
            ws_member = await workspace_service.invite_workspace_member(
                workspace_id=invite.workspace_id,
                email=email,
                role=invite.workspace_role,
                by=None,
            )
        except WorkspaceMemberAlreadyExistsError:
            ws_member = None
        if ws_member is not None:
            workspace_member_id = ws_member.id

    org = await service.get_organization(org_id)
    workspace = (
        await workspace_service.get_workspace(invite.workspace_id) if invite.workspace_id else None
    )
    sign_in_email_sent = await send_added_notice(
        email,
        inviter_name=current_user.name,
        organization_name=org.name if org else None,
        organization_role=invite.role,
        workspace_name=workspace.name if workspace else None,
        workspace_role=invite.workspace_role if invite.workspace_id else None,
        email_service=email_service or _get_email_service(request),
    )

    await _sync_member_drive(db, object_storage, member.user_id)
    return OrganizationMember(
        **member.__dict__,
        user_created=False,
        sign_in_email_sent=sign_in_email_sent,
        workspace_member_id=workspace_member_id,
    )


@router.patch(
    "/{org_id}/members/{user_id}",
    dependencies=[
        guard(
            "UpdateOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can update member roles",
        )
    ],
)
async def update_org_member(
    org_id: str,
    user_id: str,
    updates: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> OrganizationMember:
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if updates.role is not None:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        try:
            member = await service.update_member_role(
                org_id=org_id, user_id=user_id, role=updates.role, by=current_user
            )
        except MembershipDenied as exc:
            raise _member_denied(str(exc)) from exc
        except LastOwnerError as exc:
            raise HTTPException(status_code=400, detail="An organization needs an owner") from exc
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


@router.post(
    "/{org_id}/members/{user_id}/avatar",
    dependencies=[
        guard(
            "UpdateOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can update members",
        )
    ],
)
async def upload_org_member_avatar(
    org_id: str,
    user_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
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


@router.delete(
    "/{org_id}/members/{user_id}/avatar",
    dependencies=[
        guard(
            "UpdateOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can update members",
        )
    ],
)
async def remove_org_member_avatar(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
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


@router.delete(
    "/{org_id}/members/{user_id}",
    dependencies=[
        guard(
            "RemoveOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can remove members",
        )
    ],
)
async def remove_org_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    member = await service.get_organization_role(user_id=user_id, org_id=org_id)
    if member == "owner":
        # An owner is demoted first (``PATCH``): only an owner may do that.
        raise HTTPException(status_code=400, detail="Cannot remove the organization owner")

    try:
        removed = await service.remove_member(org_id=org_id, user_id=user_id, by=current_user)
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    await _sync_member_drive(db, object_storage, user_id)
    return {"message": "Member removed successfully"}


@router.get(
    "/{org_id}/domains",
    dependencies=[
        guard(
            "ListOrganizationDomains",
            org="org_id",
            literal="-",
            denied="Only admins can list organization domains",
        )
    ],
)
async def list_org_domains(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationDomain]:
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
            provider=row.provider,
        )
        for row in rows
    ]


@router.post(
    "/{org_id}/domains",
    dependencies=[
        guard(
            "AddOrganizationDomain",
            org="org_id",
            literal="-",
            denied="Only admins can add domains",
        )
    ],
)
async def add_org_domain(
    org_id: str,
    domain_data: OrganizationDomainCreate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDomain:

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


@router.post(
    "/{org_id}/domains/{domain_id}/verify",
    dependencies=[
        guard(
            "VerifyOrganizationDomain",
            org="org_id",
            id="domain_id",
            denied="Only admins can verify domains",
        )
    ],
)
async def verify_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDomain:

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
        provider=verified.provider,
    )


@router.put(
    "/{org_id}/domains/{domain_id}/provider",
    dependencies=[
        guard(
            "UpdateOrganizationDomain",
            org="org_id",
            id="domain_id",
            denied="Only admins can route domains",
        )
    ],
)
async def set_org_domain_provider(
    org_id: str,
    domain_id: str,
    update: OrganizationDomainProviderUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDomain:
    """Route logins of the domain to one of the engine's identity providers.
    Routing applies once the domain is verified."""
    if update.provider is not None:
        from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime as oidc_runtime

        providers, _ = await oidc_runtime.RUNTIME.identity.providers()
        if update.provider not in {p.name for p in providers}:
            raise HTTPException(status_code=400, detail="Unknown identity provider")
    row = await service.set_domain_provider(
        org_id=org_id, domain_id=domain_id, provider=update.provider
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    return OrganizationDomain(
        **{
            **row.__dict__,
            "verification_token": row.verification_token if not row.is_verified else None,
        }
    )


@router.delete(
    "/{org_id}/domains/{domain_id}",
    dependencies=[
        guard(
            "RemoveOrganizationDomain",
            org="org_id",
            id="domain_id",
            denied="Only admins can delete domains",
        )
    ],
)
async def delete_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:

    deleted = await service.delete_domain(org_id=org_id, domain_id=domain_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"message": "Domain removed successfully"}


@router.get(
    "/{org_id}/billing",
    dependencies=[
        guard(
            "GetBilling",
            org="org_id",
            denied="Only admins can manage billing",
        )
    ],
)
async def get_org_billing(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> BillingInfo:
    raise HTTPException(
        status_code=501,
        detail="Billing functionality is not yet implemented. This feature will be available in a future release.",
    )


@router.post(
    "/{org_id}/billing/upgrade",
    dependencies=[
        guard(
            "UpdateBilling",
            org="org_id",
            denied="Only admins can manage billing",
        )
    ],
)
async def upgrade_org_plan(
    org_id: str,
    upgrade: BillingUpgrade,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:

    raise HTTPException(
        status_code=501,
        detail="Billing upgrades are not yet implemented. Please contact support@naas.ai to discuss enterprise plans.",
    )


@router.post(
    "/{org_id}/billing/payment-method",
    dependencies=[
        guard(
            "UpdateBilling",
            org="org_id",
            denied="Only admins can manage billing",
        )
    ],
)
async def add_payment_method(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict:

    raise HTTPException(
        status_code=501,
        detail="Payment method management is not yet implemented. Billing features are coming soon.",
    )
