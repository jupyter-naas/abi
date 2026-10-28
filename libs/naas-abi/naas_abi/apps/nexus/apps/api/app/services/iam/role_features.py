"""The role features become policies of each workspace, once.

Before, each built-in role brought features: the deployment's
``feature_flags.role_baseline``, overlaid per organization by
``feature_flags.organization_overrides`` and the ``organization_role_features``
table, within ``enabled_features``. IAM generated ``builtin.features.*`` from them
and attached them beside each role at a workspace or org-wide. No role brings a
feature any more: a policy does.

``migrate_role_features`` keeps every user's features as they were: for each
workspace and each role, the features that role had there become the
workspace's policy "Features of <role>", attached at the workspace to whoever
holds that role there, directly or through an organization-wide role (a group
holding the role included). IAM drops the old ``builtin.features.*`` at boot;
this move reads the configuration and the overlay table, not them. Recorded in
``iam_migrations``; each step may run again, and the overlay table is dropped
once it is recorded. Afterwards the configuration's role features do nothing,
and a configuration that still sets them gets a warning at each start.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "role_features_v1"
# The move of the workspace feature overrides reads the role features too: it
# runs first (``sets.migrate_feature_overrides``).
AFTER = "workspace_feature_sets_v1"
OVERLAY_TABLE = "organization_role_features"
ROLE_NAMES = tuple(role.removeprefix("builtin.") for role in roles.ROLES)
# The settings that gave roles their features, read by this move only.
DEPRECATED_SETTINGS = ("role_baseline", "organization_overrides", "workspace_overrides")


def policy_name(role: str) -> str:
    return f"Features of {role}"


def resolve_role_baseline(
    flags: FeatureFlagsConfig,
    *,
    organization_id: str | None = None,
    organization_override: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[str]]:
    """The features of each role as the configuration gave them (later wins): the
    deployment's ``role_baseline``, the org's ``organization_overrides``, then
    the org's stored overlay."""
    baseline = {role: list(features) for role, features in flags.role_baseline.items()}
    if organization_id:
        for role, features in (flags.organization_overrides.get(organization_id) or {}).items():
            baseline[role] = list(features)
    for role, features in (organization_override or {}).items():
        baseline[role] = list(features)
    return baseline


def role_features(
    flags: FeatureFlagsConfig,
    org_id: str | None,
    overlays: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, tuple[str, ...]]:
    """``{role: features}`` each role had in a workspace of ``org_id`` (None: a
    workspace with no organization): its defaults, within ``enabled_features``,
    in catalog order."""
    enabled = enabled_feature_catalog(flags)
    resolved = resolve_role_baseline(
        flags,
        organization_id=org_id,
        organization_override=overlays.get(org_id) if org_id else None,
    )
    return {
        role: tuple(key for key in enabled if key in set(resolved.get(role) or ()))
        for role in ROLE_NAMES
    }


@dataclass(frozen=True)
class WorkspaceFeatures:
    """What one workspace's roles had: ``{role: features}``."""

    org: str
    workspace: str
    by_role: Mapping[str, tuple[str, ...]]

    @property
    def scope(self) -> str:
        return f"abi:{self.org}:{self.workspace}"


def plan(
    workspaces: Iterable[tuple[str, str | None]],
    flags: FeatureFlagsConfig,
    overlays: Mapping[str, Mapping[str, Sequence[str]]],
) -> list[WorkspaceFeatures]:
    """The pure part of ``migrate_role_features``: per ``(workspace, org)``."""
    return [
        WorkspaceFeatures(org_id or NO_ORG, workspace_id, role_features(flags, org_id, overlays))
        for workspace_id, org_id in sorted(workspaces, key=lambda w: w[0])
    ]


def policy_document(features: Iterable[str]) -> PolicyDocument:
    return PolicyDocument(
        statements=(
            Statement(
                "Allow",
                ("nexus:UseFeature",),
                tuple(f"${{scope}}:nexus:feature/{key}" for key in features),
                sid="UseFeatures",
            ),
        )
    )


def _workspace_policy(iam: Any, scope: str, role: str, features: tuple[str, ...]) -> Any:
    """The workspace's "Features of <role>": the one an earlier, interrupted run
    made, else a new one."""
    name = policy_name(role)
    document = policy_document(features)
    after: str | None = None
    while True:
        page = iam.list_policies(scope=scope, limit=200, after=after)
        for policy in page.items:
            if (
                policy.name == name
                and policy.owner_scope == scope
                and policy.document.statements == document.statements
            ):
                return policy
        after = page.next_after
        if after is None:
            break
    return iam.create_policy(
        name,
        document,
        description=(
            f"The features the {role} role had in this workspace when roles stopped "
            "bringing any. Attach it to whoever should use them."
        ),
        scope=scope,
    )


# (role, principal, org, workspace): ``role_attachments``.
RoleAttachments = Sequence[tuple[str, str, str, str]]


def role_attachments(iam: Any) -> list[tuple[str, str, str, str]]:
    """``(role, principal, org, workspace)`` of every role attached at a workspace
    or org-wide scope (neither field ``-``): those that brought features.

    A role attached across organizations (``abi:*:…``, which Nexus never makes)
    brought the deployment's features in every organization: kept, it would
    widen where an organization's overlay gave less, so it is left out and
    named in the log for the operator."""
    found: list[tuple[str, str, str, str]] = []
    for role in roles.ROLES:
        for attachment in iam.list_attachments(policy_id=role):
            if attachment.scope is None:
                continue
            _abi, org, workspace = attachment.scope.split(":", 2)
            if "-" in (org, workspace):
                continue
            if org == "*":
                _log.warning(
                    "%s is attached to %s at %s, across organizations: its features "
                    "are not moved; grant them with a policy if they are still wanted",
                    role,
                    attachment.principal_id,
                    attachment.scope,
                )
                continue
            found.append((role.removeprefix("builtin."), attachment.principal_id, org, workspace))
    return found


def holders(
    attachments: Iterable[tuple[str, str, str, str]], org: str, workspace: str
) -> dict[str, set[str]]:
    """``{role: principals}`` holding each role at the workspace, directly or
    through a scope that covers it (organization-wide, ``abi:<org>:*``): who had
    its features there."""
    found: dict[str, set[str]] = {}
    for role, principal_id, at_org, at_workspace in attachments:
        if at_org == org and at_workspace in (workspace, "*"):
            found.setdefault(role, set()).add(principal_id)
    return found


def apply(iam: Any, move: WorkspaceFeatures, attachments: RoleAttachments) -> int:
    """One workspace's move, as ``engine``: a "Features of <role>" for each role
    that had features there, attached to who holds the role; returns the
    attachments it holds.
    Each step may run again: finding the policy before making it, attaching
    what is attached."""
    iam.put_scope(move.org)
    iam.put_scope(move.org, move.workspace)
    attached = 0
    held = holders(attachments, move.org, move.workspace)
    # Every role that had features gets its policy, held or not: it is what an
    # invitation to the workspace carries for a newcomer.
    for role in ROLE_NAMES:
        features = move.by_role.get(role) or ()
        if not features:
            continue
        policy = _workspace_policy(iam, move.scope, role, features)
        for principal_id in sorted(held.get(role, ())):
            iam.attach_policy(policy.id, principal_id, move.scope)
            attached += 1
    return attached


async def read_overlays(db: AsyncSession) -> dict[str, dict[str, list[str]]]:
    """The organizations' stored role features (``organization_role_features``);
    none once the table is gone."""
    if not await _has_overlay_table(db):
        return {}
    overlays: dict[str, dict[str, list[str]]] = {}
    for org_id, raw in (
        await db.execute(text(f"SELECT organization_id, role_baseline FROM {OVERLAY_TABLE}"))
    ).all():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            overlays[str(org_id)] = {str(k): list(v) for k, v in parsed.items()}
    return overlays


async def _has_overlay_table(db: AsyncSession) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: inspect(sync).has_table(OVERLAY_TABLE))


async def _recorded(db: AsyncSession, name: str) -> bool:
    found = (
        await db.execute(text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": name})
    ).first()
    return found is not None


def warn_deprecated_settings(flags: FeatureFlagsConfig) -> list[str]:
    """Warn about the role feature settings a configuration still sets: they do
    nothing once the move ran. Returns their names."""
    found = [name for name in DEPRECATED_SETTINGS if name in flags.model_fields_set]
    if found:
        _log.warning(
            "feature_flags.%s no longer do anything: no role brings a feature, a "
            'policy does (each workspace\'s "Features of <role>"). Remove them from '
            "the configuration.",
            ", ".join(found),
        )
    return found


async def migrate_role_features(db: AsyncSession, flags: FeatureFlagsConfig) -> int | None:
    """Move the role features into each workspace's policies, once (see the
    module). Returns the number of attachments made, None when it did not run:
    done already, or waiting for the move of the workspace feature overrides."""
    if await _recorded(db, MIGRATION_NAME):
        warn_deprecated_settings(flags)
        return None
    if not await _recorded(db, AFTER):
        _log.warning(
            "The role features wait for the workspace feature overrides to move: "
            "the next start tries again"
        )
        return None
    overlays = await read_overlays(db)
    rows = (await db.execute(text("SELECT id, organization_id FROM workspaces"))).all()
    moves = plan(((str(ws), str(org) if org else None) for ws, org in rows), flags, overlays)

    def work() -> tuple[int, list[str]]:
        iam = runtime.iam()
        made, failed = 0, []
        with as_service_account("engine"):
            attachments = role_attachments(iam)
            for move in moves:
                try:
                    made += apply(iam, move, attachments)
                except Exception:  # noqa: BLE001 - one workspace never stops the others
                    _log.warning(
                        "The role features of workspace %s were not moved; the next "
                        "start tries again",
                        move.workspace,
                        exc_info=True,
                    )
                    failed.append(move.workspace)
        return made, failed

    made, failed = await run_in_threadpool(work)
    if failed:
        # Not recorded: the next start moves them again from the same settings
        # and the overlay table, which stays until then.
        return made
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps({"workspaces": len(moves), "attachments": made}),
        },
    )
    await db.execute(text(f"DROP TABLE IF EXISTS {OVERLAY_TABLE}"))
    await db.commit()
    _log.info(
        "The role features of %d workspaces became their policies (%d attachments)",
        len(moves),
        made,
    )
    return made


__all__ = [
    "AFTER",
    "DEPRECATED_SETTINGS",
    "MIGRATION_NAME",
    "WorkspaceFeatures",
    "apply",
    "holders",
    "migrate_role_features",
    "plan",
    "policy_document",
    "role_attachments",
    "policy_name",
    "read_overlays",
    "resolve_role_baseline",
    "role_features",
    "warn_deprecated_settings",
]
