from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationRecord,
    OrganizationUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationDomainAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationPermissionError,
    OrganizationService,
    OrganizationSlugAlreadyExistsError,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
public_router = APIRouter()


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


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


class OrganizationMemberInvite(BaseModel):
    email: str = Field(..., min_length=1)
    role: str = Field(default="member", pattern=r"^(owner|admin|member)$")


class OrganizationMemberUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|member)$")


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
    await require_org_access(current_user.id, org_id, service)
    row = await service.get_organization(org_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_schema(row)


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


@router.get("/{org_id}/workspaces")
async def list_org_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[dict]:
    await require_org_access(current_user.id, org_id, service)

    org = await service.get_organization(org_id=org_id)
    org_logo_url = org.logo_url if org else None
    org_logo_rect_url = org.logo_rectangle_url if org else None

    workspaces = await service.list_workspaces(org_id=org_id, user_id=current_user.id)
    return [
        {
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "owner_id": ws.owner_id,
            "organization_id": ws.organization_id,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
            "logo_url": ws.logo_url,
            "logo_emoji": ws.logo_emoji,
            "organization_logo_url": org_logo_url,
            "organization_logo_rectangle_url": org_logo_rect_url,
        }
        for ws in workspaces
    ]


@router.get("/{org_id}/members")
async def list_org_members(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationMember]:
    await require_org_access(current_user.id, org_id, service)
    rows = await service.list_members(org_id=org_id)
    return [OrganizationMember(**row.__dict__) for row in rows]


@router.post("/{org_id}/members/invite")
async def invite_org_member(
    org_id: str,
    invite: OrganizationMemberInvite,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can invite members")

    try:
        member = await service.invite_member(
            org_id=org_id,
            email=invite.email,
            role=invite.role,
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except OrganizationMemberAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail="User is already a member") from exc

    if member is None:
        raise HTTPException(status_code=404, detail="User not found with this email")
    return OrganizationMember(**member.__dict__)


@router.patch("/{org_id}/members/{user_id}")
async def update_org_member(
    org_id: str,
    user_id: str,
    updates: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMember:
    role = await require_org_access(current_user.id, org_id, service)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update member roles")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    member = await service.update_member_role(org_id=org_id, user_id=user_id, role=updates.role)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return OrganizationMember(**member.__dict__)


@router.delete("/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
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
    return {"message": "Member removed successfully"}


@router.get("/{org_id}/domains")
async def list_org_domains(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationDomain]:
    await require_org_access(current_user.id, org_id, service)
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
    await require_org_access(current_user.id, org_id, service)
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
