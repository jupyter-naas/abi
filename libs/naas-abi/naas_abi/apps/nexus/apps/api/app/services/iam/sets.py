"""Nexus and the organisation and workspace sets (core ``services/iam/sets.py``).

IAM keeps the sets and bounds every user's decision with them. Nexus

* reads the effective set of a workspace for what it shows that IAM does not
  decide one call at a time (the features a workspace offers its roles,
  ``effective_features``), and lists only what is in it (``within_set``: the
  agents, apps, workflows and pipelines a workspace lists, for everyone, the
  platform admin included);
* records the set of a workspace it creates, decided before the workspace
  exists (``plan_workspace_set``, then ``record_workspace_set``): its org's,
  narrowed by the features and the catalog seed chosen on the create form;
* moves the per-workspace feature overrides of earlier versions into IAM once
  (``migrate_feature_overrides``).

Edits made by people go through ``services/iam_admin`` as the signed-in user,
audited; what this module writes is part of an operation already authorized
(creating the workspace) or of the start-up migration, written as ``engine``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam import sets as core_sets
from naas_abi_core.services.iam.IAMPorts import ScopeSet
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)
T = TypeVar("T")

MIGRATION_NAME = "workspace_feature_sets_v1"
KEPT_FEATURES_POLICY = "Features kept from the workspace's overrides"


def _org(org_id: str | None) -> str:
    return org_id or NO_ORG


# -- reads ---------------------------------------------------------------------------


def effective_set(org_id: str | None, workspace_id: str | None = None) -> ScopeSet:
    """What an org (or a workspace in it) may use. Without an IAM at all (a route
    tested alone) nothing narrows; when IAM fails to answer, nothing is had: what
    is shown from it is never wider than IAM would say, and the failure is
    logged."""
    org = _org(org_id)
    workspace = workspace_id or "-"
    try:
        iam = runtime.iam()
    except runtime.IAMUnavailableError:
        return ScopeSet(org, workspace)
    try:
        with as_service_account("engine"):
            return iam.effective_set(org, workspace)
    except Exception:  # noqa: BLE001 - shown only: fail closed, never a 500
        _log.warning(
            "The set of %s/%s could not be read: shown as empty", org, workspace, exc_info=True
        )
        return ScopeSet(org, workspace, (), ())


def effective_features(
    org_id: str | None, workspace_id: str | None = None
) -> tuple[str, ...] | None:
    """The features a workspace's set (within its org's) has; None for every one."""
    return effective_set(org_id, workspace_id).features


async def effective_features_async(
    org_id: str | None, workspace_id: str | None = None
) -> tuple[str, ...] | None:
    return await run_in_threadpool(effective_features, org_id, workspace_id)


def in_set(scope_set: ScopeSet, scope: Any) -> bool:
    """Whether a module scope (``type``, ``module``, ``name``) is in ``scope_set``,
    by IAM's own rule (core ``sets.scope_within``)."""
    items = scope_set.modules
    if items is None:
        return True
    return core_sets.scope_within(items, scope.type, scope.module, scope.name)


async def workspace_set(workspace_id: str) -> ScopeSet:
    """The effective set of a workspace, its org found by ``AUTHZ``."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

    try:
        org = await AUTHZ.org_of(workspace_id)
    except runtime.IAMUnavailableError:
        return ScopeSet(NO_ORG, workspace_id)  # no IAM at all: nothing narrows
    if org is None:
        return ScopeSet(NO_ORG, workspace_id, (), ())
    return await run_in_threadpool(effective_set, None if org == NO_ORG else org, workspace_id)


async def within_set(
    items: Iterable[T], *, workspace: str, scope_of: Callable[[T], Any | None]
) -> list[T]:
    """The ``items`` whose module scope is in the workspace's set, in order; one
    with no module scope (``scope_of`` answers None: an agent the workspace
    built) is kept. What a workspace lists is its set, for everyone: IAM bounds
    the rest of its users with it already, not the platform admin."""
    found = list(items)
    scopes = [scope_of(item) for item in found]
    if not any(scopes):
        return found
    scope_set = await workspace_set(workspace)
    return [
        item
        for item, scope in zip(found, scopes, strict=True)
        if scope is None or in_set(scope_set, scope)
    ]


async def user_feature_flags(
    user: Any, workspaces: Sequence[tuple[str | None, str]], enabled: Collection[str]
) -> dict[str, dict[str, bool]] | None:
    """For each ``(org, workspace)``, whether ``user`` may use each feature there:
    IAM's ``nexus:UseFeature`` (role defaults, the sets, and any policy granting
    one), within the deployment's ``enabled`` features, in one ``filter``. None
    without IAM; when IAM fails to answer, every feature off (logged): the flags
    are only shown, the API decides each call again."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource
    from naas_abi_core.engine.call_context import use_call_context

    ctx = AUTHZ.context(user)
    keys = [key for key in KNOWN_FEATURE_KEYS if key in set(enabled)]
    names = {
        (workspace_id, key): nexus_resource(
            "feature", org=_org(org_id), workspace=workspace_id, id=key
        )
        for org_id, workspace_id in workspaces
        for key in keys
    }

    def run() -> dict[str, dict[str, bool]] | None:
        try:
            iam = runtime.iam()
        except runtime.IAMUnavailableError:
            return None  # the caller falls back to the roles' defaults
        try:
            with use_call_context(ctx):
                allowed = set(iam.filter("nexus:UseFeature", list(names.values())).allowed)
        except Exception:  # noqa: BLE001 - shown only: fail closed, never a 500
            _log.warning("Feature flags could not be read from IAM: shown off", exc_info=True)
            allowed = set()
        return {
            workspace_id: {
                key: names.get((workspace_id, key)) in allowed for key in KNOWN_FEATURE_KEYS
            }
            for _, workspace_id in workspaces
        }

    return await run_in_threadpool(run)


# -- a new workspace -------------------------------------------------------------------


def features_within(features: Iterable[str], org_set: ScopeSet) -> tuple[str, ...]:
    """``features`` its org's set has: what a workspace's feature set may record."""
    return tuple(
        sorted(f for f in set(features) if org_set.features is None or f in org_set.features)
    )


def put_features(iam: Any, org: str, workspace: str, features: Iterable[str]) -> ScopeSet:
    """Record ``features`` as a workspace's feature set, within its org's set: the
    modules it records stay, narrowed to its org's as IAM bounds them already
    (a set recorded before the org's narrowed would be refused as it is). For an
    import or a migration that may run after the platform admin narrowed the
    org; run as the engine."""
    org_set = iam.get_set(org)
    current = iam.get_set(org, workspace)
    modules = current.modules
    if modules is not None and org_set.modules is not None:
        modules = core_sets.intersect(org_set, current).modules
    return iam.put_set(org, workspace, modules=modules, features=features_within(features, org_set))


@dataclass(frozen=True)
class SeedItems:
    """The module scopes a catalog seed names: its agents and apps."""

    agents: frozenset[tuple[str, str]] | None  # (module, name); None: not seeded
    apps: frozenset[tuple[str, str]] | None


def narrowed_by_seed(modules: Sequence[str] | None, seed: SeedItems) -> tuple[str, ...] | None:
    """``modules`` (the org's items, None for every module) narrowed by the agents
    and apps a catalog seed names: those types become the seeded items the org
    has; every other type, and the actions modules declare, stay as the org has
    them. An org with no set keeps every module, installed now or later, for
    them (``<type>/*/*``, ``*:*``): nothing is a snapshot of what runs today. A
    seed that names neither returns ``modules`` as they are."""
    seeded = {"agent": seed.agents, "app": seed.apps}
    if all(chosen is None for chosen in seeded.values()):
        return tuple(modules) if modules is not None else None
    held = (
        tuple(modules)
        if modules is not None
        else (*(f"{t}/*/*" for t in module_scopes.TYPES), "*:*")
    )
    kept: set[str] = set()
    for item in held:
        parsed = core_sets.parse_item(item)
        if parsed.kind == "module":
            # The whole module: its types the seed leaves alone, its actions.
            kept.update(
                f"{t}/{parsed.module}/*" for t in module_scopes.TYPES if seeded.get(t) is None
            )
            try:
                kept.add(f"{module_scopes.module_service(parsed.module)}:*")
            except ValueError:
                pass  # no catalog name: it declares no action
        elif parsed.kind == "scope" and seeded.get(parsed.type) is not None:
            continue  # replaced by the seeded items within it, below
        else:
            kept.add(item)
    for type_name, chosen in seeded.items():
        for module, name in chosen or ():
            entry = f"{type_name}/{module}/{name}"
            if core_sets.within(held, entry):
                kept.add(entry)
    return tuple(sorted(kept))


def seed_items(catalog_seed: Mapping[str, Any] | None) -> SeedItems:
    """The module scopes of a catalog seed's agents and apps; a part the seed
    leaves out (``agents`` absent) is not narrowed."""
    if not catalog_seed:
        return SeedItems(None, None)
    apps: frozenset[tuple[str, str]] | None = None
    if catalog_seed.get("apps") is not None:
        from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope

        apps = frozenset(
            (scope.module, scope.name)
            for app_id in catalog_seed.get("apps") or ()
            if (scope := app_scope(str(app_id))) is not None
        )
    agents: frozenset[tuple[str, str]] | None = None
    if catalog_seed.get("agents") is not None:
        agents = _seeded_agents(catalog_seed.get("agents") or ())
    return SeedItems(agents, apps)


def _seeded_agents(refs: Iterable[Any]) -> frozenset[tuple[str, str]] | None:
    try:
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
            resolve_agent_ref,
        )
        from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
            agents__primary_adapter__FastAPI as agents_api,
        )
        from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import class_scope

        registry = agents_api._get_agent_class_registry()
        module_of = agents_api.agent_class_modules()
    except Exception:  # noqa: BLE001 - no agent registry: the seed does not narrow agents
        _log.warning("Catalog seed agents not resolved; agents not narrowed", exc_info=True)
        return None
    found: set[tuple[str, str]] = set()
    for ref in refs:
        key = resolve_agent_ref(str(ref), registry)
        if key is None:
            continue
        scope = class_scope(key, registry[key], module_of)
        if scope is not None:
            found.add((scope.module, scope.name))
    return frozenset(found)


async def plan_workspace_set(
    org_id: str | None,
    *,
    features: Collection[str] | None = None,
    catalog_seed: Mapping[str, Any] | None = None,
) -> ScopeSet | None:
    """The set a new workspace of ``org_id`` gets, decided before it exists (its
    ``workspace`` is ``-``): a part only where something narrows it,
    ``modules`` when its catalog seed names agents or apps (``narrowed_by_seed``
    of its org's), ``features`` when the create form chose them (within its
    org's). A part left unrecorded follows the org's, now and after the org's
    set changes; None when nothing narrows (nothing is recorded). Raises when
    IAM cannot answer, so nothing is created on a guess."""
    seed = seed_items(catalog_seed)
    narrows_modules = seed.agents is not None or seed.apps is not None
    if not narrows_modules and features is None:
        return None
    org = _org(org_id)

    def work() -> ScopeSet | None:
        iam = runtime.iam()
        with as_service_account("engine"):
            org_set = iam.get_set(org) if org_id else ScopeSet(org)
        modules = narrowed_by_seed(org_set.modules, seed) if narrows_modules else None
        chosen = features_within(features, org_set) if features is not None else None
        wanted = ScopeSet(org, "-", modules, chosen)
        return wanted if wanted.recorded else None

    return await run_in_threadpool(work)


async def record_workspace_set(workspace_id: str, planned: ScopeSet) -> ScopeSet:
    """Record ``planned`` (``plan_workspace_set``) as the set of ``workspace_id``.
    ``SetValidationError`` when its org's set narrowed in between."""

    def work() -> ScopeSet:
        with as_service_account("engine"):
            return runtime.iam().put_set(
                planned.org, workspace_id, modules=planned.modules, features=planned.features
            )

    return await run_in_threadpool(work)


# -- the migration of the feature overrides ------------------------------------------------


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
    """One workspace's move. Each step may run again: setting the set, finding
    the kept policy before making it, attaching what is attached."""
    scope = f"abi:{move.org}:{move.workspace}"
    # Org owners and admins hold their role org-wide.
    scopes = {scope, f"abi:{move.org}:*"}
    if move.features is not None:
        put_features(iam, move.org, move.workspace, move.features)
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
    else the deprecated ``feature_flags.workspace_overrides``) into IAM once: the
    workspace's feature set, and a workspace policy for the people whose role
    gained a feature through an override, so nobody's features change. Then the
    column is cleared. Recorded in ``iam_migrations``; returns the number
    of workspaces moved."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
        enabled_feature_catalog,
        parse_feature_overrides,
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
    overlays: dict[str, dict[str, list[str]]] = {}
    for org_id, raw in (
        await db.execute(
            text("SELECT organization_id, role_baseline FROM organization_role_features")
        )
    ).all():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            overlays[str(org_id)] = {str(k): list(v) for k, v in parsed.items()}
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
            "r": json.dumps({"workspaces": [m.workspace for m in moves]}),
        },
    )
    await db.commit()
    if moves:
        _log.info("Moved the feature overrides of %d workspaces into their sets", len(moves))
    return len(moves)


__all__ = [
    "KEPT_FEATURES_POLICY",
    "MIGRATION_NAME",
    "OverrideMove",
    "SeedItems",
    "effective_features",
    "effective_features_async",
    "effective_set",
    "features_within",
    "in_set",
    "migrate_feature_overrides",
    "narrowed_by_seed",
    "plan_override_moves",
    "plan_workspace_set",
    "put_features",
    "record_workspace_set",
    "seed_items",
    "user_feature_flags",
    "within_set",
    "workspace_set",
]
