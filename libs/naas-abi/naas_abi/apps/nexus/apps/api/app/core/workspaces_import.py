"""Replay a workspace snapshot (``config.workspaces.yaml``) into the Nexus database.

The config's ``workspaces`` entries only seed resources (agents, apps,
ontologies, graphs, maps). What the app manages (name, owner, group,
description, branding and feature overrides) lives in the database, and this
snapshot restores it. Fill-only, so it is safe to run against a live platform:

- creates a workspace whose slug does not exist, under its organization
  (owner: ``owner_email``, else the organization owner);
- on an existing workspace, fills only empty values. A name equal to the
  slug (what the seed sets when the config has no name) counts as empty.
  ``feature_overrides`` is written only when the workspace never saved any;
- never deletes anything. Unknown organizations and owners are reported.

Not run on API boot. Usage::

    python -m naas_abi.apps.nexus.apps.api.app.core.workspaces_import config.workspaces.yaml
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
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    dump_feature_overrides,
)
from naas_abi.apps.nexus.apps.api.app.core.org_seed import (
    _ensure_workspace_member,
    _get_user_by_email,
    _normalize_email,
)
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Snapshot key -> workspaces column, filled only where the column is empty.
_FILL_FIELDS = {
    "description": "description",
    "group": "workspace_group",
    "logo_url": "logo_url",
    "logo_emoji": "logo_emoji",
    "primary_color": "primary_color",
    "accent_color": "accent_color",
    "background_color": "background_color",
    "background_image_url": "background_image_url",
    "sidebar_color": "sidebar_color",
    "font_family": "font_family",
}


@dataclass
class ImportReport:
    workspaces_created: int = 0
    workspaces_updated: int = 0
    missing: set[str] = field(default_factory=set)


def load_entries(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("workspaces") or [])


def _feature_overrides(entry: dict[str, Any]) -> dict[str, bool] | None:
    raw = entry.get("feature_overrides")
    if not isinstance(raw, dict):
        return None
    return {str(k): bool(v) for k, v in raw.items() if k in KNOWN_FEATURE_KEYS}


async def import_workspaces(session: AsyncSession, entries: list[dict[str, Any]]) -> ImportReport:
    """Apply ``entries`` fill-only. The caller owns the transaction."""
    report = ImportReport()
    now = datetime.now(UTC).replace(tzinfo=None)
    orgs: dict[str, OrganizationModel | None] = {}

    async def org_for(slug: str) -> OrganizationModel | None:
        if slug not in orgs:
            orgs[slug] = (
                await session.execute(
                    select(OrganizationModel).where(OrganizationModel.slug == slug)
                )
            ).scalar_one_or_none()
        return orgs[slug]

    async def owner_id_for(entry: dict[str, Any], org: OrganizationModel | None) -> str | None:
        email = entry.get("owner_email")
        if email:
            user = await _get_user_by_email(session, _normalize_email(str(email)))
            if user is not None:
                return user.id
            report.missing.add(f"owner {email}")
        return org.owner_id if org is not None else None

    for entry in entries:
        slug = str(entry["slug"])
        org_slug = entry.get("organization")
        org = await org_for(str(org_slug)) if org_slug else None
        if org_slug and org is None:
            report.missing.add(f"organization {org_slug}")
        overrides = _feature_overrides(entry)

        workspace = (
            await session.execute(select(WorkspaceModel).where(WorkspaceModel.slug == slug))
        ).scalar_one_or_none()

        if workspace is None:
            owner_id = await owner_id_for(entry, org)
            if org is None or owner_id is None:
                report.missing.add(f"workspace {slug} (no organization or owner to create it)")
                continue
            workspace = WorkspaceModel(
                id=f"ws-{uuid4().hex[:12]}",
                slug=slug,
                name=entry.get("name") or slug,
                owner_id=owner_id,
                organization_id=org.id,
                feature_overrides=dump_feature_overrides(overrides),
                created_at=now,
                updated_at=now,
                **{column: entry.get(key) for key, column in _FILL_FIELDS.items()},
            )
            session.add(workspace)
            await session.flush()
            await _ensure_workspace_member(session, workspace.id, owner_id, "owner")
            report.workspaces_created += 1
            continue

        changed = False
        if entry.get("name") and (not workspace.name or workspace.name == slug):
            workspace.name = entry["name"]
            changed = True
        for key, column in _FILL_FIELDS.items():
            value = entry.get(key)
            if value and not getattr(workspace, column, None):
                setattr(workspace, column, value)
                changed = True
        if not workspace.organization_id and org is not None:
            workspace.organization_id = org.id
            changed = True
        if not workspace.owner_id:
            owner_id = await owner_id_for(entry, org)
            if owner_id:
                workspace.owner_id = owner_id
                changed = True
        if overrides is not None and workspace.feature_overrides is None:
            workspace.feature_overrides = dump_feature_overrides(overrides)
            changed = True
        if changed:
            workspace.updated_at = now
            report.workspaces_updated += 1
        await session.flush()

    return report


async def _main(path: str, dry_run: bool) -> ImportReport:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        report = await import_workspaces(session, load_entries(path))
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Snapshot file, e.g. config.workspaces.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Report without committing")
    args = parser.parse_args()
    report = asyncio.run(_main(args.path, args.dry_run))
    print(
        f"{'[dry-run] ' if args.dry_run else ''}workspaces created={report.workspaces_created} "
        f"workspaces updated={report.workspaces_updated}"
    )
    for item in sorted(report.missing):
        print(f"missing: {item}")


if __name__ == "__main__":
    main()
