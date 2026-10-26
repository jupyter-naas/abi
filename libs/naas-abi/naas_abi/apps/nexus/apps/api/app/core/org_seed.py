"""
Apply config-driven provisioning on startup.

This provisions:
- bootstrap users (create by email if missing; ``is_superadmin`` only promotes)
- organizations (upsert by slug) and their owner membership
- workspaces (upsert by slug) and their owner membership
- workspace app enable rows from ``WorkspaceSeedConfig.apps``

People are managed in the platform (Org > Users, workspace Members, Admin >
Users). Config ``members`` lists are deprecated and ignored: existing rows are
kept, and ``core.users_import`` replays a snapshot without overwriting roles.

Nexus has no login of its own: a configured user is a person of the built-in
identity provider. Their Nexus account is made here without a password, and they
are made to exist at the provider (``provision_seed_users``); their first sign-in
there, with the address verified by the code mailed to it, links the account
(``services/oidc``), which keeps the roles configured here.
"""

import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.config import (
    OrganizationSeedConfig,
    WorkspaceSeedConfig,
    settings,
)
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import (
    AppConfigModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope, workspace_scope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

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
    "background_image_url",
    "sidebar_color",
    "font_family",
)


def _apply_workspace_seed_fields(workspace: Any, workspace_cfg: WorkspaceSeedConfig) -> None:
    """Fill the seed's name and branding into an existing workspace, bootstrap only.

    A field is written only when the workspace has no value for it yet, so a
    name, logo, colour or wallpaper changed in the app survives restarts (logos
    and wallpapers chosen in the app live in the workspace drive and only their
    URL is kept here). To force a config value, clear the field in the app.
    """
    for field in _WORKSPACE_FIELDS:
        value = getattr(workspace_cfg, field)
        if value and not getattr(workspace, field, None):
            setattr(workspace, field, value)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def _get_user_by_email(session: AsyncSession, email: str) -> UserModel | None:
    result = await session.execute(
        select(UserModel).where(UserModel.email == _normalize_email(email))
    )
    return result.scalar_one_or_none()


async def _get_user_by_id(session: AsyncSession, user_id: str) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


# What this seeding run declares, applied to IAM once the rows are committed:
# role attachments are the only record of memberships.
_declared_roles: ContextVar[list[tuple[str, str, str]] | None] = ContextVar(
    "nexus_seed_roles", default=None
)
_declared_scopes: ContextVar[list[tuple[str | None, str | None]] | None] = ContextVar(
    "nexus_seed_scopes", default=None
)


def _declare_role(user_id: str, role: str, scope: str) -> None:
    declared = _declared_roles.get()
    if declared is not None:
        declared.append((user_id, role, scope))


def _declare_scope(org_id: str | None, workspace_id: str | None) -> None:
    declared = _declared_scopes.get()
    if declared is not None:
        declared.append((org_id, workspace_id))


async def _ensure_org_member(
    session: AsyncSession,
    organization_id: str,
    user_id: str,
    role: str,
) -> None:
    _declare_scope(organization_id, None)
    _declare_role(user_id, role, org_scope(organization_id))


async def _ensure_workspace_member(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    role: str,
    organization_id: str | None = None,
) -> None:
    _declare_scope(organization_id, workspace_id)
    _declare_role(user_id, role, workspace_scope(organization_id, workspace_id))


async def _upsert_users(session: AsyncSession) -> dict[str, UserModel]:
    users_by_email: dict[str, UserModel] = {}
    now = datetime.now(UTC).replace(tzinfo=None)

    for user_cfg in settings.users:
        normalized_email = _normalize_email(str(user_cfg.email))
        user = await _get_user_by_email(session, normalized_email)
        if user is None:
            user = UserModel(
                id=f"user-{uuid4().hex[:12]}",
                email=normalized_email,
                name=user_cfg.name,
                avatar=user_cfg.avatar,
                organization=user_cfg.organization,
                job_title=user_cfg.job_title,
                bio=user_cfg.bio,
                is_superadmin=user_cfg.is_superadmin,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            logger.info("Created user email=%s from config", normalized_email)
        else:
            logger.info(
                "User email=%s already exists; skipping config-driven updates",
                normalized_email,
            )
            # Config only promotes: superadmins are managed in Platform
            # Settings > Users, and listing an operator here keeps them from
            # being locked out.
            if user_cfg.is_superadmin and not user.is_superadmin:
                user.is_superadmin = True
                user.updated_at = now
                logger.info("Promoted email=%s to superadmin from config", normalized_email)

        users_by_email[normalized_email] = user

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


def _warn_ignored_members(kind: str, slug: str, count: int) -> None:
    if count:
        logger.warning(
            "Ignoring %d config members of %s slug=%s: members are managed in the "
            "platform now (existing memberships are kept). Remove the list from the "
            "config; replay a snapshot with core.users_import if needed.",
            count,
            kind,
            slug,
        )


async def _upsert_workspace(
    session: AsyncSession,
    workspace_cfg: WorkspaceSeedConfig,
    organization: OrganizationModel,
    users_by_email: dict[str, UserModel],
) -> None:
    owner = await _resolve_user(
        session,
        users_by_email,
        str(workspace_cfg.owner_email) if workspace_cfg.owner_email else None,
    )
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
            workspace_group=workspace_cfg.group,
            **{field: getattr(workspace_cfg, field) for field in _WORKSPACE_FIELDS},
        )
        # The name is managed in the app (config.workspaces.yaml snapshot).
        workspace.name = workspace_cfg.name or workspace_cfg.slug
        session.add(workspace)
        logger.info(
            "Created workspace slug=%s under org=%s",
            workspace_cfg.slug,
            organization.slug,
        )
    else:
        # Bootstrap only, like the branding below: an owner or organization
        # changed in the app is kept, the config only fills a missing one.
        if not workspace.owner_id:
            workspace.owner_id = owner.id
        if not workspace.organization_id:
            workspace.organization_id = organization.id
        _apply_workspace_seed_fields(workspace, workspace_cfg)
        if workspace_cfg.group and not getattr(workspace, "workspace_group", None):
            workspace.workspace_group = workspace_cfg.group
        workspace.updated_at = now
        logger.info(
            "Updated workspace slug=%s under org=%s",
            workspace_cfg.slug,
            organization.slug,
        )

    await _ensure_workspace_member(
        session, workspace.id, workspace.owner_id, "owner", workspace.organization_id
    )
    _warn_ignored_members("workspace", workspace_cfg.slug, len(workspace_cfg.members))

    await _seed_workspace_apps(session, workspace.id, workspace_cfg.apps)


async def _seed_workspace_apps(
    session: AsyncSession,
    workspace_id: str,
    app_ids: list[str] | None,
) -> None:
    """Insert missing enabled rows for seeded catalog apps. Existing rows win."""
    if not app_ids:
        return
    now = datetime.now(UTC).replace(tzinfo=None)
    for raw in app_ids:
        app_id = str(raw or "").strip()
        if not app_id:
            continue
        result = await session.execute(
            select(AppConfigModel).where(
                (AppConfigModel.workspace_id == workspace_id) & (AppConfigModel.app_id == app_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            continue
        session.add(
            AppConfigModel(
                id=f"app-{uuid4().hex[:12]}",
                workspace_id=workspace_id,
                app_id=app_id,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        logger.info(
            "Seeded app_id=%s enabled on workspace_id=%s",
            app_id,
            workspace_id,
        )


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

    _warn_ignored_members("organization", org_cfg.slug, len(org_cfg.members))

    for workspace_cfg in org_cfg.workspaces:
        await _upsert_workspace(session, workspace_cfg, organization, users_by_email)


def sync_platform_admins(iam: Any, users_by_email: dict[str, UserModel]) -> None:
    """``users[].is_superadmin`` as IAM's ``builtin.platform_admin`` attachment.

    The configuration only promotes, as ``is_superadmin`` itself does: a platform
    administrator is demoted in Admin > Users (IAM's attachment), never by leaving
    the flag out of the config. A user of the old login
    that has not linked yet: IAM knows it as the user of issuer
    ``urn:abi:nexus`` whose subject is the Nexus user id, the id Nexus names on
    every kernel call it makes for them.
    """
    from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
    from naas_abi_core.services.iam.roles import PLATFORM_ADMIN

    for user_cfg in settings.users:
        user = users_by_email.get(_normalize_email(str(user_cfg.email)))
        if user is None:
            continue
        # Found as it is: ensuring it again would write the profile of the old
        # login over the one a linked identity provider vouches for.
        principal = iam.resolve_user(user.id) or iam.ensure_user(
            LEGACY_NEXUS_ISSUER,
            user.id,
            provider="nexus",
            email=user.email,
            display_name=user.name,
        )
        if user_cfg.is_superadmin:
            iam.attach_policy(PLATFORM_ADMIN, principal.id)


async def _apply_declared_roles(
    scopes: list[tuple[str | None, str | None]],
    roles: list[tuple[str, str, str]],
) -> None:
    """The configuration's scopes and roles, as the system: the configuration is
    declarative, so the role it names is the role held."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    for org_id, workspace_id in dict.fromkeys(scopes):
        if workspace_id is None and org_id is not None:
            await MEMBERSHIPS.register_org(org_id)
        elif workspace_id is not None:
            await MEMBERSHIPS.register_workspace(org_id, workspace_id)
    granted, kept = await MEMBERSHIPS.seed(list(dict.fromkeys(roles)), replace=True)
    logger.info("Configured memberships in IAM: %d changed, %d already held", granted, kept)


def _engine_iam() -> Any | None:
    """The engine's IAM, when Nexus runs in a loaded engine."""
    try:
        from naas_abi import ABIModule

        services = ABIModule.get_instance().engine.services
        return services.iam if services.iam_available() else None
    except Exception:  # no engine: Nexus alone, or tests
        return None


async def apply_configuration_seeds() -> None:
    """Apply config-driven user/org/workspace provisioning."""
    if not settings.users and not settings.organizations:
        return

    roles_token = _declared_roles.set([])
    scopes_token = _declared_scopes.set([])
    try:
        return await _apply_configuration_seeds()
    finally:
        _declared_roles.reset(roles_token)
        _declared_scopes.reset(scopes_token)


async def _apply_configuration_seeds() -> None:
    async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            users_by_email = await _upsert_users(session=session)
            for org_cfg in settings.organizations:
                try:
                    await _upsert_organization(session, org_cfg, users_by_email)
                except Exception:
                    logger.exception("Failed to apply config for org slug=%s", org_cfg.slug)

    iam = _engine_iam()
    if iam is not None:
        try:
            # Blocking IAM calls; to_thread keeps the caller's context ("api").
            await asyncio.to_thread(sync_platform_admins, iam, users_by_email)
        except Exception:
            logger.exception("Failed to apply users[].is_superadmin to IAM")
        try:
            await _apply_declared_roles(_declared_scopes.get() or [], _declared_roles.get() or [])
        except Exception:
            logger.exception("Failed to apply the configured memberships to IAM")

    if settings.users:
        _provision_in_background([(str(u.email).strip().lower(), u.name) for u in settings.users])

    logger.info(
        "Configuration seeds applied (users=%d, organizations=%d)",
        len(settings.users),
        len(settings.organizations),
    )


# -- the configured users at the built-in identity provider -----------------------------------

# The provider runs as a module: the API may boot before it answers.
_PROVISION_RETRY_SECONDS = 5.0
_PROVISION_ATTEMPTS = 60
_provisioning_tasks: set[asyncio.Task[None]] = set()


def _builtin_provider(identity: Any) -> str | None:
    """The built-in identity provider (``provisioning: builtin``), when there is one."""
    for provider in identity.list_providers():
        if getattr(provider, "provisioning", None) == "builtin":
            return str(provider.name)
    return None


def provision_seed_users(identity: Any, users: list[tuple[str, str]]) -> list[str]:
    """Make each ``(email, name)`` exist at the built-in provider, as ``api``.

    Returns the emails made or found. ``ProviderUnavailableError`` when the
    provider does not answer yet (the caller tries again); no built-in provider
    configured: nobody is provisioned, and nothing is an error (the provider's
    people are made in the provider, or nobody signs in)."""
    from naas_abi_core.engine.call_context import as_service_account

    with as_service_account("api"):
        provider = _builtin_provider(identity)
        if provider is None:
            return []
        done: list[str] = []
        for email, name in users:
            made = identity.provision_user(provider, email, name=name)
            logger.info(
                "Configured user %s %s at the %s identity provider: they sign in with the "
                "code it emails to that address",
                email,
                "created" if getattr(made, "created", False) else "found",
                provider,
            )
            done.append(email)
        return done


async def _provision_when_ready(identity: Any, users: list[tuple[str, str]]) -> None:
    from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError

    for attempt in range(_PROVISION_ATTEMPTS):
        try:
            await asyncio.to_thread(provision_seed_users, identity, users)
            return
        except ProviderUnavailableError as exc:
            if attempt == 0:
                logger.info(f"The built-in identity provider is not ready yet: {exc}")
            await asyncio.sleep(_PROVISION_RETRY_SECONDS)
        except Exception:  # noqa: BLE001 - never stops the API; `abi user migrate` redoes it
            logger.exception("Could not provision the configured users at the identity provider")
            return
    logger.warning(
        "The built-in identity provider never answered: run `abi user migrate --apply` "
        "once it is up to make the configured users exist there"
    )


def _provision_in_background(users: list[tuple[str, str]]) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
        default_identity,
    )

    identity = default_identity()
    if identity is None:
        return
    task = asyncio.create_task(_provision_when_ready(identity, users))
    _provisioning_tasks.add(task)
    task.add_done_callback(_provisioning_tasks.discard)
