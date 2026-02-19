"""
Apply config-driven provisioning on startup.

This provisions:
- users (upsert by email)
- organizations (upsert by slug)
- organization members
- workspaces (upsert by slug)
- workspace members

It can also mirror configured user credentials into the Secret service.
"""

import logging
import re
import secrets
from datetime import datetime
from typing import Any
from uuid import uuid4

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    UserSeedConfig,
    WorkspaceSeedConfig,
    settings,
)
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)

logger = logging.getLogger(__name__)

_ORG_BRANDING_FIELDS = (
    "name",
    "logo_url",
    "logo_rectangle_url",
    "logo_emoji",
    "primary_color",
    "accent_color",
    "background_color",
    "font_family",
    "font_url",
    "login_card_max_width",
    "login_card_padding",
    "login_card_color",
    "login_text_color",
    "login_input_color",
    "login_border_radius",
    "login_bg_image_url",
    "show_terms_footer",
    "show_powered_by",
    "login_footer_text",
    "secondary_logo_url",
    "show_logo_separator",
    "default_theme",
)

_WORKSPACE_FIELDS = (
    "name",
    "logo_url",
    "logo_emoji",
    "primary_color",
    "accent_color",
    "background_color",
    "sidebar_color",
    "font_family",
)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _generate_password() -> str:
    # URL-safe random password (~32 chars) suitable for bootstrap credentials.
    return secrets.token_urlsafe(24)


def _secret_prefix_for_email(email: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", _normalize_email(email).upper())


def _store_user_credentials_in_secret_service(
    secret_service: Any,
    email: str,
    password: str,
) -> None:
    email_prefix = _secret_prefix_for_email(email)
    secret_service.set(f"NEXUS_USER_{email_prefix}_EMAIL", email)
    secret_service.set(f"NEXUS_USER_{email_prefix}_PASSWORD", password)


async def _get_user_by_email(session: AsyncSession, email: str) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where(UserModel.email == _normalize_email(email))
    )
    return result.scalar_one_or_none()


async def _get_user_by_id(session: AsyncSession, user_id: str) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    return result.scalar_one_or_none()


async def _ensure_org_member(
    session: AsyncSession,
    organization_id: str,
    user_id: str,
    role: str,
) -> None:
    result = await session.execute(
        select(OrganizationMemberModel).where(
            (OrganizationMemberModel.organization_id == organization_id)
            & (OrganizationMemberModel.user_id == user_id)
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        session.add(
            OrganizationMemberModel(
                id=str(uuid4()),
                organization_id=organization_id,
                user_id=user_id,
                role=role,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        return

    membership.role = role


async def _ensure_workspace_member(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    role: str,
) -> None:
    result = await session.execute(
        select(WorkspaceMemberModel).where(
            (WorkspaceMemberModel.workspace_id == workspace_id)
            & (WorkspaceMemberModel.user_id == user_id)
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        session.add(
            WorkspaceMemberModel(
                id=str(uuid4()),
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        return

    membership.role = role


async def _upsert_users(
    session: AsyncSession,
    secret_service: Any | None,
) -> dict[str, UserModel]:
    users_by_email: dict[str, UserModel] = {}
    now = datetime.now(UTC).replace(tzinfo=None)

    for user_cfg in settings.users:
        normalized_email = _normalize_email(str(user_cfg.email))
        user = await _get_user_by_email(session, normalized_email)
        generated_password: str | None = None
        if user is None:
            generated_password = _generate_password()
            user = UserModel(
                id=f"user-{uuid4().hex[:12]}",
                email=normalized_email,
                name=user_cfg.name,
                hashed_password=_hash_password(generated_password),
                avatar=user_cfg.avatar,
                company=user_cfg.company,
                role=user_cfg.role,
                bio=user_cfg.bio,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            logger.info("Created user email=%s from config", normalized_email)
        else:
            user.name = user_cfg.name
            user.avatar = user_cfg.avatar
            user.company = user_cfg.company
            user.role = user_cfg.role
            user.bio = user_cfg.bio
            user.updated_at = now
            logger.info("Updated user email=%s from config", normalized_email)

        users_by_email[normalized_email] = user

        if (
            secret_service is not None
            and user_cfg.store_credentials_in_secrets
            and generated_password is not None
        ):
            _store_user_credentials_in_secret_service(
                secret_service=secret_service,
                email=normalized_email,
                password=generated_password,
            )
        elif generated_password is not None and user_cfg.store_credentials_in_secrets:
            logger.warning(
                "User email=%s created with generated password, but no secret service is available to store credentials.",
                normalized_email,
            )

    return users_by_email


async def _resolve_user(
    session: AsyncSession,
    users_by_email: dict[str, UserModel],
    email: str | None,
) -> UserModel | None:
    if not email:
        return None
    normalized_email = _normalize_email(email)
    known = users_by_email.get(normalized_email)
    if known is not None:
        return known
    user = await _get_user_by_email(session, normalized_email)
    if user is not None:
        users_by_email[normalized_email] = user
    return user


async def _upsert_workspace(
    session: AsyncSession,
    workspace_cfg: WorkspaceSeedConfig,
    organization: OrganizationModel,
    users_by_email: dict[str, UserModel],
) -> None:
    owner = await _resolve_user(session, users_by_email, str(workspace_cfg.owner_email) if workspace_cfg.owner_email else None)
    if owner is None:
        owner = await _get_user_by_id(session, organization.owner_id)

    if owner is None:
        logger.warning(
            "Skipping workspace slug=%s for org=%s because owner cannot be resolved",
            workspace_cfg.slug,
            organization.slug,
        )
        return

    result = await session.execute(
        select(WorkspaceModel).where(WorkspaceModel.slug == workspace_cfg.slug)
    )
    workspace = result.scalar_one_or_none()
    now = datetime.now(UTC).replace(tzinfo=None)

    if workspace is None:
        workspace = WorkspaceModel(
            id=f"ws-{uuid4().hex[:12]}",
            slug=workspace_cfg.slug,
            owner_id=owner.id,
            organization_id=organization.id,
            created_at=now,
            updated_at=now,
            **{field: getattr(workspace_cfg, field) for field in _WORKSPACE_FIELDS},
        )
        session.add(workspace)
        logger.info(
            "Created workspace slug=%s under org=%s",
            workspace_cfg.slug,
            organization.slug,
        )
    else:
        workspace.owner_id = owner.id
        workspace.organization_id = organization.id
        for field in _WORKSPACE_FIELDS:
            setattr(workspace, field, getattr(workspace_cfg, field))
        workspace.updated_at = now
        logger.info(
            "Updated workspace slug=%s under org=%s",
            workspace_cfg.slug,
            organization.slug,
        )

    await _ensure_workspace_member(session, workspace.id, owner.id, "owner")
    for membership in workspace_cfg.members:
        member = await _resolve_user(session, users_by_email, str(membership.email))
        if member is None:
            logger.warning(
                "Skipping workspace member email=%s in workspace slug=%s because user does not exist",
                membership.email,
                workspace_cfg.slug,
            )
            continue
        member_role = "owner" if member.id == owner.id else membership.role
        await _ensure_workspace_member(session, workspace.id, member.id, member_role)


async def _upsert_organization(
    session: AsyncSession,
    org_cfg: OrganizationSeedConfig,
    users_by_email: dict[str, UserModel],
) -> None:
    owner = await _resolve_user(
        session,
        users_by_email,
        str(org_cfg.owner_email) if org_cfg.owner_email else None,
    )

    result = await session.execute(
        select(OrganizationModel).where(OrganizationModel.slug == org_cfg.slug)
    )
    organization = result.scalar_one_or_none()
    now = datetime.now(UTC).replace(tzinfo=None)

    if organization is None:
        if owner is None:
            logger.warning(
                "Skipping org slug=%s creation because owner_email is missing or unknown",
                org_cfg.slug,
            )
            return
        organization = OrganizationModel(
            id=f"org-{uuid4().hex[:12]}",
            slug=org_cfg.slug,
            owner_id=owner.id,
            created_at=now,
            updated_at=now,
            **{field: getattr(org_cfg, field) for field in _ORG_BRANDING_FIELDS},
        )
        session.add(organization)
        logger.info("Created organization slug=%s", org_cfg.slug)
    else:
        if owner is not None:
            organization.owner_id = owner.id
        for field in _ORG_BRANDING_FIELDS:
            setattr(organization, field, getattr(org_cfg, field))
        organization.updated_at = now
        logger.info("Updated organization slug=%s", org_cfg.slug)

    if owner is not None:
        await _ensure_org_member(session, organization.id, owner.id, "owner")

    for membership in org_cfg.members:
        member = await _resolve_user(session, users_by_email, str(membership.email))
        if member is None:
            logger.warning(
                "Skipping org member email=%s in org slug=%s because user does not exist",
                membership.email,
                org_cfg.slug,
            )
            continue
        member_role = "owner" if owner is not None and member.id == owner.id else membership.role
        await _ensure_org_member(session, organization.id, member.id, member_role)

    for workspace_cfg in org_cfg.workspaces:
        await _upsert_workspace(session, workspace_cfg, organization, users_by_email)


async def apply_configuration_seeds(secret_service: Any | None = None) -> None:
    """Apply config-driven user/org/workspace provisioning."""
    if not settings.users and not settings.organizations:
        return

    async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            users_by_email = await _upsert_users(
                session=session,
                secret_service=secret_service,
            )
            for org_cfg in settings.organizations:
                try:
                    await _upsert_organization(session, org_cfg, users_by_email)
                except Exception:
                    logger.exception("Failed to apply config for org slug=%s", org_cfg.slug)

    logger.info(
        "Configuration seeds applied (users=%d, organizations=%d)",
        len(settings.users),
        len(settings.organizations),
    )
