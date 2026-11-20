"""
Apply config-driven provisioning on startup.

This provisions:
- bootstrap users (create by email if missing; ``is_superadmin`` only promotes)
- organizations (upsert by slug) and their owner membership
- workspaces (upsert by slug) and their owner membership
- workspace app enable rows from ``WorkspaceSeedConfig.apps``

Seeding updates only the rows it made (``seeded``). A configured slug that a
person's organization or workspace holds is refused and logged, never taken
over, and configured slugs are reserved at create and rename
(``core.configured_slugs``). A row older than the flag is recognised once, where
seeding left it: an organization the configured owner owns, a workspace inside
its configured organization.

People are managed in the platform (Org > Users, workspace Members, Admin >
Users). Config ``members`` lists are deprecated and ignored: existing rows are
kept, and ``core.users_import`` replays a snapshot without overwriting roles.

Nexus has no login of its own: a configured user is a person of the people
directory (``services/people``) who signs in at an identity provider: the one
``users[].provider`` names, else the default one, else the built-in one, else the
only one. Their row is made here ``invited``, with no password and no identity
yet, naming that provider; until they sign in, they are made to exist there in the
background, as the people service makes an invited person
(``provision_configured_users``), when it can (``builtin``, ``zitadel``,
``keycloak``; ``none`` makes nobody). Their first
sign-in through that provider, with the address verified there, binds the row
(``services/oidc``), which keeps the roles configured here and makes it
``active``. A row the configuration names that no provider signs in yet (made
before this, or by the old login) is given that provider too. With no identity
service (Nexus alone) the row is made as before: no provider named, linked at the
first sign-in through the built-in provider.
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
from naas_abi.apps.nexus.apps.api.app.services.iam import legacy_names
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from sqlalchemy import inspect, select
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
# role attachments are the only record of memberships. A role is declared at an
# organization or a workspace (``(user, role, org, workspace)``, the workspace
# ``None`` for the organization's own), named when it is applied, in the grammar
# IAM's names are in then (``_apply_declared_roles``).
_declared_roles: ContextVar[list[tuple[str, str, str | None, str | None]] | None] = ContextVar(
    "nexus_seed_roles", default=None
)
_declared_scopes: ContextVar[list[tuple[str | None, str | None]] | None] = ContextVar(
    "nexus_seed_scopes", default=None
)


def _declare_role(user_id: str, role: str, org_id: str | None, workspace_id: str | None) -> None:
    declared = _declared_roles.get()
    if declared is not None:
        declared.append((user_id, role, org_id, workspace_id))


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
    _declare_role(user_id, role, organization_id, None)


async def _ensure_workspace_member(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    role: str,
    organization_id: str | None = None,
) -> None:
    _declare_scope(organization_id, workspace_id)
    _declare_role(user_id, role, organization_id, workspace_id)


# Domains that receive no mail (RFC 2606, RFC 6761, mDNS).
_PLACEHOLDER_DOMAINS = frozenset({"example.com", "example.net", "example.org", "localhost"})
_PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".test", ".localhost", ".local")


def is_placeholder_address(email: str) -> bool:
    """Whether ``email``'s domain receives no mail: the identity provider's
    sign-in codes for it reach nobody."""
    domain = email.rsplit("@", 1)[-1].strip().lower().rstrip(".")
    # The reserved domains and every name under them (mail.example.com).
    return domain.endswith(_PLACEHOLDER_SUFFIXES) or any(
        domain == reserved or domain.endswith("." + reserved) for reserved in _PLACEHOLDER_DOMAINS
    )


def warn_on_placeholder_superadmins(users: list[Any]) -> list[str]:
    """Log a warning for each configured superadmin whose address receives no
    mail, and return them."""
    found = [
        str(user.email)
        for user in users
        if user.is_superadmin and is_placeholder_address(str(user.email))
    ]
    for email in found:
        logger.warning(
            "users: makes %s a platform administrator, an address that receives "
            "no mail: nobody gets its sign-in codes. Put the administrator's own "
            "address in the configuration.",
            email,
        )
    return found


def identity_providers() -> tuple[dict[str, str], str | None]:
    """``({name: provisioning}, default)`` of the engine's identity providers;
    ``({}, None)`` without an identity service (Nexus alone, tests)."""
    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
        default_identity,
    )
    from naas_abi_core.engine.call_context import as_service_account

    identity = default_identity()
    if identity is None:
        return {}, None
    try:
        with as_service_account("api"):
            found = {str(p.name): str(p.provisioning) for p in identity.list_providers()}
            default = identity.default_provider
    except Exception:  # noqa: BLE001 - the rows are made as before, no provider named
        logger.exception("The identity providers could not be listed for the configured users")
        return {}, None
    return found, (str(default) if default else None)


def seed_provider(
    requested: str | None, providers: dict[str, str], default: str | None
) -> str | None:
    """The provider a configured person signs in through: the one named, else the
    default, else the built-in one, else the only one; None when none is known."""
    if requested:
        if requested in providers:
            return requested
        logger.warning(
            "users: names the identity provider %r, which is not configured: the default "
            "one is used",
            requested,
        )
    if default and default in providers:
        return default
    builtin = next((name for name, kind in providers.items() if kind == "builtin"), None)
    if builtin is not None:
        return builtin
    return next(iter(providers)) if len(providers) == 1 else None


def configured_row(
    *,
    email: str,
    name: str,
    provider: str | None,
    now: datetime,
    **profile: Any,
) -> UserModel:
    """A person the configuration (or a people snapshot) names, as the people service
    leaves someone invited whom no provider made yet: ``invited``, unbound, naming
    the provider whose verified sign-in binds them. No provider known: the row of
    before (``active``, linked through the built-in provider)."""
    return UserModel(
        id=f"user-{uuid4().hex[:12]}",
        email=email,
        name=name,
        status="invited" if provider else "active",
        idp_provider=provider,
        created_at=now,
        updated_at=now,
        **profile,
    )


def name_the_provider(user: Any, provider: str | None, now: datetime) -> bool:
    """Give a configured row that no provider signs in yet, and that names none, the
    provider the configuration says: its verified sign-in there binds it (before,
    only the built-in provider's did). True when it changed."""
    if (
        provider is None
        or getattr(user, "idp_provider", None)
        or getattr(user, "principal_id", None)
        or getattr(user, "idp_issuer", None)
    ):
        return False
    user.idp_provider = provider
    user.updated_at = now
    return True


async def _upsert_users(session: AsyncSession) -> dict[str, UserModel]:
    users_by_email: dict[str, UserModel] = {}
    now = datetime.now(UTC).replace(tzinfo=None)
    warn_on_placeholder_superadmins(list(settings.users))
    providers, default = await asyncio.to_thread(identity_providers)

    for user_cfg in settings.users:
        normalized_email = _normalize_email(str(user_cfg.email))
        provider = seed_provider(user_cfg.provider, providers, default)
        user = await _get_user_by_email(session, normalized_email)
        if user is None:
            user = configured_row(
                email=normalized_email,
                name=user_cfg.name,
                provider=provider,
                now=now,
                avatar=user_cfg.avatar,
                organization=user_cfg.organization,
                job_title=user_cfg.job_title,
                bio=user_cfg.bio,
                is_superadmin=user_cfg.is_superadmin,
            )
            session.add(user)
            logger.info(
                "Created user email=%s from config (signs in through %s)",
                normalized_email,
                provider or "the built-in provider",
            )
        else:
            if name_the_provider(user, provider, now):
                logger.info(
                    "User email=%s signs in through %s from config", normalized_email, provider
                )
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

    if workspace is not None and not _workspace_is_managed(workspace, organization):
        logger.error(
            "Configured workspace slug=%s is held by workspace %s, which the configuration "
            "did not make (organization %s): left as it is, and not configured. Rename the "
            "workspace in the configuration, or remove that workspace.",
            workspace_cfg.slug,
            workspace.id,
            workspace.organization_id or "none",
        )
        return

    if workspace is None:
        workspace = WorkspaceModel(
            id=f"ws-{uuid4().hex[:12]}",
            slug=workspace_cfg.slug,
            owner_id=owner.id,
            organization_id=organization.id,
            seeded=True,
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
        # Bootstrap only, like the branding below: an owner changed in the app is
        # kept, the config only fills a missing one. The organization is never set
        # here: the workspace stays where it is.
        workspace.seeded = True
        if not workspace.owner_id:
            workspace.owner_id = owner.id
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


def _workspace_is_managed(workspace: WorkspaceModel, organization: OrganizationModel) -> bool:
    """Whether seeding may update ``workspace`` as the configured one of
    ``organization``: one it made (wherever an administrator moved it since), or one
    older than the flag that is in that organization, where seeding put it."""
    flag = getattr(workspace, "seeded", None)
    if flag is True:
        return True
    return flag is None and workspace.organization_id == organization.id


def _organization_is_managed(organization: OrganizationModel, owner: UserModel | None) -> bool:
    """Whether seeding may update ``organization``: one it made, or one older than
    the flag that the configured owner owns (seeding wrote that owner at every
    start). A person's organization of the same slug is neither."""
    flag = getattr(organization, "seeded", None)
    if flag is True:
        return True
    return flag is None and owner is not None and organization.owner_id == owner.id


async def _seed_workspace_apps(
    session: AsyncSession,
    workspace_id: str,
    app_ids: list[str] | None,
) -> None:
    """Insert the missing rows of seeded catalog apps (installed in the
    workspace; who opens one is a policy's). Existing rows win."""
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
                created_at=now,
                updated_at=now,
            )
        )
        logger.info(
            "Seeded app_id=%s on workspace_id=%s",
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

    if organization is not None and not _organization_is_managed(organization, owner):
        logger.error(
            "Configured organization slug=%s is held by organization %s, which the "
            "configuration did not make: left as it is, and none of its configured "
            "workspaces is seeded. Rename the organization in the configuration, or "
            "remove that organization.",
            org_cfg.slug,
            organization.id,
        )
        return

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
            seeded=True,
            created_at=now,
            updated_at=now,
            **{field: getattr(org_cfg, field) for field in _ORG_BRANDING_FIELDS},
        )
        session.add(organization)
        logger.info("Created organization slug=%s", org_cfg.slug)
    else:
        organization.seeded = True
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
    roles: list[tuple[str, str, str | None, str | None]],
) -> None:
    """The configuration's scopes and roles, as the system: the configuration is
    declarative, so the role it names is the role held. One scope that fails (IAM
    refuses to register it, or a role there) is logged and skipped: the others
    are still applied.

    Named in the grammar IAM's names are in: while the move of the names
    (``container_names_v1``) is not recorded (a start whose moves stopped), the
    one before container paths (``abi:<org>:<ws>``, an owner's or admin's
    organization role org-wide too, ``abi:<org>:*``), which the move rewrites;
    a role of the new grammar next to its old twin would stop that move. Until it
    is recorded, under the moves' lock (read again under it), so another API
    process does not rewrite the names between the reading and the writing; once
    it is, without: the record never goes. An install with no ``iam_migrations``
    table has nothing to move (container paths); when the record cannot be read,
    that is logged and the roles are named as container paths too (IAM merges
    twins at the move)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import container_names

    async def names_rewritten() -> bool:
        try:
            async with AsyncSession(async_engine) as db:
                connection = await db.connection()
                if not await connection.run_sync(
                    lambda sync: inspect(sync).has_table("iam_migrations")
                ):
                    return True
                return await container_names.recorded(db, container_names.MIGRATION_NAME)
        except Exception:
            logger.exception(
                "Whether IAM's names are container paths could not be read: the configured "
                "roles are named as container paths"
            )
            return True

    if await names_rewritten():
        await _attach_declared(scopes, roles, rewritten=True)
        return
    async with container_names.moves_lock(async_engine):
        await _attach_declared(scopes, roles, rewritten=await names_rewritten())


async def _attach_declared(
    scopes: list[tuple[str | None, str | None]],
    roles: list[tuple[str, str, str | None, str | None]],
    *,
    rewritten: bool,
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam import container_names, runtime
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
    from starlette.concurrency import run_in_threadpool

    failed: set[str] = set()
    for org_id, workspace_id in dict.fromkeys(scopes):
        try:
            if workspace_id is None and org_id is not None:
                await MEMBERSHIPS.register_org(org_id)
            elif workspace_id is not None:
                await MEMBERSHIPS.register_workspace(org_id, workspace_id)
        except Exception:
            logger.exception(
                "Configured scope org=%s workspace=%s not registered in IAM: its roles "
                "are not applied",
                org_id,
                workspace_id,
            )
            failed_scope = _role_scope(org_id, workspace_id, rewritten=rewritten)
            if failed_scope is not None:
                failed.add(failed_scope)
    by_scope: dict[str, list[tuple[str, str, str]]] = {}
    for user_id, role, org_id, workspace_id in dict.fromkeys(roles):
        scope = _role_scope(org_id, workspace_id, rewritten=rewritten)
        if scope is None:
            # One declaration that names no place never keeps the others out.
            logger.warning(
                "Configured role %s of %s names no organization or workspace: skipped",
                role,
                user_id,
            )
            continue
        by_scope.setdefault(scope, []).append((user_id, role, scope))
    granted = kept = 0
    applied: set[str] = set()
    for scope, entries in by_scope.items():
        if scope in failed:
            continue
        try:
            changed, held = await MEMBERSHIPS.seed(list(dict.fromkeys(entries)), replace=True)
        except Exception:
            logger.exception("Configured roles at %s not applied in IAM", scope)
            continue
        applied.add(scope)
        granted += changed
        kept += held
    if not rewritten:
        # What ``seed`` mirrors below an organization, in the old grammar: the
        # organizations' roles applied here hold the org-wide role they carry, and
        # no other (a configured demotion takes the former one away).
        try:
            declared: dict[tuple[str, str], str | None] = {}
            for user_id, role, org_id, workspace_id in dict.fromkeys(roles):
                if workspace_id is not None or org_id is None:
                    continue
                if _role_scope(org_id, None, rewritten=False) in applied:
                    declared[(await MEMBERSHIPS.principal_id(user_id), org_id)] = role
            await run_in_threadpool(container_names.mirror_old_org_wide, runtime.iam(), declared)
        except Exception:
            logger.exception(
                "The configured roles were applied, but their org-wide roles of the "
                "grammar before container paths (abi:<org>:*) were not"
            )
    logger.info("Configured memberships in IAM: %d changed, %d already held", granted, kept)


def _role_scope(org_id: str | None, workspace_id: str | None, *, rewritten: bool) -> str | None:
    """Where a declared role is attached: the workspace's container, else the
    organization's (None without either); their scopes of the old grammar until
    the names are rewritten."""
    if workspace_id is not None:
        if rewritten:
            return workspace_container(org_id, workspace_id)
        return legacy_names.workspace_scope(org_id, workspace_id)
    if org_id is None:
        return None
    return org_container(org_id) if rewritten else legacy_names.org_scope(org_id)


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
        _provision_in_background(
            not_signed_in_yet(
                users_by_email, [_normalize_email(str(u.email)) for u in settings.users]
            )
        )

    logger.info(
        "Configuration seeds applied (users=%d, organizations=%d)",
        len(settings.users),
        len(settings.organizations),
    )


# -- the configured users at their identity provider -----------------------------------------

# The provider runs as a module: the API may boot before it answers.
_PROVISION_RETRY_SECONDS = 5.0
_PROVISION_ATTEMPTS = 60
_provisioning_tasks: set[asyncio.Task[None]] = set()


class _NotYet(Exception):  # noqa: N818 - a signal: the provider does not answer yet
    pass


def not_signed_in_yet(users_by_email: dict[str, Any], emails: list[str]) -> list[str]:
    """The configured people no provider signs in yet (their row holds no identity),
    those the seeds make at their provider. Someone who signed in has an account
    there: one their provider's admins removed since is never made again here."""
    done: list[str] = []
    for email in emails:
        row = users_by_email.get(email)
        if row is None or getattr(row, "principal_id", None) or getattr(row, "idp_issuer", None):
            continue
        if email not in done:
            done.append(email)
    return done


async def provision_configured_users(people: Any, emails: list[str]) -> list[str]:
    """Make each configured person exist at the provider their row names, through
    the people service (``PeopleService.provision``: as Nexus, an account it makes
    recorded as ABI's). Returns the emails done (made, found, or nothing to make);
    ``_NotYet`` when the provider does not answer yet. Another failure is logged and
    that person skipped (the next start tries again)."""
    from naas_abi.apps.nexus.apps.api.app.services.people.port import (
        NoProviderError,
        ProvisioningFailedError,
    )
    from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError

    done: list[str] = []
    for email in emails:
        user = await people.by_email(email)
        if user is None:
            done.append(email)
            continue
        try:
            made = await people.provision(user.id)
        except ProvisioningFailedError as exc:
            if isinstance(exc.__cause__, ProviderUnavailableError):
                raise _NotYet(str(exc)) from exc
            logger.exception("Could not make the configured user %s at %s", email, user.provider)
            done.append(email)
            continue
        except NoProviderError as exc:
            logger.warning(
                "The configured user %s has no identity provider to be made at: %s", email, exc
            )
            done.append(email)
            continue
        if made is not None:
            logger.info(
                "Configured user %s %s at the %s identity provider: their first sign-in "
                "there, address verified, opens their account",
                email,
                "created" if made.created else "found",
                user.provider,
            )
        done.append(email)
    return done


async def _provision_when_ready(people_of: Any, emails: list[str]) -> None:
    """``people_of()``: an async context giving a people service on a session of its
    own. Tried again while the provider does not answer (making someone twice finds
    them)."""
    for attempt in range(_PROVISION_ATTEMPTS):
        try:
            async with people_of() as people:
                await provision_configured_users(people, emails)
            return
        except _NotYet as exc:
            if attempt == 0:
                logger.info(f"The identity provider is not ready yet: {exc}")
            await asyncio.sleep(_PROVISION_RETRY_SECONDS)
        except Exception:  # noqa: BLE001 - never stops the API; the next start does it
            logger.exception("Could not provision the configured users at the identity provider")
            return
    logger.warning(
        "The identity provider never answered: the configured users are made there at the "
        "next start"
    )


def _people_session() -> Any:
    from contextlib import asynccontextmanager

    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime

    @asynccontextmanager
    async def opened() -> Any:
        async with AsyncSessionLocal() as db:
            yield people_runtime.RUNTIME.service(db)

    return opened()


def _provision_in_background(emails: list[str]) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
        default_identity,
    )

    if default_identity() is None:
        return
    task = asyncio.create_task(_provision_when_ready(_people_session, emails))
    _provisioning_tasks.add(task)
    task.add_done_callback(_provisioning_tasks.discard)
