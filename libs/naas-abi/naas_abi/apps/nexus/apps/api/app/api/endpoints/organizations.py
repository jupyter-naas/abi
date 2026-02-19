"""
Organizations API endpoints.
Public branding endpoint (no auth) + authenticated CRUD.
Organizations sit above Workspaces in the hierarchy and own branding configuration.
"""

import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User, get_current_user_required)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import (OrganizationDomainModel,
                                                     OrganizationMemberModel,
                                                     OrganizationModel,
                                                     WorkspaceMemberModel,
                                                     WorkspaceModel)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
public_router = APIRouter()


# ============ Pydantic Schemas ============

class OrganizationBranding(BaseModel):
    """Public branding data returned without authentication."""
    id: str
    name: str
    slug: str
    logo_url: str | None = None              # Square logo (icon, sidebar)
    logo_rectangle_url: str | None = None     # Wide/horizontal logo (login page, headers)
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
    default_theme: str | None = None             # "light", "dark", or null (system)


class Organization(BaseModel):
    """Full organization model (authenticated)."""
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
    """Create a new organization."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$')
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
    """Update an organization's branding."""
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
    """Organization member model."""
    id: str
    organization_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None


class OrganizationMemberInvite(BaseModel):
    """Invite a member to an organization."""
    email: str = Field(..., min_length=1)
    role: str = Field(default="member", pattern=r'^(owner|admin|member)$')


class OrganizationMemberUpdate(BaseModel):
    """Update organization member role."""
    role: str = Field(..., pattern=r'^(owner|admin|member)$')


class OrganizationDomain(BaseModel):
    """Organization domain model."""
    id: str
    organization_id: str
    domain: str
    is_verified: bool
    verification_token: str | None = None
    created_at: datetime | None = None
    verified_at: datetime | None = None


class OrganizationDomainCreate(BaseModel):
    """Add a domain to an organization."""
    domain: str = Field(..., min_length=3, max_length=255, pattern=r'^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$')


# ============ Helpers ============

def _to_schema(row: OrganizationModel) -> Organization:
    return Organization(
        id=row.id,
        name=row.name,
        slug=row.slug,
        owner_id=row.owner_id,
        logo_url=row.logo_url,
        logo_rectangle_url=row.logo_rectangle_url,
        logo_emoji=row.logo_emoji,
        primary_color=row.primary_color,
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
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_branding(row: OrganizationModel) -> OrganizationBranding:
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


# Upload directory for organization logos
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
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


async def get_org_role(user_id: str, org_id: str, db: AsyncSession) -> str | None:
    """Get user's role in an organization. Returns None if not a member."""
    result = await db.execute(
        select(OrganizationMemberModel.role).where(
            (OrganizationMemberModel.organization_id == org_id)
            & (OrganizationMemberModel.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def require_org_access(user_id: str, org_id: str, db: AsyncSession) -> str:
    """Check that user has access to an organization. Returns role. Raises 403 if not."""
    role = await get_org_role(user_id, org_id, db)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this organization")
    return role


# ============ PUBLIC Endpoints (no auth) ============

@public_router.get("/slug/{slug}/branding")
async def get_organization_branding(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> OrganizationBranding:
    """
    Get organization branding by slug. PUBLIC endpoint - no authentication required.
    This is called by the login page before the user authenticates.
    """
    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.slug == slug)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_branding(row)


# ============ Authenticated Endpoints ============

@router.get("")
async def list_organizations(
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[Organization]:
    """List organizations the current user is a member of (or owns)."""
    result = await db.execute(
        select(OrganizationModel)
        .outerjoin(
            OrganizationMemberModel,
            OrganizationModel.id == OrganizationMemberModel.organization_id,
        )
        .where(
            (OrganizationModel.owner_id == current_user.id)
            | (OrganizationMemberModel.user_id == current_user.id)
        )
        .distinct()
        .order_by(OrganizationModel.name)
    )
    return [_to_schema(row) for row in result.scalars().all()]


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Get an organization by ID. Requires membership."""
    await require_org_access(current_user.id, org_id, db)
    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.id == org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_schema(row)


@router.post("")
async def create_organization(
    org: OrganizationCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Create a new organization. The current user becomes the owner."""
    # Check slug uniqueness
    existing = await db.execute(
        select(OrganizationModel).where(OrganizationModel.slug == org.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    org_id = f"org-{uuid4().hex[:12]}"
    now = datetime.now(UTC).replace(tzinfo=None)

    organization = OrganizationModel(
        id=org_id,
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
        created_at=now,
        updated_at=now,
    )
    db.add(organization)

    member = OrganizationMemberModel(
        id=str(uuid4()),
        organization_id=org_id,
        user_id=current_user.id,
        role="owner",
        created_at=now,
    )
    db.add(member)
    await db.flush()

    return _to_schema(organization)


@router.patch("/{org_id}")
async def update_organization(
    org_id: str,
    updates: OrganizationUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Update an organization's branding. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update organization branding")

    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    org.updated_at = datetime.now(UTC).replace(tzinfo=None)

    await db.flush()
    return _to_schema(org)


@router.post("/{org_id}/upload-logo-square")
async def upload_org_logo_square(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a square logo image for an organization.
    Returns JSON with logo_url (relative path under /uploads).
    """
    role = await require_org_access(current_user.id, org_id, db)
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
    with open(filepath, "wb") as f:
        f.write(contents)

    # Update org
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Delete old local file if previously uploaded
    if org.logo_url and org.logo_url.startswith("/uploads/org-logos/"):
        try:
            old = ORG_LOGO_UPLOAD_DIR / os.path.basename(org.logo_url)
            if old.exists():
                old.unlink()
        except Exception:
            pass

    org.logo_url = f"/uploads/org-logos/{filename}"
    await db.flush()

    return {"logo_url": org.logo_url}


@router.post("/{org_id}/upload-logo-rectangle")
async def upload_org_logo_rectangle(
    org_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a rectangle (wide) logo image for an organization."""
    role = await require_org_access(current_user.id, org_id, db)
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
    with open(filepath, "wb") as f:
        f.write(contents)

    # Update org
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Delete old local file if previously uploaded
    if org.logo_rectangle_url and org.logo_rectangle_url.startswith("/uploads/org-logos/"):
        try:
            old = ORG_LOGO_UPLOAD_DIR / os.path.basename(org.logo_rectangle_url)
            if old.exists():
                old.unlink()
        except Exception:
            pass

    org.logo_rectangle_url = f"/uploads/org-logos/{filename}"
    await db.flush()

    return {"logo_rectangle_url": org.logo_rectangle_url}


@router.get("/{org_id}/workspaces")
async def list_org_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List workspaces belonging to an organization that the user can access."""
    await require_org_access(current_user.id, org_id, db)

    # Fetch org once to provide inherited branding (logos)
    org_res = await db.execute(
        select(OrganizationModel.logo_url, OrganizationModel.logo_rectangle_url)
        .where(OrganizationModel.id == org_id)
    )
    org_row = org_res.first()
    org_logo_url = org_row[0] if org_row else None
    org_logo_rect_url = org_row[1] if org_row else None

    result = await db.execute(
        select(WorkspaceModel)
        .outerjoin(WorkspaceMemberModel, WorkspaceModel.id == WorkspaceMemberModel.workspace_id)
        .where(
            (WorkspaceModel.organization_id == org_id)
            & (
                (WorkspaceModel.owner_id == current_user.id)
                | (WorkspaceMemberModel.user_id == current_user.id)
            )
        )
        .distinct()
        .order_by(WorkspaceModel.name)
    )
    workspaces = result.scalars().all()
    # Include workspace logo and inherited organization logos to allow UI fallback
    response: list[dict] = []
    for ws in workspaces:
        response.append({
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "owner_id": ws.owner_id,
            "organization_id": ws.organization_id,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
            # Branding
            "logo_url": ws.logo_url,
            "logo_emoji": ws.logo_emoji,
            "organization_logo_url": org_logo_url,
            "organization_logo_rectangle_url": org_logo_rect_url,
        })
    return response


@router.get("/{org_id}/members")
async def list_org_members(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationMember]:
    """List members of an organization. Requires membership."""
    await require_org_access(current_user.id, org_id, db)

    # Get members with user info
    from naas_abi.apps.nexus.apps.api.app.models import UserModel
    result = await db.execute(
        select(OrganizationMemberModel, UserModel)
        .join(UserModel, OrganizationMemberModel.user_id == UserModel.id)
        .where(OrganizationMemberModel.organization_id == org_id)
        .order_by(OrganizationMemberModel.created_at)
    )

    members = []
    for member, user in result.all():
        members.append(OrganizationMember(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role=member.role,
            email=user.email,
            name=user.name,
            created_at=member.created_at,
        ))

    return members


@router.post("/{org_id}/members/invite")
async def invite_org_member(
    org_id: str,
    invite: OrganizationMemberInvite,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Invite a member to an organization. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can invite members")

    # Find user by email
    from naas_abi.apps.nexus.apps.api.app.models import UserModel
    result = await db.execute(
        select(UserModel).where(UserModel.email == invite.email)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found with this email")

    # Check if already a member
    existing = await db.execute(
        select(OrganizationMemberModel).where(
            (OrganizationMemberModel.organization_id == org_id)
            & (OrganizationMemberModel.user_id == user.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")

    # Create membership
    now = datetime.now(UTC).replace(tzinfo=None)
    member = OrganizationMemberModel(
        id=str(uuid4()),
        organization_id=org_id,
        user_id=user.id,
        role=invite.role,
        created_at=now,
    )
    db.add(member)
    await db.flush()

    return OrganizationMember(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email,
        name=user.name,
        created_at=member.created_at,
    )


@router.patch("/{org_id}/members/{user_id}")
async def update_org_member(
    org_id: str,
    user_id: str,
    updates: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Update an organization member's role. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update member roles")

    # Can't change your own role
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Get member
    result = await db.execute(
        select(OrganizationMemberModel).where(
            (OrganizationMemberModel.organization_id == org_id)
            & (OrganizationMemberModel.user_id == user_id)
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Update role
    member.role = updates.role
    await db.flush()

    # Get user info
    from naas_abi.apps.nexus.apps.api.app.models import UserModel
    user_result = await db.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = user_result.scalar_one()

    return OrganizationMember(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email,
        name=user.name,
        created_at=member.created_at,
    )


@router.delete("/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a member from an organization. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can remove members")

    # Can't remove yourself
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    # Get member
    result = await db.execute(
        select(OrganizationMemberModel).where(
            (OrganizationMemberModel.organization_id == org_id)
            & (OrganizationMemberModel.user_id == user_id)
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Can't remove the owner
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the organization owner")

    await db.delete(member)
    await db.flush()

    return {"message": "Member removed successfully"}


# ============ Organization Domains ============

@router.get("/{org_id}/domains")
async def list_org_domains(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationDomain]:
    """List domains for an organization. Requires membership."""
    await require_org_access(current_user.id, org_id, db)

    result = await db.execute(
        select(OrganizationDomainModel)
        .where(OrganizationDomainModel.organization_id == org_id)
        .order_by(OrganizationDomainModel.created_at)
    )
    domains = result.scalars().all()

    return [
        OrganizationDomain(
            id=domain.id,
            organization_id=domain.organization_id,
            domain=domain.domain,
            is_verified=domain.is_verified,
            verification_token=domain.verification_token if not domain.is_verified else None,
            created_at=domain.created_at,
            verified_at=domain.verified_at,
        )
        for domain in domains
    ]


@router.post("/{org_id}/domains")
async def add_org_domain(
    org_id: str,
    domain_data: OrganizationDomainCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDomain:
    """Add a domain to an organization. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can add domains")

    # Check if domain already exists
    existing = await db.execute(
        select(OrganizationDomainModel).where(OrganizationDomainModel.domain == domain_data.domain)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Domain already registered")

    # Generate verification token
    import secrets
    verification_token = secrets.token_urlsafe(32)

    now = datetime.now(UTC).replace(tzinfo=None)
    domain = OrganizationDomainModel(
        id=str(uuid4()),
        organization_id=org_id,
        domain=domain_data.domain,
        is_verified=False,
        verification_token=verification_token,
        created_at=now,
    )
    db.add(domain)
    await db.flush()

    return OrganizationDomain(
        id=domain.id,
        organization_id=domain.organization_id,
        domain=domain.domain,
        is_verified=domain.is_verified,
        verification_token=domain.verification_token,
        created_at=domain.created_at,
        verified_at=domain.verified_at,
    )


@router.post("/{org_id}/domains/{domain_id}/verify")
async def verify_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDomain:
    """Verify a domain (checks DNS TXT record). Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can verify domains")

    result = await db.execute(
        select(OrganizationDomainModel).where(
            (OrganizationDomainModel.id == domain_id)
            & (OrganizationDomainModel.organization_id == org_id)
        )
    )
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    if domain.is_verified:
        raise HTTPException(status_code=400, detail="Domain already verified")

    # TODO: Implement actual DNS verification
    # For now, just mark as verified
    domain.is_verified = True
    domain.verified_at = datetime.now(UTC).replace(tzinfo=None)
    await db.flush()

    return OrganizationDomain(
        id=domain.id,
        organization_id=domain.organization_id,
        domain=domain.domain,
        is_verified=domain.is_verified,
        verification_token=None,  # Don't return token once verified
        created_at=domain.created_at,
        verified_at=domain.verified_at,
    )


@router.delete("/{org_id}/domains/{domain_id}")
async def delete_org_domain(
    org_id: str,
    domain_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a domain from an organization. Requires admin or owner role."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can delete domains")

    result = await db.execute(
        select(OrganizationDomainModel).where(
            (OrganizationDomainModel.id == domain_id)
            & (OrganizationDomainModel.organization_id == org_id)
        )
    )
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.flush()

    return {"message": "Domain removed successfully"}


# ============ Organization Billing (Placeholder) ============

class BillingInfo(BaseModel):
    """Organization billing information."""
    plan: str
    usage: dict | None = None


class BillingUpgrade(BaseModel):
    """Upgrade organization plan."""
    plan: str


@router.get("/{org_id}/billing")
async def get_org_billing(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> BillingInfo:
    """Get organization billing information. NOT IMPLEMENTED."""
    await require_org_access(current_user.id, org_id, db)

    # Return 501 Not Implemented
    raise HTTPException(
        status_code=501,
        detail="Billing functionality is not yet implemented. This feature will be available in a future release."
    )


@router.post("/{org_id}/billing/upgrade")
async def upgrade_org_plan(
    org_id: str,
    upgrade: BillingUpgrade,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upgrade organization plan. NOT IMPLEMENTED."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can manage billing")

    raise HTTPException(
        status_code=501,
        detail="Billing upgrades are not yet implemented. Please contact support@naas.ai to discuss enterprise plans."
    )


@router.post("/{org_id}/billing/payment-method")
async def add_payment_method(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add payment method to organization. NOT IMPLEMENTED."""
    role = await require_org_access(current_user.id, org_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can manage billing")

    raise HTTPException(
        status_code=501,
        detail="Payment method management is not yet implemented. Billing features are coming soon."
    )
