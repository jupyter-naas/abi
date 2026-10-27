"""Replay a workspace snapshot (``config.workspaces.yaml``) into the Nexus database.

The config's ``workspaces`` entries only seed resources (agents, apps,
ontologies, graphs, maps). What the app manages (name, owner, group,
description, branding) lives in the database, and this snapshot restores it.
Fill-only, so it is safe to run against a live platform:

- creates a workspace whose slug does not exist, under its organization
  (owner: ``owner_email``, else the organization owner; the owner role is IAM's, so
  this runs in an engine: ``main`` opens the project's);
- on an existing workspace, fills only empty values. A name equal to the
  slug (what the seed sets when the config has no name) counts as empty.
  ``feature_overrides`` become the workspace's feature set (every feature but
  those turned off; IAM's, ``services/iam/sets.py``), recorded only when the
  workspace has none; an override turning a feature on adds nothing to a set;
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
    feature_set_from_overrides,
)
from naas_abi.apps.nexus.apps.api.app.core.org_seed import _get_user_by_email, _normalize_email
from naas_abi.apps.nexus.apps.api.app.core.users_import import _in_engine
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import placements
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
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
    # What IAM derives from them, done once the rows are committed.
    created_ids: list[str] = field(default_factory=list)
    # Workspace id -> (org id, the features of its set), from the overrides.
    feature_sets: dict[str, tuple[str, list[str]]] = field(default_factory=dict)


def load_entries(path: str | Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("workspaces") or [])


def _feature_overrides(entry: dict[str, Any]) -> dict[str, bool] | None:
    raw = entry.get("feature_overrides")
    if not isinstance(raw, dict):
        return None
    return {str(k): bool(v) for k, v in raw.items() if k in KNOWN_FEATURE_KEYS}


def feature_set_of(overrides: dict[str, bool] | None) -> list[str] | None:
    """The feature set a snapshot's overrides stand for: ``feature_set_from_overrides``."""
    return feature_set_from_overrides(overrides)


async def import_workspaces(
    session: AsyncSession,
    entries: list[dict[str, Any]],
    *,
    memberships: Memberships = MEMBERSHIPS,
    apply: bool = True,
) -> ImportReport:
    """Apply ``entries`` fill-only. The caller owns the transaction (and, with
    ``apply=False``, rolls it back: IAM is then left alone)."""
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
                created_at=now,
                updated_at=now,
                **{column: entry.get(key) for key, column in _FILL_FIELDS.items()},
            )
            session.add(workspace)
            await session.flush()
            if apply:
                # The owner is IAM's attachment; the workspace's scope exists first.
                scope = await memberships.register_workspace(org.id, workspace.id)
                await memberships.grant(owner_id, "owner", scope)
                assert scope == workspace_scope(org.id, workspace.id)
            report.workspaces_created += 1
            report.created_ids.append(workspace.id)
            features = feature_set_of(overrides)
            if features is not None:
                report.feature_sets[workspace.id] = (org.id, features)
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
        features = feature_set_of(overrides)
        if features is not None and workspace.organization_id:
            report.feature_sets[workspace.id] = (workspace.organization_id, features)
        if changed:
            workspace.updated_at = now
            report.workspaces_updated += 1
        await session.flush()

    return report


async def _main(path: str, dry_run: bool) -> ImportReport:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        report = await import_workspaces(session, load_entries(path), apply=not dry_run)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
            # What IAM derives from the rows: the kernel resources a new workspace's
            # roles reach, and the feature sets of the overrides.
            for workspace_id in report.created_ids:
                await placements.place_new_workspace(session, workspace_id)
            record_feature_sets(report.feature_sets)
    return report


def record_feature_sets(feature_sets: dict[str, tuple[str, list[str]]]) -> list[str]:
    """Record each workspace's feature set, as the engine, where its set records
    none yet (fill-only); the workspaces recorded."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi_core.engine.call_context import as_service_account

    recorded: list[str] = []
    iam = runtime.iam()
    with as_service_account("engine"):
        for workspace_id, (org_id, features) in sorted(feature_sets.items()):
            current = iam.get_set(org_id, workspace_id)
            if current.features is not None:
                continue
            iam.put_set(org_id, workspace_id, modules=current.modules, features=features)
            recorded.append(workspace_id)
    return recorded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Snapshot file, e.g. config.workspaces.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Report without committing")
    args = parser.parse_args()
    report = _in_engine(lambda: asyncio.run(_main(args.path, args.dry_run)))
    print(
        f"{'[dry-run] ' if args.dry_run else ''}workspaces created={report.workspaces_created} "
        f"workspaces updated={report.workspaces_updated}"
    )
    for item in sorted(report.missing):
        print(f"missing: {item}")


if __name__ == "__main__":
    main()
