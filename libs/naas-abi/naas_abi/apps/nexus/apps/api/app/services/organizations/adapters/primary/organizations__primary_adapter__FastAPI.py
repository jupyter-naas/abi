from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import offered_features
from naas_abi.apps.nexus.apps.api.app.core.timezones import valid_timezone
from naas_abi.apps.nexus.apps.api.app.services.auth import avatar_store, user_drive_profile
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    is_platform_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__FastAPI import (  # noqa: E501
    ALLOWED_AVATAR_EXTENSIONS,
    MAX_AVATAR_SIZE,
    _delete_old_avatar,
    _get_object_storage,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    LastOrgAdminError,
    MembershipDenied,
    UnknownUserError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    org_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.roles import (
    KEEP,
    HeldRolesView,
    MemberRolesInput,
    RoleChange,
    RoleOptionsView,
    RoleOptionView,
    RoleRefView,
    change_roles,
    held_roles,
    role_groups_of,
    role_options,
    roles_of_people,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations import domain_proof
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationDomainRecord,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    LastOwnerError,
    OrganizationDomainAlreadyExistsError,
    OrganizationDomainNotAllowedError,
    OrganizationHasWorkspacesError,
    OrganizationOwnerRemovalError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
    new_org_id,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    RESEND_LIMIT,
    check_invitation_mail_quota,
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.confinement import (
    outside_this_organization,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
    LAST_ORG_ADMIN,
    Grant,
    PeopleServicePort,
    UserStatus,
    WorkspaceAccess,
    added_result,
    capability_group_items,
    get_people_service,
    people_errors,
    people_status,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceUpdateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceService,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import resolve_stored_asset_url
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
public_router = APIRouter()


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def get_workspace_service_for_org_invite(
    db: AsyncSession = Depends(get_db),
) -> WorkspaceService:
    return WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))


# The organization's identity: Organization Settings > General edits them, the
# public branding (``OrganizationBranding``) never carries them.
ORGANIZATION_IDENTITY_FIELDS = (
    "legal_name",
    "registration_number",
    "vat_number",
    "website",
    "contact_email",
    "address_line1",
    "address_line2",
    "postal_code",
    "city",
    "country",
)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


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
    legal_name: str | None = None
    registration_number: str | None = None
    vat_number: str | None = None
    website: str | None = None
    contact_email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    # IANA time zone the analytics periods follow (Organization Settings > General).
    timezone: str = "UTC"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    current_user_role: str | None = None


class OrganizationIdentityFields(BaseModel):
    """The organization's identity (Organization Settings > General), on create and
    update alike. A blank value is no value: on update, it clears the field."""

    legal_name: str | None = Field(default=None, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    vat_number: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=2000)
    contact_email: str | None = Field(default=None, max_length=254)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)

    @field_validator(*ORGANIZATION_IDENTITY_FIELDS)
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("website")
    @classmethod
    def _website_is_http(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("website is an http(s) URL, such as https://example.com")
        return value

    @field_validator("contact_email")
    @classmethod
    def _contact_email_is_an_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _EMAIL.fullmatch(value):
            raise ValueError("contact_email is an email address")
        return value.lower()


class OrganizationCreate(OrganizationIdentityFields):
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


class OrganizationUpdate(OrganizationIdentityFields):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$"
    )
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
    # An IANA time zone (``Europe/Paris``): the organization's analytics periods
    # (and its workspaces') start at midnight there.
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _timezone_is_iana(cls, value: str | None) -> str:
        if value is None or not valid_timezone(value):
            raise ValueError("timezone is an IANA time zone, such as Europe/Paris or UTC")
        return value


class OrganizationMember(BaseModel):
    """One person of the organization's directory."""

    id: str
    organization_id: str
    user_id: str
    # Their organization role; null: workspace access only (no org permission).
    role: str | None
    # "organization" (a role in it) or "workspace" (only in one of its workspaces).
    source: str = "organization"
    # "invited" until their first sign-in, then "active".
    status: str = "active"
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
    # Their IAM principal, which the access pages link to (an account linked from
    # the old login has another id there).
    principal_id: str | None = None
    # Their level ("member", "viewer"; #1585), one choice for every workspace.
    level: str | None = None
    # They administer the organization ("<O> admins"; #1589).
    org_admin: bool = False
    user_created: bool = False
    sign_in_email_sent: bool = False
    workspace_member_id: str | None = None
    # Users › Role: their groups and policies at the organization.
    roles: list[RoleRefView] = Field(default_factory=list)

    @model_validator(mode="after")
    def _org_admin_of_role(self) -> OrganizationMember:
        self.org_admin = self.role in ("admin", "owner")
        return self


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
    # They administer it ("<W> admins", or as an org admin; #1589).
    admin: bool = False

    @model_validator(mode="after")
    def _admin_of_role(self) -> OrganizationMemberWorkspace:
        self.admin = self.role in ("admin", "owner")
        return self


class CapabilityGroupRef(BaseModel):
    id: str
    name: str
    owner_scope: str


class OrganizationMemberDetails(BaseModel):
    member: OrganizationMember
    account: OrganizationMemberAccount
    organization_profile: OrganizationMemberProfile
    workspaces: list[OrganizationMemberWorkspace]
    # The capability groups they are in, of this organization or the platform.
    capabilities: list[CapabilityGroupRef] = Field(default_factory=list)


class WorkspaceGrantInput(BaseModel):
    """A workspace of the organization the person works in, and whether they
    administer it (#1589). ``role``, the body of before: ``admin`` is ``admin``."""

    id: str = Field(..., min_length=1)
    admin: bool | None = None
    role: str | None = Field(default=None, pattern=r"^(admin|member|viewer)$")

    def is_admin(self) -> bool:
        return self.admin if self.admin is not None else self.role == "admin"


class OrganizationMemberInvite(BaseModel):
    email: str = Field(..., min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # Their level (None: keep theirs; someone with none who joins a workspace is a
    # Member), whether they administer the organization, the workspaces they join
    # (each with ``admin``) and capability groups (#1589). With no workspace and no
    # org admin they join "<O> people" (Viewer access at the organization's level).
    level: str | None = Field(default=None, pattern=r"^(viewer|member)$")
    org_admin: bool = False
    workspaces: list[WorkspaceGrantInput] = Field(default_factory=list, max_length=100)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    # The body of before (CLI, agent tools): ``role`` admin is ``org_admin``; owner
    # is not assigned any more; the single ``workspace_id`` is ``workspaces``' first.
    role: str | None = Field(default=None, pattern=r"^(owner|admin|member)$")
    workspace_id: str | None = Field(default=None, min_length=1)
    workspace_role: str | None = Field(default=None, pattern=r"^(admin|member|viewer)$")
    # The identity provider to invite through; by default the one the email's
    # domain routes to, else the default provider.
    provider: str | None = Field(default=None, min_length=1, max_length=32)
    # Customer policies are no longer attached to a person (#1589): refused.
    policy_ids: list[str] = Field(default_factory=list, max_length=20)
    # Member profile in this organization (Organization Settings > Users > Create user).
    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)

    def workspace_grants(self) -> list[WorkspaceGrantInput]:
        """``workspaces``, with the legacy ``workspace_id`` among them, each once."""
        named = list(self.workspaces)
        if self.workspace_id:
            named.insert(0, WorkspaceGrantInput(id=self.workspace_id, role=self.workspace_role))
        unique: dict[str, WorkspaceGrantInput] = {}
        for grant in named:
            unique.setdefault(grant.id, grant)
        return list(unique.values())

    def grant(self, org_id: str) -> Grant:
        """The people service's grant: ``ValueError`` (400) for what is not one."""
        if self.policy_ids:
            raise ValueError("Policies are no longer attached to a person: name capability groups")
        if self.role == "owner":
            raise ValueError("Owner is no longer assigned: make them an org admin")
        workspaces = self.workspace_grants()
        level = self.level
        if level is None and workspaces and any(w.role for w in workspaces):
            # The roles of before: the highest that is a level.
            roles = {w.role for w in workspaces}
            level = "member" if roles & {"admin", "member"} else "viewer"
        return Grant(
            org_id,
            level=level,  # type: ignore[arg-type]
            org_admin=self.org_admin or self.role == "admin",
            workspaces=tuple(WorkspaceAccess(w.id, w.is_admin()) for w in workspaces),
            capabilities=tuple(self.capabilities),
        )


class OrganizationMemberUpdate(BaseModel):
    # Whether they administer the organization, their level (everywhere) and the
    # capability groups wanted (the full set, of the listed ones; #1589).
    org_admin: bool | None = None
    level: str | None = Field(default=None, pattern=r"^(viewer|member)$")
    capabilities: list[str] | None = Field(default=None, max_length=50)
    # The body of before: ``admin`` is ``org_admin``, ``member`` is not.
    role: str | None = Field(default=None, pattern=r"^(owner|admin|member)$")
    # No name: a member's full name is always their account name (users.name).
    organization: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)
    service_line: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    interest: str | None = Field(default=None, max_length=1000)


class OrganizationMemberWorkspacesUpdate(BaseModel):
    """The workspaces of the organization the member works in, each with whether
    they administer it: the full set (those left out are left). ``workspace_ids``
    and ``workspace_role``, the body of before."""

    workspaces: list[WorkspaceGrantInput] | None = Field(default=None, max_length=500)
    workspace_ids: list[str] = Field(default_factory=list)
    workspace_role: str = Field(default="member", pattern=r"^(admin|member|viewer)$")

    def wanted(self) -> list[WorkspaceAccess]:
        if self.workspaces is not None:
            return [WorkspaceAccess(w.id, w.is_admin()) for w in self.workspaces]
        admin = self.workspace_role == "admin"
        return [WorkspaceAccess(w, admin) for w in dict.fromkeys(self.workspace_ids)]


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
    # Until verified: publish ``verification_token`` as a TXT record at
    # ``verification_record`` (``_nexus-verify.<domain>``), then verify.
    verification_token: str | None = None
    verification_record: str | None = None
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
    # Each organization with the caller's role there, read once from IAM: the account
    # menu decides Organization Settings from this one answer.
    roles = await service.organization_roles(current_user.id, [row.id for row in rows])
    return [Organization(**row.__dict__, current_user_role=roles.get(row.id)) for row in rows]


@router.get("/{org_id}", dependencies=[guard("GetOrganization", workspace=None, org="org_id")])
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> Organization:
    if (outside := outside_this_organization(org_id)) is not None:
        # In a view the shell reads the organization of the viewed workspace, and no other
        # (``view_as/AGENTS.md``, "Confined to the workspace").
        raise HTTPException(status_code=403, detail=outside)
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
            identity={field: getattr(org, field) for field in ORGANIZATION_IDENTITY_FIELDS},
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
    try:
        row = await service.update_organization(
            org_id=org_id,
            updates=OrganizationUpdateInput(
                **updates.model_dump(exclude_unset=True),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
                set_fields=set(updates.model_dump(exclude_unset=True).keys()) | {"updated_at"},
            ),
        )
    except OrganizationSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Slug already exists") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_schema(row)


@router.delete(
    "/{org_id}",
    dependencies=[
        # The platform admin's (#1585): on the platform-level organization_record.
        guard(
            "DeletePlatformOrganization",
            workspace=None,
            id="org_id",
            denied="Only the platform administrators can delete an organization",
        )
    ],
)
async def delete_organization(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> dict[str, str]:
    """Delete an organization that has no workspace left (409 naming those it still
    has): its row, its IAM container with what it owns, its access policy."""
    try:
        deleted = await service.delete_organization(org_id)
    except OrganizationHasWorkspacesError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"status": "deleted", "id": org_id}


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
    people: PeopleServicePort = Depends(get_people_service),
) -> dict:
    """Set the workspaces of the organization the member works in, each with whether
    they administer it (#1589): they join "<W> workspace" (and "<W> admins") of each
    named, and leave those of the others. All or nothing, each change checked as
    the caller. Out of every workspace and not an org admin, they stay among the
    organization's people ("<O> people")."""
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    org_workspaces = [ws.id for ws in await service.list_all_workspaces(org_id=org_id)]
    wanted = body.wanted()
    unknown = sorted({w.id for w in wanted} - set(org_workspaces))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Workspaces not in this organization: {', '.join(unknown)}",
        )
    before = {
        row.workspace_id
        for row in await service.list_workspace_memberships(org_id=org_id)
        if row.user_id == user_id
    }
    with people_errors(_member_denied):
        await people.change_access(
            user_id=user_id,
            organization_id=org_id,
            by=current_user,
            workspaces=wanted,
            among=org_workspaces,
        )
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
        "added": sorted({row["workspace_id"] for row in refreshed} - before),
        "removed": sorted(before - {row["workspace_id"] for row in refreshed}),
        "skipped_owner": [],
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
    roles = await roles_of_people(
        org_container(org_id), [str(r.principal_id) for r in rows if r.principal_id]
    )
    return [
        OrganizationMember(**row.__dict__, roles=roles.get(str(row.principal_id), []))
        for row in rows
    ]


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


async def _org_workspace_groups(
    service: OrganizationService, org_id: str
) -> list[tuple[str, str | None, str | None, str, str]]:
    workspaces = await service.list_all_workspaces(org_id=org_id)
    return await MEMBERSHIPS.workspace_groups(org_id, [w.id for w in workspaces])


@router.get(
    "/{org_id}/members/role-options",
    dependencies=[
        guard(
            "ListOrganizationMembers",
            org="org_id",
            literal="-",
            denied="Only admins can list organization members",
        )
    ],
)
async def org_member_role_options(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> RoleOptionsView:
    """What a member's Role in the organization may hold, as the caller may give it:
    the levels, its people and admins groups, its workspaces' groups (to place them
    there), its other groups the caller lists, and the policies the caller may attach
    here."""
    container = org_container(org_id)
    groups = await role_groups_of(container)
    more: list[RoleOptionView] = []
    for ws, own, admins, own_name, admins_name in await _org_workspace_groups(service, org_id):
        if own:
            more.append(RoleOptionView(kind="group", id=own, name=own_name, workspace=ws))
        if admins:
            more.append(
                RoleOptionView(
                    kind="group", id=admins, name=admins_name, workspace=ws, administers=True
                )
            )
    return await role_options(current_user, container, groups, listed_at=container, more=more)


@router.get(
    "/{org_id}/members/{user_id}/roles",
    dependencies=[
        guard(
            "ListOrganizationMembers",
            org="org_id",
            literal="-",
            denied="Only admins can view member details",
        )
    ],
)
async def org_member_roles(org_id: str, user_id: str) -> HeldRolesView:
    """What a member holds in the organization (its groups and its workspaces'), as a
    change of their Role starts from."""
    try:
        principal = await MEMBERSHIPS.principal_id(user_id)
    except UnknownUserError as exc:
        raise HTTPException(status_code=404, detail="Member not found") from exc
    container = org_container(org_id)
    return await held_roles(container, principal, await role_groups_of(container))


@router.put(
    "/{org_id}/members/{user_id}/roles",
    dependencies=[
        guard(
            "UpdateOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can update member roles",
        )
    ],
)
async def set_org_member_roles(
    org_id: str,
    user_id: str,
    body: MemberRolesInput,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> MemberRolesInput:
    """Make a member's Role in the organization the groups and policies asked: their
    level, the org admin seat and their workspaces (each with its admins group) all or
    nothing through the people service (the last org admin stays), the other groups
    and the policies attached here as the caller."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own access")
    try:
        principal = await MEMBERSHIPS.principal_id(user_id)
    except UnknownUserError as exc:
        raise HTTPException(status_code=404, detail="Member not found") from exc
    container = org_container(org_id)
    groups = await role_groups_of(container)
    ws_groups = await _org_workspace_groups(service, org_id)
    wanted = set(body.groups)

    def placed(source: set[str]) -> dict[str, bool]:
        return {
            ws: bool(admins and admins in source)
            for ws, own, admins, _o, _a in ws_groups
            if (own and own in source) or (admins and admins in source)
        }

    async def seats(change: RoleChange, held: set[str]) -> set[str]:
        desired, current = placed(wanted), placed(held)
        workspaces = (
            None
            if desired == current
            else [WorkspaceAccess(id=ws, admin=admin) for ws, admin in sorted(desired.items())]
        )
        level = None if change.level in (KEEP, None) else str(change.level)
        if level is not None or change.admin is not None or workspaces is not None:
            with people_errors(_member_denied):
                await people.change_access(
                    user_id=user_id,
                    organization_id=org_id,
                    by=current_user,
                    level=level,
                    org_admin=change.admin,
                    workspaces=workspaces,
                    among=[ws for ws, *_rest in ws_groups],
                )
        return {g for _ws, own, admins, _o, _a in ws_groups for g in (own, admins) if g}

    held, _ = await MEMBERSHIPS.held_at(container, principal)
    await change_roles(
        user=current_user,
        scope=container,
        principal_id=principal,
        body=body,
        groups=groups,
        reaches_otherwise=bool(held & groups.elsewhere),
        attach_at=container,
        seats=seats,
    )
    return await held_roles(container, principal, groups)


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
    summary = await MEMBERSHIPS.access_of(user_id)
    org_scope = org_container(org_id)
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
        capabilities=[
            CapabilityGroupRef(id=gid, name=name, owner_scope=owner)
            for gid, name, owner in (summary.capabilities if summary else ())
            if owner in (org_scope, PLATFORM)
        ],
    )


@router.get(
    "/{org_id}/capability-groups",
    dependencies=[
        guard(
            "InviteOrganizationMember",
            org="org_id",
            literal="-",
            denied="Only admins can invite members",
        )
    ],
)
async def list_org_capability_groups(
    org_id: str, current_user: User = Depends(get_current_user_required)
) -> dict[str, object]:
    """The capability groups a person of the organization may join beside their
    level: its own, then the platform's. The model's own groups (levels, workspace
    and admin groups, "<O> people") are not listed."""
    return {"items": await capability_group_items(org_id)}


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
    people: PeopleServicePort = Depends(get_people_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict[str, object]:
    """Create the person's platform account, or link the one their email has, and
    put them in the organization (#1589): their level, org admin, each workspace
    named (with whether they administer it) and capability groups; with no
    workspace and no org admin, among the organization's people. The answer is the
    same either way. IAM decided who may invite (the guard) and decides what each
    group may be given by the caller (``by``)."""
    try:
        grant = invite.grant(org_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    email = invite.email.lower().strip()
    await check_rate_limit(
        get_rate_limit_identifier(request, current_user.id),
        "/api/organizations/members/invite",
    )
    await check_rate_limit(f"email:{email}", "/api/organizations/members/invite")

    workspaces = invite.workspace_grants()
    if workspaces:
        org_workspaces = {ws.id for ws in await service.list_all_workspaces(org_id=org_id)}
        if any(w.id not in org_workspaces for w in workspaces):
            raise HTTPException(
                status_code=400,
                detail="workspace_id must belong to this organization",
            )
    await check_invitation_mail_quota(org_id, workspaces[0].id if workspaces else None)
    with people_errors(_member_denied):
        result = await people.create_or_link(
            email=email,
            name=invite.name,
            provider=invite.provider,
            grant=grant,
            by=current_user,
            profile=_invite_profile(invite),
            organization_id=org_id,
        )
    member = await service.get_organization_member(org_id=org_id, user_id=result.user.id)
    await _sync_member_drive(db, object_storage, result.user.id)
    return added_result(result, OrganizationMember(**member.__dict__) if member else None)


@router.post(
    "/{org_id}/members/{user_id}/resend",
    dependencies=[
        guard(
            "InviteOrganizationMember",
            org="org_id",
            literal="-",
            denied="Only admins can invite members",
        )
    ],
)
async def resend_org_member_invite(
    org_id: str,
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    people: PeopleServicePort = Depends(get_people_service),
) -> dict[str, bool]:
    """Send an invited member of the directory their sign-in mail again; 409 once
    they signed in. Once a window for one person, then the invite limits
    (inviting user, address, the organization's day of mail)."""
    if not await service.in_directory(org_id, user_id):
        raise HTTPException(status_code=404, detail="Member not found")
    user = await people.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if people_status(user.status) != UserStatus.INVITED:
        raise HTTPException(status_code=409, detail="This member has already signed in")
    # The person's own limit first: a refused resend spends nothing else.
    await check_rate_limit(f"invitation:{user_id}", RESEND_LIMIT, limit=1)
    await check_rate_limit(
        get_rate_limit_identifier(request, current_user.id),
        "/api/organizations/members/invite",
    )
    await check_rate_limit(f"email:{user.email.lower()}", "/api/organizations/members/invite")
    await check_invitation_mail_quota(org_id, None)
    with people_errors(_member_denied):
        sent = await people.resend(user_id=user_id, by=current_user)
    return {"sign_in_email_sent": sent}


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
    people: PeopleServicePort = Depends(get_people_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> OrganizationMember:
    """Change a member's access in the organization (#1589: org admin, level, the
    capability groups wanted), all or nothing, and their profile here. 409 when the
    last org admin would stop being one."""
    member = await service.get_organization_member(org_id=org_id, user_id=user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if updates.role == "owner":
        raise HTTPException(
            status_code=400, detail="Owner is no longer assigned: make them an org admin"
        )
    org_admin = updates.org_admin
    if org_admin is None and updates.role is not None:
        org_admin = updates.role == "admin"
    if org_admin is not None or updates.level is not None or updates.capabilities is not None:
        if user_id == current_user.id and (org_admin is not None or updates.level is not None):
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        with people_errors(_member_denied):
            await people.change_access(
                user_id=user_id,
                organization_id=org_id,
                by=current_user,
                level=updates.level,
                org_admin=org_admin,
                capabilities=updates.capabilities,
            )
        member = await service.get_organization_member(org_id=org_id, user_id=user_id)
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


@router.delete(
    "/{org_id}/members/{user_id}/access",
    dependencies=[
        guard(
            "RemoveOrganizationMember",
            org="org_id",
            id="user_id",
            denied="Only admins can remove members",
        )
    ],
)
async def remove_org_member_access(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
    db: AsyncSession = Depends(get_db),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    """Remove someone from the organization in one step: every group of it they are
    in, its workspaces' included (Org settings › Users › Remove from organization;
    ``OrganizationService.remove_from_organization``). Their platform account and
    level stay. The last org admin is a 409. ``DELETE /members/{user_id}`` takes
    the org role alone."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")
    try:
        left = await service.remove_from_organization(
            org_id=org_id, user_id=user_id, by=current_user
        )
    except OrganizationOwnerRemovalError as exc:
        raise HTTPException(status_code=400, detail="Cannot remove the organization owner") from exc
    except LastOrgAdminError as exc:
        raise HTTPException(status_code=409, detail=LAST_ORG_ADMIN) from exc
    except LastOwnerError as exc:
        names = {ws.id: ws.name for ws in await service.list_all_workspaces(org_id=org_id)}
        workspace = workspace_of(exc.scope) or ""
        raise HTTPException(
            status_code=409,
            detail=(
                f"They are the last owner of {names.get(workspace, workspace)}: "
                "give it another owner first"
            ),
        ) from exc
    except MembershipDenied as exc:
        raise _member_denied(str(exc)) from exc
    if left is None:
        raise HTTPException(status_code=404, detail="Member not found")
    await _sync_member_drive(db, object_storage, user_id)
    return {"message": "Removed from the organization", "workspace_ids": left}


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
    return [_domain_view(row) for row in rows]


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

    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        row = await service.add_domain(org_id=org_id, domain=domain_data.domain, now=now)
    except OrganizationDomainNotAllowedError as exc:
        raise HTTPException(
            status_code=400, detail="A public mail domain belongs to no organization"
        ) from exc
    except OrganizationDomainAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="Domain already registered") from exc
    # Its record already published: verified at once.
    if not row.is_verified and await domain_proof.proven(row.domain, row.verification_token):
        row = await service.verify_domain(org_id=org_id, domain_id=row.id, verified_at=now) or row
    return _domain_view(row)


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
    # The organization proves it controls the domain (its TXT record); a platform
    # administrator may vouch for it instead.
    if not await domain_proof.proven(
        domain.domain, domain.verification_token
    ) and not await is_platform_admin(current_user.id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Publish a TXT record {domain_proof.proof_name(domain.domain)} with the "
                "value of verification_token, then verify again"
            ),
        )

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


def _domain_view(row: OrganizationDomainRecord) -> OrganizationDomain:
    pending = not row.is_verified
    return OrganizationDomain(
        **{
            **row.__dict__,
            "verification_token": row.verification_token if pending else None,
            "verification_record": domain_proof.proof_name(row.domain) if pending else None,
        }
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
    return _domain_view(row)


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
