"""Build the invitation service, from the engine's services; tests replace the
runtime with ``configure``."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineDirectoryGateway,
    EngineGrantsGateway,
    EngineMigrationGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.mailer import (
    EngineInvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.postgres import (
    InvitationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.migration import (
    MIGRATION_NAME,
    InvitationMigration,
    MigrationReport,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    PROFILE_FIELDS,
    InvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    default_iam,
    default_identity,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.postgres import (
    PeopleSecondaryAdapterPostgres,
)
from naas_abi_core import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


def now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def sign_in_url(email: str, provider: str) -> str:
    """Where the invitee signs in: the web app's login, with their address."""
    base = settings.frontend_url.rstrip("/")
    return f"{base}/auth/login?{urlencode({'email': email, 'provider': provider})}"


class InvitationRuntime:
    def __init__(
        self,
        identity: Callable[[], Any | None] = default_identity,
        iam: Callable[[], Any | None] = default_iam,
        mailer: InvitationMailer | None = None,
    ) -> None:
        self.directory = EngineDirectoryGateway(identity)
        self.grants = EngineGrantsGateway(iam)
        self.mailer = mailer or EngineInvitationMailer()

    def claimer(self, db: AsyncSession) -> Callable[[Any, Any], Awaitable[None]]:
        """What a sign-in runs for its user: the memberships of the invitations
        their verified email was sent."""
        service = self.service(db)

        async def claim(user: Any, signed_in: Any) -> None:
            token = signed_in.token
            # The provider vouched for the address, and Nexus stored it as
            # given: a placeholder for an unverified one never matches anyone.
            if not token.email or not token.email_verified:
                return
            if token.email.lower() != user.email.lower():
                return
            accepted = await service.claim(
                user_id=user.id, email=user.email, provider=token.provider
            )
            # What the inviting admin set about the person in the organization.
            for invitation in accepted:
                if invitation.organization_id and invitation.profile:
                    await OrganizationSecondaryAdapterPostgres(
                        db
                    ).update_organization_member_profile(
                        invitation.organization_id,
                        user.id,
                        name=None,
                        **{field: invitation.profile.get(field) for field in PROFILE_FIELDS},
                    )
                    await db.commit()
            # An org owner or admin reaches every workspace of the organization.
            if any(invitation.org_role for invitation in accepted):
                await MEMBERSHIPS.sync_org_wide_roles(user.id)
            # What derives from who belongs to an organization or a workspace
            # (its default groups, shared graphs) follows.
            for invitation in accepted:
                if invitation.organization_id and invitation.org_role:
                    await MEMBERSHIPS.changed(org_container(invitation.organization_id))
                if invitation.workspace_id:
                    container = await AUTHZ.container_of(invitation.workspace_id)
                    if container is not None:
                        await MEMBERSHIPS.changed(container)

        return claim

    def service(self, db: AsyncSession) -> InvitationService:
        return InvitationService(
            InvitationSecondaryAdapterPostgres(db),
            self.directory,
            self.grants,
            self.mailer,
            sign_in_url=sign_in_url,
            clock=now_naive,
        )


RUNTIME = InvitationRuntime()


def configure(runtime: InvitationRuntime) -> InvitationRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


def get_invitation_service(db: AsyncSession = Depends(get_db)) -> InvitationService:
    """The invitation service of a request (a route dependency)."""
    return RUNTIME.service(db)


# =============================================================================
# The move of pending invitations into people (``migration.py``)
# =============================================================================

# One API process (or ``abi user migrate-invitations``) moves them at a time.
MIGRATION_LOCK = 0x4E58_5045_4F50_4C45  # "NXPEOPLE"
# How often, and how long apart, a start retries a provider that does not answer
# yet (the built-in IdP runs as a module: the API may start before it answers).
MIGRATION_ATTEMPTS = 60
MIGRATION_RETRY_SECONDS = 5.0

_MARKER_TABLE = (
    "CREATE TABLE IF NOT EXISTS iam_migrations ("
    "name VARCHAR(128) PRIMARY KEY, "
    "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
    "report TEXT)"
)


@asynccontextmanager
async def migration_lock(engine: AsyncEngine) -> AsyncIterator[None]:
    """A session advisory lock on PostgreSQL, on a connection of its own: another
    process waits, then finds the invitations moved. SQLite has none: each
    invitation is taken once (pending → migrated) whoever runs."""
    if engine.dialect.name != "postgresql":
        yield
        return
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATION_LOCK})
        try:
            yield
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK})


async def migration_recorded(db: AsyncSession) -> bool:
    await db.execute(text(_MARKER_TABLE))
    found = (
        await db.execute(
            text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": MIGRATION_NAME}
        )
    ).first()
    return found is not None


async def _record_migration(db: AsyncSession, report: MigrationReport) -> None:
    try:
        await db.execute(
            text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
            {
                "n": MIGRATION_NAME,
                "at": now_naive(),
                "r": json.dumps(
                    {
                        "migrated": report.migrated,
                        "bound": report.bound,
                        "unbound": report.unbound,
                        "linked": report.linked,
                        "skipped": report.skipped,
                    }
                ),
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()  # another process recorded it first


def invitation_migration(
    db: AsyncSession,
    identity: Callable[[], Any | None] = default_identity,
    iam: Callable[[], Any | None] = default_iam,
) -> InvitationMigration:
    return InvitationMigration(
        InvitationSecondaryAdapterPostgres(db),
        PeopleSecondaryAdapterPostgres(db),
        EngineMigrationGateway(identity, iam),
        clock=now_naive,
    )


async def migrate_pending_invitations(
    sessions: Callable[[], Any],
    engine: AsyncEngine,
    *,
    identity: Callable[[], Any | None] = default_identity,
    iam: Callable[[], Any | None] = default_iam,
    force: bool = False,
) -> MigrationReport | None:
    """Move the pending invitations into invited people, once: None when
    ``iam_migrations`` records it done (``force``: run anyway, as the CLI does).
    Recorded once a run left nothing to retry."""
    async with migration_lock(engine):
        async with sessions() as db:
            if await migration_recorded(db) and not force:
                return None
            await db.commit()
            report = await invitation_migration(db, identity, iam).run()
            if report.finished:
                await _record_migration(db, report)
            return report


async def migrate_when_ready(
    sessions: Callable[[], Any],
    engine: AsyncEngine,
    *,
    identity: Callable[[], Any | None] = default_identity,
    iam: Callable[[], Any | None] = default_iam,
) -> MigrationReport | None:
    """The start's move: tried again while a provider does not answer yet. What
    fails otherwise is logged and tried at the next start (not recorded)."""
    report: MigrationReport | None = None
    for attempt in range(MIGRATION_ATTEMPTS):
        try:
            report = await migrate_pending_invitations(sessions, engine, identity=identity, iam=iam)
        except Exception as exc:  # noqa: BLE001 - never stops the API; tried at the next start
            logger.opt(exception=exc).error(
                "Pending invitations were not moved to the people directory"
            )
            return None
        if report is None:
            return None
        if report.migrated:
            logger.info(
                f"{report.migrated} pending invitation(s) are invited people now "
                f"({report.bound} bound, {report.unbound} waiting for their first sign-in, "
                f"{report.linked} existing)"
            )
        if not report.deferred:
            return report
        if attempt == 0:
            logger.info(
                f"{report.deferred} pending invitation(s) wait for their identity provider to answer"
            )
        await asyncio.sleep(MIGRATION_RETRY_SECONDS)
    logger.warning(
        "Some pending invitations were not moved to the people directory: their identity "
        "provider never answered. They still work as before; the next start (or "
        "`abi user migrate-invitations --apply`) moves them."
    )
    return report


async def migrate_from_cli(
    database_url: str, services: Any, *, apply: bool
) -> tuple[list[Any], MigrationReport | None]:
    """``abi user migrate-invitations``: the pending invitations, and (``apply``)
    the report of their move, run whether or not a start recorded it. Roles are
    IAM's: ``services`` are the engine's (IAM and identity) the CLI opened."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    previous = iam_runtime.configure(lambda: services.iam)
    try:
        async with sessions() as db:
            pending = await invitation_migration(db).pending()
        if not apply:
            return pending, None
        report = await migrate_pending_invitations(
            sessions,
            engine,
            identity=lambda: services.identity,
            iam=lambda: services.iam,
            force=True,
        )
        return pending, report
    finally:
        iam_runtime.configure(previous)
        await engine.dispose()
