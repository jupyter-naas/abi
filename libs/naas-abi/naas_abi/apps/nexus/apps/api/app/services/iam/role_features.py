"""The features roles brought become policies, once.

Before, each built-in role brought features: an older version computed
``builtin.features.<key>`` (``<role>``, ``<org>.<role>``, ``<org>.<ws>.<role>``)
from the deployment's ``feature_flags`` and the organizations' overlays, and IAM
attached the most specific one beside each role held at a workspace or
org-wide, at the role's own scope. No role brings a feature any more: a policy
does.

``migrate_role_features`` keeps every user's features exactly as they were,
from what IAM has in force, never from the configuration: the stored
``builtin.features.*`` and the roles held now.

* Each role held at a workspace becomes the workspace's policy "Features of
  <role>" attached there; a role held org-wide (``abi:<org>:*``) the
  organization's "Features of <role>" attached org-wide, so it still covers the
  organization's workspaces made later, as before. A group holding the role is
  given it like a person.
* Each workspace gets its "Features of <role>" for every role that had features
  there, held or not: what an invitation carries for a newcomer.
* A pending invitation to a role (IAM's pending grant) gets the matching pending
  grant beside it, and the Nexus invitation lists it, so the invitee still has
  the role's features at the first sign-in. An organization owner's or admin's
  gets the organization's, org-wide, where the role is mirrored.

The old policies stay in force until the move is recorded (``iam_migrations``,
``role_features_v1``); then they are retired (``IAMService.retire_policies``),
with their attachments, and the overlay table is dropped. Each step may run
again: a failure leaves the move unrecorded, nothing retired, and the next start
does it again. Afterwards the configuration's role features do nothing, and a
configuration that still sets them gets a warning at each start.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
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
# Recorded once the old policies are gone: later starts look no more.
RETIRED_NAME = "role_features_retired_v1"
# The move of the workspace feature overrides reads the role features and the
# overlay table this move drops: it runs first (``feature_overrides``).
AFTER = "workspace_feature_sets_v1"
OVERLAY_TABLE = "organization_role_features"
# The policies the older version generated: ``builtin.features.<key>``.
OLD_PREFIX = "builtin.features."
ROLE_NAMES = tuple(role.removeprefix("builtin.") for role in roles.ROLES)
# The organization roles Nexus mirrors org-wide (``Memberships.mirror_org_wide``).
ORG_WIDE_ROLES = ("owner", "admin")
# The settings that gave roles their features, read by the overrides' move only.
DEPRECATED_SETTINGS = ("role_baseline", "organization_overrides", "workspace_overrides")
_FEATURE = ":nexus:feature/"


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
    the org's stored overlay. Read by the move of the feature overrides only."""
    baseline = {role: list(features) for role, features in flags.role_baseline.items()}
    if organization_id:
        for role, features in (flags.organization_overrides.get(organization_id) or {}).items():
            baseline[role] = list(features)
    for role, features in (organization_override or {}).items():
        baseline[role] = list(features)
    return baseline


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


# -- what was in force ---------------------------------------------------------------


def stored_features(policies: Iterable[Any]) -> dict[str, tuple[str, ...]]:
    """``{key: features}`` of the stored ``builtin.features.<key>``: the features
    each allows (``${scope}:nexus:feature/<k>``), none for a key that overrode the
    broader ones with nothing."""
    found: dict[str, tuple[str, ...]] = {}
    for policy in policies:
        if not policy.id.startswith(OLD_PREFIX):
            continue
        features = {
            resource.split(_FEATURE, 1)[1]
            for statement in policy.document.statements
            if statement.effect == "Allow" and "nexus:UseFeature" in statement.actions
            for resource in statement.resources
            if _FEATURE in resource
        }
        found[policy.id.removeprefix(OLD_PREFIX)] = tuple(sorted(features))
    return found


def key_for(role: str, org: str, workspace: str, keys: Mapping[str, tuple[str, ...]]) -> str | None:
    """The key whose policy came with ``role`` at ``abi:<org>:<workspace>``: the
    most specific that exists (workspace, then org, then the deployment's), as
    the older IAM chose it."""
    candidates = [f"{org}.{workspace}.{role}"] if workspace not in ("*", "-") else []
    candidates += [f"{org}.{role}", role]
    return next((c for c in candidates if c in keys), None)


def _fields(scope: str) -> tuple[str, str]:
    _abi, org, workspace = scope.split(":", 2)
    return org, workspace


def owner_of(scope: str) -> str | None:
    """Who owns the policy that replaces a companion attached at ``scope``: the
    workspace, the organization for an org-wide scope, the platform (None) for
    one across organizations (which Nexus never makes)."""
    org, workspace = _fields(scope)
    if org == "*":
        return None
    if workspace == "*":
        return f"abi:{org}:-"
    return scope


@dataclass
class MoveReport:
    attached: int = 0
    policies: int = 0
    # pending role grant id -> (pending feature grant id, its policy id)
    carried: dict[str, tuple[str, str]] = field(default_factory=dict)
    # What could not be moved, named for the operator: the move goes on with
    # the rest, then is not recorded (nothing is retired) until a start moves all.
    failed: list[str] = field(default_factory=list)


class MoveIncomplete(RuntimeError):
    """Some of what the old policies grant could not be moved (``failed``)."""

    def __init__(self, failed: Sequence[str]) -> None:
        super().__init__(f"{len(failed)} item(s) of the role features were not moved")
        self.failed = list(failed)


def _step(report: MoveReport, what: str, step: Any) -> Any:
    """Run one step of the move; a failure is named and the move goes on."""
    try:
        return step()
    except Exception as exc:  # noqa: BLE001 - reported, and the move stays unrecorded
        _log.warning("The role features could not move %s: %s", what, exc)
        report.failed.append(f"{what}: {exc}")
        return None


class _Policies:
    """The "Features of <role>" of each owner: found (an earlier, interrupted
    run made it) or made, each owner's listed once."""

    def __init__(self, iam: Any) -> None:
        self._iam = iam
        self._known: dict[str | None, list[Any]] = {}
        self.made = 0

    def _of(self, owner: str | None) -> list[Any]:
        if owner not in self._known:
            found: list[Any] = []
            after: str | None = None
            while True:
                page = self._iam.list_policies(scope=owner, limit=200, after=after)
                # The platform: abi:-:- before container paths, abi: once made today.
                found += [
                    p
                    for p in page.items
                    if p.owner_scope == owner
                    or (owner is None and p.owner_scope in ("abi:-:-", "abi:"))
                ]
                after = page.next_after
                if after is None:
                    break
            self._known[owner] = found
        return self._known[owner]

    def get(self, owner: str | None, role: str, features: tuple[str, ...]) -> Any:
        name = policy_name(role)
        document = policy_document(features)
        known = self._of(owner)
        for policy in known:
            if policy.name == name and policy.document.statements == document.statements:
                return policy
        where = (
            "platform" if owner is None else "organization" if owner.endswith(":-") else "workspace"
        )
        made = self._iam.create_policy(
            name,
            document,
            description=(
                f"The features the {role} role brought in this {where} when roles stopped "
                "bringing any. Attach it to whoever should use them."
            ),
            scope=owner,
        )
        known.append(made)
        self.made += 1
        return made


def _features(role: str, scope: str, keys: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    org, workspace = _fields(scope)
    key = key_for(role, org, workspace, keys)
    return keys[key] if key is not None else ()


def _companion_scope(scope: str | None) -> str | None:
    """Where a role at ``scope`` brought features: a workspace or org-wide scope
    (neither field ``-``); an org-level role brought none."""
    if scope is None:
        return None
    return None if "-" in _fields(scope) else scope


def move(
    iam: Any,
    workspaces: Iterable[tuple[str, str | None]],
    keys: Mapping[str, tuple[str, ...]],
) -> MoveReport:
    """The move, as ``engine``, from ``keys`` (``stored_features``). Each step may
    run again: policies are found before they are made, attaching and pending
    grants are idempotent."""
    report = MoveReport()
    policies = _Policies(iam)
    # Every workspace's policies, held or not.
    for workspace, org_id in sorted(workspaces, key=lambda w: w[0]):
        org = org_id or NO_ORG
        scope = f"abi:{org}:{workspace}"

        def own(scope: str = scope) -> None:
            # Containers are registered when the names are rewritten
            # (``container_names``); IAM takes these owners from the engine.
            for role in ROLE_NAMES:
                features = _features(role, scope, keys)
                if features:
                    policies.get(scope, role, features)

        _step(report, f"the policies of workspace {scope}", own)
    # Who held a role brings its features where they held it.
    for role_policy in roles.ROLES:
        role = role_policy.removeprefix("builtin.")
        for attachment in iam.list_attachments(policy_id=role_policy):
            scope = _companion_scope(attachment.scope)
            if scope is None:
                continue
            features = _features(role, scope, keys)
            if not features:
                continue
            owner = owner_of(scope)

            def attach(
                owner: str | None = owner,
                role: str = role,
                features: tuple[str, ...] = features,
                principal_id: str = attachment.principal_id,
                scope: str = scope,
            ) -> bool:
                policy = policies.get(owner, role, features)
                iam.attach_policy(policy.id, principal_id, scope)
                return True

            what = f"{role_policy} of {attachment.principal_id} at {scope}"
            if _step(report, what, attach):
                report.attached += 1
    # Invitations still pending: their role's features come with them.
    for grant in iam.list_pending_grants():
        if grant.policy_id not in roles.ROLES or grant.scope is None:
            continue
        role = grant.policy_id.removeprefix("builtin.")
        org, workspace = _fields(grant.scope)
        if workspace == "-" and org not in ("-", "*") and role in ORG_WIDE_ROLES:
            scope: str | None = f"abi:{org}:*"  # mirrored org-wide at the claim
        else:
            scope = _companion_scope(grant.scope)
        if scope is None:
            continue
        features = _features(role, scope, keys)
        if not features:
            continue

        def carry(
            grant: Any = grant,
            role: str = role,
            features: tuple[str, ...] = features,
            scope: str = scope,
        ) -> tuple[str, str]:
            policy = policies.get(owner_of(scope), role, features)
            carried = iam.create_pending_grant(grant.provider, grant.email, policy.id, scope)
            return str(carried.id), str(policy.id)

        found = _step(
            report, f"pending grant {grant.id} ({grant.policy_id} at {grant.scope})", carry
        )
        if found is not None:
            report.carried[str(grant.id)] = found
    report.policies = policies.made
    if report.failed:
        raise MoveIncomplete(report.failed)
    return report


# -- the Nexus side ----------------------------------------------------------------


async def read_overlays(db: AsyncSession) -> dict[str, dict[str, list[str]]]:
    """The organizations' stored role features (``organization_role_features``);
    none once the table is gone. Read by the move of the feature overrides."""
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


async def recorded(db: AsyncSession, name: str) -> bool:
    """Whether ``iam_migrations`` records ``name`` (a start-up move done)."""
    found = (
        await db.execute(text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": name})
    ).first()
    return found is not None


async def _carry_into_invitations(db: AsyncSession, carried: Mapping[str, tuple[str, str]]) -> int:
    """List each carried pending grant on the Nexus invitation of its role's, so
    revoking or renewing the invitation withdraws it too."""
    if not carried:
        return 0
    changed = 0
    rows = (
        await db.execute(
            text("SELECT id, grant_ids, policy_ids FROM invitations WHERE status = 'pending'")
        )
    ).all()
    for invitation_id, raw_grants, raw_policies in rows:
        grants = list(json.loads(raw_grants or "[]"))
        policies = list(json.loads(raw_policies or "[]"))
        before = (len(grants), len(policies))
        for role_grant in list(grants):
            if str(role_grant) in carried:
                grant_id, policy_id = carried[str(role_grant)]
                if grant_id not in grants:
                    grants.append(grant_id)
                if policy_id not in policies:
                    policies.append(policy_id)
        if (len(grants), len(policies)) != before:
            await db.execute(
                text("UPDATE invitations SET grant_ids = :g, policy_ids = :p WHERE id = :i"),
                {"g": json.dumps(grants), "p": json.dumps(policies), "i": invitation_id},
            )
            changed += 1
    return changed


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


def _retire_old() -> tuple[list[str], list[str]]:
    """Retire what is left of the old policies (the move is recorded):
    ``(retired, kept)``. IAM keeps one that is the parent of a sub-policy,
    detached, until an administrator re-parents its sub-policies."""
    iam = runtime.iam()
    with as_service_account("engine"):
        old = [p.id for p in iam.retired_policies() if p.id.startswith(OLD_PREFIX)]
        retired = iam.retire_policies(old) if old else []
        return retired, [p for p in old if p not in retired]


async def _retire_and_record(db: AsyncSession) -> None:
    """Retire the old policies, then record that none is left, so later starts
    look no more. A failure is logged and tried again at the next start: they
    grant what the new ones do meanwhile."""
    try:
        retired, kept = await run_in_threadpool(_retire_old)
    except Exception:  # noqa: BLE001 - tried again at the next start
        _log.warning("The old role feature policies were not retired yet", exc_info=True)
        return
    if retired:
        _log.info("The old role feature policies were retired: %s", ", ".join(retired))
    if kept:
        # Detached, they grant nothing; each start tries again until they can go.
        _log.warning(
            "The old role feature policies %s are kept: each is a sub-policy's parent",
            ", ".join(kept),
        )
        return
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": RETIRED_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps({"retired": retired}),
        },
    )
    await db.commit()


async def migrate_role_features(db: AsyncSession, flags: FeatureFlagsConfig) -> int | None:
    """Move the features roles brought into policies, once (see the module).
    Returns the number of attachments made, None when it did not run: done
    already, or waiting for the move of the workspace feature overrides."""
    if await recorded(db, MIGRATION_NAME):
        warn_deprecated_settings(flags)
        # A start that recorded the move but failed to retire finishes here.
        if not await recorded(db, RETIRED_NAME):
            await _retire_and_record(db)
        return None
    if not await recorded(db, AFTER):
        _log.warning(
            "The role features wait for the workspace feature overrides to move: "
            "the next start tries again (the old ones stay in force meanwhile)"
        )
        return None
    rows = (await db.execute(text("SELECT id, organization_id FROM workspaces"))).all()
    workspaces = [(str(ws), str(org) if org else None) for ws, org in rows]

    def work() -> MoveReport:
        iam = runtime.iam()
        with as_service_account("engine"):
            keys = stored_features(iam.retired_policies())
            return move(iam, workspaces, keys)

    try:
        report = await run_in_threadpool(work)
    except MoveIncomplete as incomplete:
        _log.warning(
            "The role features were not all moved (%d item(s), listed above: clear "
            "them, or the next start tries again); the old policies stay in force",
            len(incomplete.failed),
        )
        return None
    except Exception:  # noqa: BLE001 - nothing is lost: the old policies stay in force
        _log.warning(
            "The role features were not moved: the old policies stay in force and "
            "the next start tries again",
            exc_info=True,
        )
        return None
    invitations = await _carry_into_invitations(db, report.carried)
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps(
                {
                    "workspaces": len(workspaces),
                    "policies": report.policies,
                    "attachments": report.attached,
                    "pending_grants": len(report.carried),
                    "invitations": invitations,
                }
            ),
        },
    )
    await db.execute(text(f"DROP TABLE IF EXISTS {OVERLAY_TABLE}"))
    await db.commit()
    # Recorded: the old policies go. A failure here is finished at the next start.
    await _retire_and_record(db)
    _log.info(
        "The features roles brought became policies: %d made, %d attachments, "
        "%d pending invitations",
        report.policies,
        report.attached,
        len(report.carried),
    )
    return report.attached


__all__ = [
    "AFTER",
    "DEPRECATED_SETTINGS",
    "MIGRATION_NAME",
    "MoveIncomplete",
    "MoveReport",
    "RETIRED_NAME",
    "key_for",
    "migrate_role_features",
    "move",
    "owner_of",
    "policy_document",
    "policy_name",
    "read_overlays",
    "recorded",
    "resolve_role_baseline",
    "stored_features",
    "warn_deprecated_settings",
]
