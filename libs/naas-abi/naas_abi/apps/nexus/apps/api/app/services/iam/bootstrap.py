"""Nexus at startup: its catalog and its role data in IAM.

* ``register_catalog`` gives IAM the ``nexus`` action catalog (the built-in
  roles are regenerated from it; its flags say what they leave out: features,
  the owners' deletes) and the platform grants of the shared repository. No
  role brings a feature: ``role_features`` moved what they brought into each
  workspace's policies.
* ``migrate_role_data`` moves what Nexus kept itself into IAM, once: the
  organization and workspace memberships (and the ``owner_id`` fallbacks) as
  role attachments, the superadmin flags as ``builtin.platform_admin``, and a
  container for every organization and workspace. Afterwards IAM is the only
  record: nothing reads those rows for a decision again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    ROLE_NAMES,
    Memberships,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.names import PLATFORM, resource_name
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

MIGRATION_NAME = "iam_roles_v1"


async def nexus_user_exists(user_id: str) -> bool:
    """Whether Nexus has a user with this id: what lets a legacy id become an IAM user."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
        AuthSecondaryAdapterPostgres,
    )

    async with AsyncSessionLocal() as db:
        return await AuthSecondaryAdapterPostgres(db=db).get_user_by_id(user_id) is not None


def shared_repo_grants(repo_id: str) -> list[roles.PlatformGrant]:
    """The one repository slides, documents, sheets and the code section share
    (``coding_repo_id``) is a platform container, so no workspace role reaches it.
    Every workspace member reaches it by level (viewers read, members write): the
    routes still keep a project to its workspace by its branch name, and a
    workspace's own repositories are placed in it."""
    return [
        roles.PlatformGrant(
            "source_control",
            (
                resource_name("source_control", "repo", repo_id),
                resource_name("source_control", "branch", [repo_id], kind="path") + "/*",
                resource_name("source_control", "proposal", [repo_id], kind="path") + "/*",
            ),
        ),
        # The datasets of the platform's modules are read by every workspace's
        # members, as they were before roles: nothing links a namespace to one
        # workspace, and Nexus only reads them.
        roles.PlatformGrant(
            "dataset",
            (f"{PLATFORM}dataset:namespace/*", f"{PLATFORM}dataset:dataset/*"),
            member_writes=False,
        ),
    ]


async def register_catalog() -> None:
    """Register the ``nexus`` catalog and the shared repository's platform
    grants, as the engine."""
    grants = shared_repo_grants(settings.coding_repo_id)

    def work() -> None:
        iam = runtime.iam()
        with as_service_account("engine"):
            iam.register_catalog(NEXUS_CATALOG)
            iam.set_platform_grants(grants)

    await run_in_threadpool(work)


@dataclass
class MigrationReport:
    applied: bool
    orgs: int = 0
    workspaces: int = 0
    granted: int = 0
    kept: int = 0
    platform_admins: int = 0
    notes: list[str] = field(default_factory=list)


async def migrate_role_data(db: AsyncSession, *, apply: bool = True) -> MigrationReport:
    """Move memberships, owners and superadmin flags into IAM, once.

    Rows already held in IAM win (a role changed through the new API is never
    undone by an old row). Returns what was done; ``apply=False`` reports
    without changing anything.
    """
    done = (
        await db.execute(
            text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": MIGRATION_NAME}
        )
    ).first()
    if done is not None:
        return MigrationReport(applied=False, notes=["already applied"])

    orgs = (await db.execute(text("SELECT id, owner_id FROM organizations"))).all()
    workspaces = (
        await db.execute(text("SELECT id, organization_id, owner_id FROM workspaces"))
    ).all()
    org_members = (
        await db.execute(text("SELECT organization_id, user_id, role FROM organization_members"))
    ).all()
    ws_members = (
        await db.execute(text("SELECT workspace_id, user_id, role FROM workspace_members"))
    ).all()
    admins = (
        await db.execute(text("SELECT id FROM users WHERE is_superadmin = :t"), {"t": True})
    ).all()
    ws_org = {str(row[0]): row[1] for row in workspaces}

    entries: list[tuple[str, str, str]] = []
    # The owner fallbacks first: an explicit membership row of the same user wins
    # over it (it is how ``get_workspace_role`` read them).
    for org_id, owner_id in orgs:
        if owner_id:
            entries.append((str(owner_id), "owner", org_container(str(org_id))))
    for workspace_id, org_id, owner_id in workspaces:
        if owner_id:
            entries.append(
                (str(owner_id), "owner", workspace_container(_org(org_id), str(workspace_id)))
            )
    explicit: list[tuple[str, str, str]] = []
    for org_id, user_id, role in org_members:
        explicit.append((str(user_id), _role(role), org_container(str(org_id))))
    for workspace_id, user_id, role in ws_members:
        explicit.append(
            (
                str(user_id),
                _role(role),
                workspace_container(_org(ws_org.get(str(workspace_id))), str(workspace_id)),
            )
        )
    # Where a user has both, the explicit row is what they hold today.
    explicit_keys = {(u, scope) for u, _, scope in explicit}
    entries = [e for e in entries if (e[0], e[2]) not in explicit_keys] + explicit

    report = MigrationReport(
        applied=apply, orgs=len(orgs), workspaces=len(workspaces), platform_admins=len(admins)
    )
    if not apply:
        report.notes.append(f"would grant {len(entries)} roles")
        return report

    def admins_of_platform(iam: Any) -> None:
        with as_service_account("api"):
            for (user_id,) in admins:
                principal = MEMBERSHIPS._principal_id(iam, str(user_id))
                iam.attach_policy(roles.PLATFORM_ADMIN, principal)

    for org_id, _ in orgs:
        await MEMBERSHIPS.register_org(str(org_id))
    for workspace_id, org_id, _ in workspaces:
        await MEMBERSHIPS.register_workspace(_org(org_id), str(workspace_id))
    await run_in_threadpool(lambda: admins_of_platform(runtime.iam()))
    report.granted, report.kept = await MEMBERSHIPS.seed(entries, replace=False)
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps(report.__dict__),
        },
    )
    await db.commit()
    logger.info(f"Nexus role data moved into IAM: {report}")
    return report


def _org(raw: Any) -> str | None:
    return str(raw) if raw else None


def _role(raw: Any) -> str:
    return str(raw) if str(raw) in ROLE_NAMES else "member"


__all__ = [
    "MEMBERSHIPS",
    "Memberships",
    "MigrationReport",
    "migrate_role_data",
    "register_catalog",
]
