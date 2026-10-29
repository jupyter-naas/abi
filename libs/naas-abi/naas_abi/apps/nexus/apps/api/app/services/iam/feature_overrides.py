"""The per-workspace feature overrides of earlier versions, moved once.

An override could turn a feature on or off for every role of a workspace. The
move (``migrate_feature_overrides``, recorded in ``iam_migrations`` as
``workspace_feature_sets_v1``) keeps everyone's features: an ``on`` override a
role's defaults lacked becomes a workspace policy attached to who held that role
there; what the overrides left out of the workspace becomes its feature set,
kept in the move's report and turned into the workspace's access policy by the
move of the sets (``policy_tree``). It runs before the role features' move,
which reads the role defaults and the overlay table it drops.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "workspace_feature_sets_v1"
KEPT_FEATURES_POLICY = "Features kept from the workspace's overrides"


def _org(org_id: str | None) -> str:
    return org_id or NO_ORG


@dataclass(frozen=True)
class OverrideMove:
    """What one workspace's overrides become: its feature set (None: every
    feature), and the features some of its roles gained through an ``on`` override,
    for each role that lacks them by default."""

    org: str
    workspace: str
    features: tuple[str, ...] | None
    kept: Mapping[str, tuple[str, ...]]  # role -> features its holders keep


def plan_override_moves(
    overrides: Mapping[str, Mapping[str, bool]],
    *,
    org_of: Mapping[str, str | None],
    enabled: Sequence[str],
    role_defaults: Mapping[str | None, Mapping[str, Sequence[str]]],
) -> list[OverrideMove]:
    """The pure part of ``migrate_feature_overrides``.

    An ``off`` override leaves the feature out of the workspace's set, which is
    every other feature known, enabled now or later, and always ``settings``
    (``feature_set_from_overrides``, as a snapshot import); an ``on`` one keeps it
    there and, for each role whose defaults lack it, is kept for the people holding
    that role there (``kept``, enabled features only: a policy never brings back
    one the deployment turned off). ``role_defaults`` are the role features by org
    (None: an org with no overlay)."""
    moves: list[OverrideMove] = []
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import feature_set_from_overrides

    for workspace, found in sorted(overrides.items()):
        known = {k: bool(v) for k, v in found.items() if k in enabled}
        if not known and feature_set_from_overrides(found) is None:
            continue
        org_id = org_of.get(workspace)
        found_set = feature_set_from_overrides(found)
        features = tuple(found_set) if found_set is not None else None
        defaults = role_defaults.get(org_id) or role_defaults.get(None) or {}
        kept: dict[str, tuple[str, ...]] = {}
        for role in roles.ROLES:
            name = role.removeprefix("builtin.")
            gained = tuple(
                sorted(k for k, on in known.items() if on and k not in (defaults.get(name) or ()))
            )
            if gained:
                kept[name] = gained
        moves.append(OverrideMove(_org(org_id), workspace, features, kept))
    return moves


def _kept_policy_document(features: Iterable[str]) -> PolicyDocument:
    return PolicyDocument(
        statements=(
            Statement(
                "Allow",
                ("nexus:UseFeature",),
                tuple(f"${{scope}}:nexus:feature/{key}" for key in sorted(set(features))),
                sid="KeptFromOverrides",
            ),
        )
    )


def _kept_policy(iam: Any, scope: str, features: tuple[str, ...]) -> Any:
    """The workspace's policy keeping ``features``: the one an earlier, interrupted
    run made, else a new one."""
    document = _kept_policy_document(features)
    after: str | None = None
    while True:
        page = iam.list_policies(scope=scope, limit=200, after=after)
        for policy in page.items:
            if (
                policy.name == KEPT_FEATURES_POLICY
                and policy.owner_scope == scope
                and policy.document.statements == document.statements
            ):
                return policy
        after = page.next_after
        if after is None:
            break
    return iam.create_policy(
        KEPT_FEATURES_POLICY,
        document,
        description=(
            "Features an earlier feature override gave every role of the "
            f"workspace: {', '.join(features)}. Attached to who held a role "
            "there when the overrides became the workspace's feature set."
        ),
        scope=scope,
    )


def _apply_move(iam: Any, move: OverrideMove) -> None:
    """One workspace's move. Each step may run again: finding the kept policy
    before making it, attaching what is attached."""
    scope = f"abi:{move.org}:{move.workspace}"
    # Org owners and admins hold their role org-wide.
    scopes = {scope, f"abi:{move.org}:*"}
    holders: dict[str, set[str]] = {}
    for role, features in move.kept.items():
        for attachment in iam.list_attachments(policy_id=f"builtin.{role}"):
            if attachment.scope in scopes:
                holders.setdefault(attachment.principal_id, set()).update(features)
    by_features: dict[tuple[str, ...], list[str]] = {}
    for principal_id, features in holders.items():
        by_features.setdefault(tuple(sorted(features)), []).append(principal_id)
    for features, principals in sorted(by_features.items()):
        policy = _kept_policy(iam, scope, features)
        for principal_id in sorted(principals):
            iam.attach_policy(policy.id, principal_id, scope)


async def migrate_feature_overrides(db: AsyncSession, flags: Any) -> int:
    """Move the per-workspace feature overrides (``workspaces.feature_overrides``,
    else the deprecated ``feature_flags.workspace_overrides``) once: a workspace
    policy for the people whose role gained a feature through an override, so
    nobody's features change, and the workspace's feature set, kept in the
    report (``feature_sets``) for the move of the sets into policies
    (``policy_tree``), which bounds the workspace's features with it. Then the
    column is cleared. Recorded in ``iam_migrations``; returns the number of
    workspaces moved."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
        enabled_feature_catalog,
        parse_feature_overrides,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam.role_features import (
        read_overlays,
        resolve_role_baseline,
    )

    done = (
        await db.execute(
            text("SELECT 1 FROM iam_migrations WHERE name = :name"),
            {"name": MIGRATION_NAME},
        )
    ).first()
    if done is not None:
        return 0
    rows = (
        await db.execute(
            text("SELECT id, slug, organization_id, feature_overrides FROM workspaces")
        )
    ).all()
    overrides: dict[str, dict[str, bool]] = {}
    org_of: dict[str, str | None] = {}
    for workspace_id, slug, org_id, raw in rows:
        org_of[str(workspace_id)] = org_id
        saved = parse_feature_overrides(raw)
        configured = flags.workspace_overrides.get(slug or "") or flags.workspace_overrides.get(
            str(workspace_id)
        )
        found = saved if saved is not None else configured
        if found:
            overrides[str(workspace_id)] = dict(found)
    overlays = await read_overlays(db)
    defaults: dict[str | None, Mapping[str, Sequence[str]]] = {None: resolve_role_baseline(flags)}
    for org_id in {o for o in org_of.values() if o}:
        defaults[org_id] = resolve_role_baseline(
            flags, organization_id=org_id, organization_override=overlays.get(org_id)
        )
    moves = plan_override_moves(
        overrides,
        org_of=org_of,
        enabled=enabled_feature_catalog(flags),
        role_defaults=defaults,
    )

    def work() -> list[str]:
        iam = runtime.iam()
        failed: list[str] = []
        with as_service_account("engine"):
            for move in moves:
                try:
                    iam.put_scope(move.org)
                    iam.put_scope(move.org, move.workspace)
                    _apply_move(iam, move)
                except Exception:  # noqa: BLE001 - one workspace never stops the others
                    _log.warning(
                        "The feature overrides of workspace %s were not moved; "
                        "the next start tries again",
                        move.workspace,
                        exc_info=True,
                    )
                    failed.append(move.workspace)
        return failed

    failed = await run_in_threadpool(work)
    if failed:
        # Not recorded: the next start moves them again (each step may), and
        # the overrides stay until then.
        return len(moves) - len(failed)
    await db.execute(text("UPDATE workspaces SET feature_overrides = NULL"))
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps(
                {
                    "workspaces": [m.workspace for m in moves],
                    "feature_sets": {
                        m.workspace: list(m.features) for m in moves if m.features is not None
                    },
                }
            ),
        },
    )
    await db.commit()
    if moves:
        _log.info("Moved the feature overrides of %d workspaces", len(moves))
    return len(moves)


__all__ = [
    "KEPT_FEATURES_POLICY",
    "MIGRATION_NAME",
    "OverrideMove",
    "migrate_feature_overrides",
    "plan_override_moves",
]
