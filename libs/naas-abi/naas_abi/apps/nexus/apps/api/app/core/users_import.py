"""Replay a people snapshot (``config.users.yaml``) into Nexus.

Create-only, so it is safe to run against a live platform:

- creates accounts that do not exist (no password: people sign in at the identity
  provider; ``abi user migrate --apply`` makes the new accounts exist there; a new
  ``is_superadmin`` account is a platform administrator in IAM). Existing accounts
  are left untouched, superadmin flag included;
- gives the roles the snapshot names where the person holds none yet: roles are
  IAM's (``services/iam/memberships``), so this runs in an engine (``main`` opens
  the project's). A role already held is kept, even if the snapshot says otherwise;
- never deletes anything. Unknown organization/workspace slugs are reported.

Not run on API boot. Usage::

    python -m naas_abi.apps.nexus.apps.api.app.core.users_import config.users.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.org_seed import _get_user_by_email, _normalize_email
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope, workspace_scope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ImportReport:
    users_created: int = 0
    organization_memberships_created: int = 0
    workspace_memberships_created: int = 0
    missing: set[str] = field(default_factory=set)


def load_entries(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("users") or [])


async def _ensure_user(
    session: AsyncSession, entry: dict[str, Any], now: datetime
) -> tuple[UserModel, bool]:
    email = _normalize_email(str(entry["email"]))
    user = await _get_user_by_email(session, email)
    if user is not None:
        return user, False
    user = UserModel(
        id=f"user-{uuid4().hex[:12]}",
        email=email,
        name=entry.get("name") or email.split("@", 1)[0],
        avatar=entry.get("avatar"),
        organization=entry.get("organization"),
        job_title=entry.get("job_title"),
        bio=entry.get("bio"),
        is_superadmin=bool(entry.get("is_superadmin", False)),
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()
    return user, True


async def import_users(
    session: AsyncSession,
    entries: list[dict[str, Any]],
    *,
    memberships: Memberships = MEMBERSHIPS,
    apply: bool = True,
) -> ImportReport:
    """Apply ``entries`` create-only. The caller owns the transaction (and, with
    ``apply=False``, rolls it back: the roles are then only counted, never given)."""
    report = ImportReport()
    now = datetime.now(UTC).replace(tzinfo=None)
    org_ids: dict[str, str | None] = {}
    workspace_orgs: dict[str, tuple[str, str | None] | None] = {}

    async def org_id_for(slug: str) -> str | None:
        if slug not in org_ids:
            org_ids[slug] = (
                await session.execute(
                    select(OrganizationModel.id).where(OrganizationModel.slug == slug)
                )
            ).scalar_one_or_none()
        return org_ids[slug]

    async def workspace_for(slug: str) -> tuple[str, str | None] | None:
        """``(workspace id, organization id)``."""
        if slug not in workspace_orgs:
            row = (
                await session.execute(
                    select(WorkspaceModel.id, WorkspaceModel.organization_id).where(
                        WorkspaceModel.slug == slug
                    )
                )
            ).one_or_none()
            workspace_orgs[slug] = (str(row[0]), row[1]) if row is not None else None
        return workspace_orgs[slug]

    org_roles: list[tuple[str, str, str]] = []
    workspace_roles: list[tuple[str, str, str]] = []
    scopes: set[tuple[str | None, str | None]] = set()

    async def wanted(user_id: str, created: bool, scope: str) -> bool:
        return created or await memberships.role_at(user_id, scope) is None

    for entry in entries:
        user, created = await _ensure_user(session, entry, now)
        report.users_created += int(created)
        if created and entry.get("is_superadmin") and apply:
            # A platform administrator is IAM's attachment, not the flag of the row.
            await memberships.set_platform_admin(user.id, True)

        for membership in entry.get("organizations") or []:
            org_id = await org_id_for(str(membership["slug"]))
            if org_id is None:
                report.missing.add(f"organization {membership['slug']}")
                continue
            role = str(membership.get("role", "member"))
            scope = org_scope(org_id)
            scopes.add((org_id, None))
            if await wanted(user.id, created, scope):
                org_roles.append((user.id, role, scope))

        for membership in entry.get("workspaces") or []:
            found = await workspace_for(str(membership["slug"]))
            if found is None:
                report.missing.add(f"workspace {membership['slug']}")
                continue
            workspace_id, org_id = found
            role = str(membership.get("role", "member"))
            scope = workspace_scope(org_id, workspace_id)
            scopes.add((org_id, workspace_id))
            if await wanted(user.id, created, scope):
                workspace_roles.append((user.id, role, scope))
        await session.flush()

    report.organization_memberships_created = len(org_roles)
    report.workspace_memberships_created = len(workspace_roles)
    if apply:
        for org_id, workspace_id in sorted(scopes, key=str):
            if workspace_id is None and org_id is not None:
                await memberships.register_org(org_id)
            elif workspace_id is not None:
                await memberships.register_workspace(org_id, workspace_id)
        await memberships.seed(org_roles, replace=False)
        await memberships.seed(workspace_roles, replace=False)
    return report


async def _main(path: str, dry_run: bool) -> ImportReport:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        report = await import_users(session, load_entries(path), apply=not dry_run)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return report


def _in_engine(work: Any) -> Any:
    """Run ``work()`` with the project's engine open: roles are IAM's."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi_cli.cli.iam import open_engine_services

    services, close = open_engine_services()
    previous = runtime.configure(lambda: services.iam)
    try:
        return work()
    finally:
        runtime.configure(previous)
        close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Snapshot file, e.g. config.users.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Report without committing")
    args = parser.parse_args()
    report = _in_engine(lambda: asyncio.run(_main(args.path, args.dry_run)))
    print(
        f"{'[dry-run] ' if args.dry_run else ''}users created={report.users_created} "
        f"org memberships created={report.organization_memberships_created} "
        f"workspace memberships created={report.workspace_memberships_created}"
    )
    for item in sorted(report.missing):
        print(f"missing: {item}")
    if report.users_created and not args.dry_run:
        print(
            "Run `abi user migrate --apply` to make the new accounts exist at the identity provider."
        )


if __name__ == "__main__":
    main()
