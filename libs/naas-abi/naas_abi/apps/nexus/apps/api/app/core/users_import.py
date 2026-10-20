"""Replay a people snapshot (``config.users.yaml``) into the Nexus database.

Create-only, so it is safe to run against a live platform:

- creates accounts that do not exist (random password; users sign in with a
  magic link). Existing accounts are left untouched, superadmin flag included;
- inserts missing organization and workspace memberships. A membership that
  already exists keeps its role, even if the snapshot says otherwise;
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
from naas_abi.apps.nexus.apps.api.app.core.org_seed import (
    _generate_password,
    _get_user_by_email,
    _hash_password,
    _normalize_email,
)
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
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
        hashed_password=_hash_password(_generate_password()),
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


async def import_users(session: AsyncSession, entries: list[dict[str, Any]]) -> ImportReport:
    """Apply ``entries`` create-only. The caller owns the transaction."""
    report = ImportReport()
    now = datetime.now(UTC).replace(tzinfo=None)
    org_ids: dict[str, str | None] = {}
    workspace_ids: dict[str, str | None] = {}

    async def org_id_for(slug: str) -> str | None:
        if slug not in org_ids:
            org_ids[slug] = (
                await session.execute(
                    select(OrganizationModel.id).where(OrganizationModel.slug == slug)
                )
            ).scalar_one_or_none()
        return org_ids[slug]

    async def workspace_id_for(slug: str) -> str | None:
        if slug not in workspace_ids:
            workspace_ids[slug] = (
                await session.execute(select(WorkspaceModel.id).where(WorkspaceModel.slug == slug))
            ).scalar_one_or_none()
        return workspace_ids[slug]

    for entry in entries:
        user, created = await _ensure_user(session, entry, now)
        report.users_created += int(created)

        for membership in entry.get("organizations") or []:
            org_id = await org_id_for(str(membership["slug"]))
            if org_id is None:
                report.missing.add(f"organization {membership['slug']}")
                continue
            exists = (
                await session.execute(
                    select(OrganizationMemberModel.id)
                    .where(OrganizationMemberModel.organization_id == org_id)
                    .where(OrganizationMemberModel.user_id == user.id)
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    OrganizationMemberModel(
                        id=str(uuid4()),
                        organization_id=org_id,
                        user_id=user.id,
                        role=membership.get("role", "member"),
                        created_at=now,
                    )
                )
                report.organization_memberships_created += 1

        for membership in entry.get("workspaces") or []:
            workspace_id = await workspace_id_for(str(membership["slug"]))
            if workspace_id is None:
                report.missing.add(f"workspace {membership['slug']}")
                continue
            exists = (
                await session.execute(
                    select(WorkspaceMemberModel.id)
                    .where(WorkspaceMemberModel.workspace_id == workspace_id)
                    .where(WorkspaceMemberModel.user_id == user.id)
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    WorkspaceMemberModel(
                        id=str(uuid4()),
                        workspace_id=workspace_id,
                        user_id=user.id,
                        role=membership.get("role", "member"),
                        created_at=now,
                    )
                )
                report.workspace_memberships_created += 1
        await session.flush()

    return report


async def _main(path: str, dry_run: bool) -> ImportReport:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        report = await import_users(session, load_entries(path))
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Snapshot file, e.g. config.users.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Report without committing")
    args = parser.parse_args()
    report = asyncio.run(_main(args.path, args.dry_run))
    print(
        f"{'[dry-run] ' if args.dry_run else ''}users created={report.users_created} "
        f"org memberships created={report.organization_memberships_created} "
        f"workspace memberships created={report.workspace_memberships_created}"
    )
    for item in sorted(report.missing):
        print(f"missing: {item}")


if __name__ == "__main__":
    main()
