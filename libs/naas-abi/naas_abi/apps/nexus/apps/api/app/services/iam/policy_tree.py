"""The sets and the on/off toggles become a tree of policies, once.

Before, three things decided whether a user used a module's agent, app, workflow,
pipeline or declared action, or a feature, in a workspace: the policies (and
the built-in admin and owner roles, which held every module scope at their
scope), the **sets** of the organisation and the workspace (IAM's, recorded by
the Modules & features pages), and what the workspace **turned off** (its apps
not turned on, its agents, workflows and pipelines turned off). Only policies
decide now. ``migrate_sets`` keeps every user's decision as it was:

* each organisation O gets a platform-owned policy "<O> access", its set's items
  and features (everything when it had no set), attached at ``abi:O:-`` to who
  held ``builtin.admin`` or ``builtin.owner`` there or org-wide;
* each workspace W of O gets "<W> access", a sub-policy of it owned by O, its
  own set's items and features, the apps it had turned on alone, and a Deny of
  the agents, workflows and pipelines it had turned off; attached at
  ``abi:O:W`` to who held ``builtin.admin`` or ``builtin.owner`` there, directly
  or org-wide (a group holding the role is given it like a person, and a pending
  invitation to the role gets it as a pending grant beside its own);
* a customer policy granting module scopes or features follows the same bounds:
  a workspace's policy becomes a sub-policy of its "<W> access", an
  organisation's of its "<O> access". Where that would not bound it as the sets
  and the toggles did (an organisation's policy attached in a workspace or
  org-wide, a platform policy attached anywhere), its attachment is replaced by
  one, at each workspace (and the organisation) it reached, of a sub-policy of
  that place's access policy holding the same statements. A policy that also
  grants something else (files, graphs, ...) or denies keeps that part, attached
  as before; its modules and features move to a sub-policy beside it;
* a service account was never bounded by a set: it gets the same grants without
  a parent.

What cannot be kept exactly stops the move, logged and named: nothing is
recorded, and Nexus refuses every module scope and feature until a start moves
everything (``pending``). The few things that change by construction are listed
in ``NOTES`` and written into the report.

The rows read once (IAM's legacy sets, ``app_configs.enabled``,
``agent_configs.enabled``, ``workflow_visibility``, ``workspaces.feature_overrides``
of an install that never ran the overrides' move) are read here and nowhere else.
Once the move is recorded (``iam_migrations``, ``MIGRATION_NAME``), IAM drops its
sets and ``workflow_visibility`` goes.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG
from naas_abi.apps.nexus.apps.api.app.services.iam.role_features import recorded
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.names import PLATFORM_SCOPE, encode_segment, matches
from naas_abi_core.services.iam.policy import (
    MAX_PATTERNS,
    MAX_STATEMENTS,
    PolicyDocument,
    Statement,
)
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "policy_tree_v1"
# The moves that come first: the workspace feature overrides (their features
# are part of the sets read here) and the role features (their old policies
# were bounded by the sets too; once moved they are detached, kept or not).
AFTER = ("workspace_feature_sets_v1", "role_features_v1")
OVERRIDES_MOVE = "workspace_feature_sets_v1"

FEATURE = ("nexus", "feature")
USE_FEATURE = "nexus:UseFeature"
ROLES_WITH_MODULES = (roles.ADMIN, roles.OWNER)
ANY = "*"

# What changes by construction, for the report and the owner's notes.
NOTES = (
    "The platform admin now reaches what a workspace had turned off (the toggles "
    "refused it to everyone, the platform admin included).",
    "Admins and owners of an organization no longer reach a workspace made after "
    "the upgrade by their role: a policy attached there, or attached org-wide after "
    "the upgrade, gives it.",
    "An agent a workspace built and had turned off is denied to whoever held a role "
    "there at the upgrade; someone given a role there later uses it: delete the "
    "agent, or deny it to them.",
    "A module installed after the upgrade is in no access policy: whoever "
    "administers the policies adds it.",
)

# Set while a start has an upgrade to finish: Nexus refuses every module scope
# and feature until it is recorded (never wider than before).
_pending = False


def pending() -> bool:
    """Whether the sets still wait to become policies (module scopes and
    features are refused meanwhile)."""
    return _pending


def set_pending(value: bool) -> None:
    global _pending
    _pending = value


class UpgradeStop(RuntimeError):
    """Something the move cannot keep exactly: nothing is recorded."""


# -- what the legacy sets said -------------------------------------------------------

_MODULE = re.compile(r"^[^\s/:]{1,200}$")
_DECLARED = re.compile(r"^([a-z][a-z0-9_]*|\*):([A-Z][A-Za-z0-9]*|\*)$")


@dataclass(frozen=True)
class Item:
    """One item of a set's ``modules``, as the sets wrote them: ``module`` (a
    whole module), ``scope`` (``<type>/<module>/<name>``, ``*`` for every name;
    ``<type>/*/*`` every one of that type), or ``action``
    (``<service>:<Action>``, ``<service>:*``, ``*:*``)."""

    kind: str
    module: str = ""
    type: str = ""
    name: str = ""
    service: str = ""
    action: str = ""


def parse_item(item: str) -> Item:
    declared = _DECLARED.match(item)
    if declared:
        return Item("action", service=declared.group(1), action=item)
    if "/" not in item:
        if not _MODULE.match(item):
            raise UpgradeStop(f"A set item is not one the sets recorded: {item!r}")
        return Item("module", module=item)
    type_name, _, rest = item.partition("/")
    module, _, name = rest.partition("/")
    if type_name not in module_scopes.TYPES or not module or not name:
        raise UpgradeStop(f"A set item is not one the sets recorded: {item!r}")
    return Item("scope", module=module, type=type_name, name=name)


def scope_within(items: Sequence[str], type_name: str, module: str, name: str) -> bool:
    """The sets' rule: an item of a module is in a set through itself, its whole
    module, or a wildcard of its type."""
    return (
        module in items
        or f"{type_name}/{module}/{name}" in items
        or f"{type_name}/{module}/{ANY}" in items
        or f"{type_name}/{ANY}/{ANY}" in items
    )


@dataclass(frozen=True)
class Legacy:
    """One org's or workspace's set: each part None for everything."""

    modules: tuple[str, ...] | None = None
    features: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TurnedOff:
    """What a workspace had turned off: every app but ``apps_on`` (an app was
    off until turned on, or its catalog seed turned it on), the agents of
    ``agents_off`` and the workflows and pipelines of ``processes_off``."""

    apps_on: frozenset[tuple[str, str]] = frozenset()
    agents_off: frozenset[tuple[str, str]] = frozenset()
    processes_off: frozenset[tuple[str, str, str]] = frozenset()
    # Agents the workspace built itself (no module) and had turned off.
    custom_off: frozenset[str] = frozenset()


# -- the statements of an access policy ---------------------------------------------


def _scope_pattern(type_name: str, module: str, name: str) -> str:
    """``${scope}:module:<type>/<module>/<name>``, ``*`` kept as a wildcard."""
    module_part = ANY if module == ANY else encode_segment(module)
    name_part = ANY if name == ANY else encode_segment(name)
    if module == ANY:
        return f"${{scope}}:module:{type_name}/*"
    return f"${{scope}}:module:{type_name}/{module_part}/{name_part}"


def _chunks(values: Sequence[str]) -> list[tuple[str, ...]]:
    return [tuple(values[i : i + MAX_PATTERNS]) for i in range(0, len(values), MAX_PATTERNS)]


def _allow(sid: str, actions: Sequence[str], resources: Sequence[str]) -> list[Statement]:
    found = sorted(dict.fromkeys(resources))
    return [
        Statement("Allow", tuple(actions), chunk, sid=sid if i == 0 else f"{sid}{i + 1}")
        for i, chunk in enumerate(_chunks(found))
    ]


def access_statements(
    scope_set: Legacy,
    declared: Mapping[str, str],
    *,
    turned_off: TurnedOff | None = None,
) -> list[Statement]:
    """What a set (and, for a workspace, what it turned off) lets through, as
    statements written at ``${scope}``. ``declared`` maps each catalog a module
    declares to its module."""
    modules = scope_set.modules
    patterns: list[str] = []
    apps: list[str] = []
    declared_actions: dict[str, set[str]] = {}
    every_type = dict.fromkeys(module_scopes.TYPES, modules is None)
    if modules is None:
        declared_actions = {service: {f"{service}:*"} for service in declared}
    else:
        for raw in modules:
            item = parse_item(raw)
            if item.kind == "module":
                for type_name in module_scopes.TYPES:
                    patterns.append(_scope_pattern(type_name, item.module, ANY))
                for service, module in declared.items():
                    if module == item.module:
                        declared_actions.setdefault(service, set()).add(f"{service}:*")
            elif item.kind == "scope":
                if item.module == ANY:
                    every_type[item.type] = True
                else:
                    patterns.append(_scope_pattern(item.type, item.module, item.name))
            elif item.service == ANY:
                for service in declared:
                    declared_actions.setdefault(service, set()).add(f"{service}:*")
            elif item.service in declared:
                declared_actions.setdefault(item.service, set()).add(item.action)
    for type_name, every in every_type.items():
        if every:
            patterns.append(f"${{scope}}:module:{type_name}/*")
    if turned_off is not None:
        # Apps were off until turned on: the workspace's are listed one by one.
        patterns = [p for p in patterns if not p.startswith("${scope}:module:app/")]
        apps = [
            _scope_pattern(module_scopes.APP, module, name)
            for module, name in sorted(turned_off.apps_on)
            if modules is None or scope_within(modules, module_scopes.APP, module, name)
        ]
    statements: list[Statement] = []
    statements += _allow("Modules", ["module:*"], patterns + apps)
    for service in sorted(declared_actions):
        actions = sorted(declared_actions[service])
        if f"{service}:*" in actions:
            actions = [f"{service}:*"]
        statements += _allow(f"Actions{_sid_part(service)}", actions, [f"${{scope}}:{service}:*"])
    features = scope_set.features
    if features is None:
        statements += _allow("Features", [USE_FEATURE], ["${scope}:nexus:feature/*"])
    else:
        statements += _allow(
            "Features",
            [USE_FEATURE],
            [f"${{scope}}:nexus:feature/{encode_segment(key)}" for key in features],
        )
    if turned_off is not None:
        statements += _turned_off(turned_off)
    if not any(s.effect == "Allow" for s in statements):
        # A set of nothing: a policy holds one statement at least, and refusing
        # every module scope and feature through it is what it says.
        statements.append(_nothing(declared))
    if len(statements) > MAX_STATEMENTS:
        raise UpgradeStop(f"A set needs {len(statements)} statements, past {MAX_STATEMENTS}")
    return statements


def _sid_part(service: str) -> str:
    return "".join(part.capitalize() for part in service.split("_"))


def _turned_off(turned_off: TurnedOff) -> list[Statement]:
    found: list[Statement] = []
    agents = [
        _scope_pattern(module_scopes.AGENT, module, name)
        for module, name in sorted(turned_off.agents_off)
    ]
    for i, chunk in enumerate(_chunks(agents)):
        found.append(
            Statement(
                "Deny",
                (f"module:{module_scopes.USE_ACTION[module_scopes.AGENT]}",),
                chunk,
                sid="TurnedOffAgents" if i == 0 else f"TurnedOffAgents{i + 1}",
            )
        )
    for type_name in (module_scopes.WORKFLOW, module_scopes.PIPELINE):
        off = [
            _scope_pattern(type_name, module, name)
            for kind, module, name in sorted(turned_off.processes_off)
            if kind == type_name
        ]
        for i, chunk in enumerate(_chunks(off)):
            sid = f"TurnedOff{type_name.capitalize()}s"
            found.append(
                Statement(
                    "Deny",
                    (f"module:{module_scopes.USE_ACTION[type_name]}",),
                    chunk,
                    sid=sid if i == 0 else f"{sid}{i + 1}",
                )
            )
    return found


def _nothing(declared: Mapping[str, str]) -> Statement:
    """An Allow no name matches (a module id holds no NUL): what a set of
    nothing lets through, as a parent. Not a Deny, which would refuse a
    service account holding such a grant through a group too."""
    return Statement(
        "Allow",
        ("module:UseAgent",),
        ("${scope}:module:agent/%00",),
        sid="Nothing",
    )


# -- which statements the sets bounded ---------------------------------------------------


@dataclass(frozen=True)
class Split:
    """An Allow statement split: ``bounded`` what the sets bounded (None: none),
    ``rest`` what they did not, and ``every_service`` when a wildcard of every
    service was spelled out in it (the bus and later services are left out)."""

    bounded: Statement | None
    rest: tuple[Statement, ...]
    every_service: bool = False


@dataclass(frozen=True)
class Bounds:
    """The actions the sets bounded: the ``module`` catalog's, every module's
    declared catalog's, and ``nexus:UseFeature``."""

    bounded: frozenset[str]
    other: frozenset[str]
    services: Mapping[str, frozenset[str]]  # service -> its actions

    @classmethod
    def of(cls, registry: CatalogRegistry) -> Bounds:
        bounded: set[str] = set()
        other: set[str] = set()
        services: dict[str, frozenset[str]] = {}
        for catalog in registry.all():
            module_scope = {t.name for t in catalog.resource_types if t.module_scope}
            if catalog.service == FEATURE[0]:
                module_scope.add(FEATURE[1])
            names: set[str] = set()
            for action in catalog.actions:
                qualified = catalog.qualified(action.name)
                names.add(qualified)
                types = set(action.resource_types)
                if types and types <= module_scope:
                    bounded.add(qualified)
                elif types & module_scope:
                    raise UpgradeStop(
                        f"{qualified} acts on module scopes and on other types: the "
                        "sets bounded part of it, which a policy cannot say"
                    )
                else:
                    other.add(qualified)
            services[catalog.service] = frozenset(names)
        return cls(frozenset(bounded), frozenset(other), services)

    def split(self, statement: Statement) -> Split:
        """An Allow statement as what the sets bounded and the rest: the first
        keeps the patterns that reach a bounded action (as written: the parent it
        moves under bounds it), the rest the actions that are not, a pattern that
        reaches both spelled out action by action (in as many statements as the
        patterns need, ``MAX_PATTERNS`` each)."""
        bounded_patterns: list[str] = []
        other_patterns: list[str] = []
        every_service = False
        for pattern in statement.actions:
            reached_bounded = sorted(a for a in self.bounded if matches(pattern, a))
            reached_other = sorted(a for a in self.other if matches(pattern, a))
            if reached_bounded:
                bounded_patterns.append(pattern)
                if reached_other:
                    other_patterns += self._spelled(pattern, reached_other)
                # A wildcard of the service reached the bus and the services
                # registered later too: spelled out, it no longer does.
                every_service |= any(c in pattern.partition(":")[0] for c in "*?")
            else:
                # Other actions, or a service no catalog registers: never bounded.
                other_patterns.append(pattern)
        bounded = (
            Statement("Allow", tuple(bounded_patterns), statement.resources, sid=statement.sid)
            if bounded_patterns
            else None
        )
        actions = list(dict.fromkeys(other_patterns))
        rest = [
            Statement(
                "Allow",
                chunk,
                statement.resources,
                sid=statement.sid if i == 0 or not statement.sid else f"{statement.sid}{i + 1}",
            )
            for i, chunk in enumerate(_chunks(actions))
        ]
        return Split(bounded, tuple(rest), every_service and bool(rest))

    def _spelled(self, pattern: str, reached: Sequence[str]) -> list[str]:
        """``reached`` as patterns: ``<service>:*`` for a service it reaches whole."""
        found: list[str] = []
        by_service: dict[str, list[str]] = {}
        for action in reached:
            by_service.setdefault(action.partition(":")[0], []).append(action)
        for service, actions in sorted(by_service.items()):
            if set(actions) == set(self.services.get(service, ())):
                found.append(f"{service}:*")
            else:
                found += actions
        return found


# -- glob derivatives: a pattern within one place ------------------------------------------


def within_place(pattern: str, prefix: str) -> list[str]:
    """What follows ``prefix`` in the names ``pattern`` matches that start with
    it, as patterns: ``abi:*:*:module:agent/*`` within ``abi:O:W:`` is
    ``module:agent/*``. Exact: the names ``pattern`` matches under ``prefix``
    are ``prefix`` followed by one of them."""

    @cache
    def derive(i: int, j: int) -> frozenset[str]:
        if j == len(prefix):
            return frozenset({pattern[i:]})
        if i == len(pattern):
            return frozenset()
        char = pattern[i]
        if char == "*":
            return derive(i, j + 1) | derive(i + 1, j)
        if char == "?" or char == prefix[j]:
            return derive(i + 1, j + 1)
        return frozenset()

    # What follows a place in a name is ``<service>:<type>/<id>``, one raw
    # ``:`` (ids are encoded): a rest that needs two names no resource.
    return sorted(p for p in derive(0, 0) if p.count(":") <= 1)


def place_prefix(org: str, workspace: str) -> str:
    return f"abi:{org}:{workspace}:"


def statements_at(
    statements: Iterable[Statement], scope: str | None, org: str, workspace: str
) -> list[Statement]:
    """``statements`` as attached at ``scope``, kept for the names of the place
    ``(org, workspace)`` and written at that place's own scope: an Allow keeps
    what it reaches there (``${scope}:<rest>``), a Deny is kept whole, its
    ``${scope}`` filled with ``scope`` when that is not the place's own."""
    own = f"abi:{org}:{workspace}"
    prefix = place_prefix(org, workspace)
    found: list[Statement] = []
    for statement in statements:
        resources: list[str] = []
        for resource in statement.resources:
            if (
                statement.effect == "Allow"
                and scope is not None
                and not resource.startswith("${scope}:")
            ):
                continue  # an Allow attached at a scope reaches only ${scope}:
            if scope == own:
                filled = resource
            elif "${scope}" in resource:
                if scope is None:
                    continue  # unscoped: it matches nothing
                filled = resource.replace("${scope}", scope)
            else:
                filled = resource
            if statement.effect == "Deny":
                resources.append(filled)
                continue
            if filled.startswith("${scope}:"):
                resources.append(filled)
                continue
            resources += [f"${{scope}}:{rest}" for rest in within_place(filled, prefix)]
        if resources:
            found.append(
                Statement(
                    statement.effect,
                    statement.actions,
                    tuple(dict.fromkeys(resources)),
                    sid=statement.sid,
                )
            )
    return found


# -- the plan ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Place:
    org: str
    workspace: str = "-"  # "-": the organization itself

    @property
    def scope(self) -> str:
        return f"abi:{self.org}:{self.workspace}"


@dataclass
class World:
    """What the move reads: the orgs and workspaces, their sets and toggles, the
    catalogs, and IAM's policies, attachments, pending grants and principals."""

    workspaces: Mapping[str, str]  # workspace -> its org (NO_ORG for none)
    org_names: Mapping[str, str]
    workspace_names: Mapping[str, str]
    sets: Mapping[tuple[str, str], Legacy]  # (org, workspace or "-")
    turned_off: Mapping[str, TurnedOff]
    registry: CatalogRegistry
    policies: Sequence[Any]
    attachments: Sequence[Any]
    pending: Sequence[Any]
    kinds: Mapping[str, str]  # principal -> user | group | service_account
    members: Mapping[str, Sequence[str]]  # group -> its static members

    def orgs(self) -> list[str]:
        return sorted({*self.org_names, *self.workspaces.values(), *(o for o, _ in self.sets)})

    def workspaces_of(self, org: str) -> list[str]:
        return sorted(ws for ws, o in self.workspaces.items() if o == org)

    def declared(self) -> dict[str, str]:
        return {c.service: c.module for c in self.registry.all() if c.module}


@dataclass(frozen=True)
class NewPolicy:
    """A policy the move makes (found again by owner, name and description)."""

    key: str
    name: str
    description: str
    owner: str  # scope
    parent: str | None  # key of a NewPolicy, or an existing policy id
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class Grant:
    """``policy`` (a NewPolicy key or a policy id) to ``principal`` at ``scope``;
    for a pending grant, ``principal`` is ``pending:<grant id>`` and the grant
    is made for the same invitee."""

    policy: str
    principal: str
    scope: str | None


@dataclass
class Plan:
    policies: dict[str, NewPolicy] = field(default_factory=dict)
    reparent: dict[str, str] = field(default_factory=dict)  # policy id -> NewPolicy key
    documents: dict[str, tuple[Statement, ...]] = field(default_factory=dict)
    grants: list[Grant] = field(default_factory=list)
    removed: list[Grant] = field(default_factory=list)  # attachments and pending grants
    # What cannot be kept exactly and changes for someone: the owner reads it.
    notes: list[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def add(self, policy: NewPolicy) -> str:
        self.policies.setdefault(policy.key, policy)
        return policy.key

    def grant(self, policy: str, principal: str, scope: str | None) -> None:
        found = Grant(policy, principal, scope)
        if found not in self.grants:
            self.grants.append(found)


def org_key(org: str) -> str:
    return f"org:{org}"


def workspace_key(org: str, workspace: str) -> str:
    return f"ws:{org}:{workspace}"


def plan(world: World) -> Plan:
    """The whole move, from what is in force (pure)."""
    result = Plan()
    declared = world.declared()
    bounds = Bounds.of(world.registry)
    for org in world.orgs():
        org_set = world.sets.get((org, "-"), Legacy())
        name = world.org_names.get(org) or ("Personal workspaces" if org == NO_ORG else org)
        result.add(
            NewPolicy(
                org_key(org),
                f"{name} access",
                f"What organization {org} uses: its modules and features, from its set "
                "before policies decided alone. Its workspaces' access policies are "
                "sub-policies of it." + MADE,
                PLATFORM_SCOPE,
                None,
                tuple(access_statements(org_set, declared)),
            )
        )
        for workspace in world.workspaces_of(org):
            own = world.sets.get((org, workspace), Legacy())
            result.add(
                NewPolicy(
                    workspace_key(org, workspace),
                    f"{world.workspace_names.get(workspace) or workspace} access",
                    f"What workspace {workspace} uses, within its organization's: its "
                    "modules and features from its set, the apps it had turned on, and "
                    "none of the agents, workflows and pipelines it had turned off." + MADE,
                    f"abi:{org}:-",
                    org_key(org),
                    tuple(
                        access_statements(
                            own,
                            declared,
                            turned_off=world.turned_off.get(workspace, TurnedOff()),
                        )
                    ),
                )
            )
    _roles(world, result)
    _customer_policies(world, result, bounds)
    _custom_agents(world, result)
    _prune(result)
    return result


def _prune(result: Plan) -> None:
    """Leave out what the move would make and nobody holds: a split part granted
    nowhere, its place covered by sub-policies of each place's access. The
    access policies stay, held or not: they are the tree."""
    while True:
        used = {g.policy for g in result.grants} | set(result.reparent.values())
        used |= {p.parent for p in result.policies.values() if p.parent}
        unused = [
            key
            for key in result.policies
            if key not in used and not key.startswith(("org:", "ws:"))
        ]
        if not unused:
            return
        for key in unused:
            del result.policies[key]


def _places(world: World, scope: str | None) -> list[Place]:
    """The places an attachment at ``scope`` reaches names of."""
    if scope is None:
        return [Place(org) for org in world.orgs()] + [
            Place(org, ws) for org in world.orgs() for ws in world.workspaces_of(org)
        ]
    _abi, org, workspace = scope.split(":", 2)
    if org == "-":
        return []
    if workspace == "*":
        return [Place(org)] + [Place(org, ws) for ws in world.workspaces_of(org)]
    return [Place(org, workspace)]


def _node(place: Place) -> str:
    return (
        org_key(place.org) if place.workspace == "-" else workspace_key(place.org, place.workspace)
    )


def _known(world: World, place: Place) -> bool:
    return place.org in world.orgs() and (
        place.workspace == "-" or world.workspaces.get(place.workspace) == place.org
    )


def _grantees(world: World) -> list[tuple[str, str | None, str]]:
    """``(policy, scope, principal)`` of every attachment and pending grant."""
    found = [(a.policy_id, a.scope, a.principal_id) for a in world.attachments]
    found += [(g.policy_id, g.scope, f"pending:{g.id}") for g in world.pending]
    return found


def _service_accounts(world: World, principal: str) -> list[str]:
    """The service accounts a grant to ``principal`` reaches: itself, or a
    group's static members that are."""
    if world.kinds.get(principal) == "service_account":
        return [principal]
    if world.kinds.get(principal) == "group":
        return [
            m for m in world.members.get(principal, ()) if world.kinds.get(m) == "service_account"
        ]
    return []


def _roles(world: World, result: Plan) -> None:
    """Who held ``builtin.admin`` or ``builtin.owner`` gets, at each place the
    role reached, the module scopes of that place's access policy: a sub-policy
    of it granting every module scope, so within it (the role never brought a
    feature, so the access policy itself, which bounds features too, is not
    theirs). A service account, never bounded by a set, gets every module scope
    there, within what the workspace had turned off (``_for_accounts``)."""
    held: dict[str, str] = {}

    def of_roles(place: Place) -> str:
        node = _node(place)
        if node not in held:
            access = result.policies[node]
            held[node] = result.add(
                NewPolicy(
                    f"roles:{node}",
                    f"{access.name.removesuffix(' access')} modules (admins and owners)",
                    f"The modules {place.scope} uses, within its access: what its admins "
                    "and owners held by their role before no role held a module scope." + MADE,
                    f"abi:{place.org}:-",
                    node,
                    tuple(_every_module_scope(world)),
                )
            )
        return held[node]

    for policy_id, scope, principal in _grantees(world):
        if policy_id not in ROLES_WITH_MODULES or scope is None:
            continue
        reached = scope
        if principal.startswith("pending:") and scope.endswith(":-"):
            # An invited org owner or admin holds the role org-wide once signed
            # in (Nexus mirrors it): the workspaces too.
            reached = scope[: -len("-")] + "*"
        if world.kinds.get(principal) != "service_account":
            for place in _places(world, reached):
                if _known(world, place):
                    result.grant(of_roles(place), principal, place.scope)
        accounts = _service_accounts(world, principal)
        if accounts:
            _for_accounts(
                world,
                result,
                "roles",
                "Module scopes of an admin or owner role",
                _every_module_scope(world),
                reached,
                accounts,
            )


def _every_module_scope(world: World) -> list[Statement]:
    found: list[Statement] = []
    for catalog in world.registry.all():
        types = [t.name for t in catalog.resource_types if t.module_scope]
        if not types:
            continue
        found += _allow(
            f"Scopes{_sid_part(catalog.service)}",
            [f"{catalog.service}:*"],
            [f"${{scope}}:{catalog.service}:{t}/*" for t in types],
        )
    return found


def _customer_policies(world: World, result: Plan, bounds: Bounds) -> None:
    tree = {p.id for p in world.policies if made_by_move(p)}
    held: dict[str, list[tuple[str | None, str]]] = {}
    for policy_id, scope, principal in _grantees(world):
        held.setdefault(policy_id, []).append((scope, principal))
    for policy in world.policies:
        if policy.id in tree:
            continue
        if policy.managed:
            _check_managed(world, policy, bounds, held.get(policy.id, []))
            continue
        allows = [s for s in policy.document.statements if s.effect == "Allow"]
        denies = [s for s in policy.document.statements if s.effect == "Deny"]
        parts = [bounds.split(s) for s in allows]
        bounded = [part.bounded for part in parts if part.bounded is not None]
        if not bounded:
            continue  # the sets never bounded it
        if policy.parent_id and policy.parent_id not in tree:
            raise UpgradeStop(
                f"Policy {policy.id} ({policy.name}) is a sub-policy granting module "
                "scopes or features: give it no parent (or delete it) and start again"
            )
        rest = [o for part in parts for o in part.rest] + denies
        if any(part.every_service for part in parts):
            result.note(
                f"{policy.name} ({policy.id}): its wildcard of every service now names "
                "each action of the services registered at the upgrade (its modules and "
                "features moved beside it): the bus, and a service registered later, "
                "are not in it any more."
            )
        whole = not rest  # it grants module scopes and features alone
        owner = policy.owner_scope
        owner_place = _owner_place(owner)
        if owner_place is not None and not _known(world, owner_place):
            raise UpgradeStop(
                f"Policy {policy.id} ({policy.name}) is owned by {owner}, which Nexus "
                "does not know: delete it or its scope first"
            )
        # Where it stays bounded as before: an owned policy at its owner's
        # place, under that place's access; a platform policy at the platform's
        # own scope, which no set bounded.
        moved = policy.id
        if whole and owner_place is not None:
            result.reparent[policy.id] = _node(owner_place)
        elif not whole:
            moved = result.add(
                NewPolicy(
                    f"split:{policy.id}",
                    f"{policy.name}: modules and features",
                    f"The modules and features {policy.id} granted, beside it"
                    + (f", within {owner_place.scope}'s access." if owner_place else ".")
                    + MADE,
                    owner,
                    _node(owner_place) if owner_place is not None else None,
                    tuple(bounded),
                )
            )
        if not whole:
            result.documents[policy.id] = tuple(rest)
        for scope, principal in held.get(policy.id, []):
            _move_grant(world, result, policy, bounded, rest, moved, owner_place, scope, principal)


def _owner_place(owner: str) -> Place | None:
    if owner == PLATFORM_SCOPE:
        return None
    _abi, org, workspace = owner.split(":", 2)
    return Place(org, workspace)


def _move_grant(
    world: World,
    result: Plan,
    policy: Any,
    bounded: Sequence[Statement],
    rest: Sequence[Statement],
    moved: str,
    owner_place: Place | None,
    scope: str | None,
    principal: str,
) -> None:
    """One attachment (or pending grant) of a policy the sets bounded. ``moved``
    is what holds its modules and features where they stay bounded as before:
    the policy itself, or the sub-policy split from it."""
    whole = not rest
    accounts = _service_accounts(world, principal)
    if accounts:
        _for_accounts(world, result, policy.id, policy.name, bounded, scope, accounts)
        if world.kinds.get(principal) == "service_account":
            if whole:
                result.removed.append(Grant(policy.id, principal, scope))
            return
    exact = (owner_place is not None and scope == owner_place.scope) or (
        owner_place is None and scope == PLATFORM_SCOPE
    )
    if exact:
        if moved != policy.id:
            result.grant(moved, principal, scope)
        return
    if scope is None and _reaches_platform(bounded):
        # The platform's own names, which no set bounded.
        platform = result.add(
            NewPolicy(
                f"platform:{policy.id}",
                f"{policy.name}: platform",
                f"The modules and features {policy.id} grants at the platform level, "
                "which no set bounded." + MADE,
                PLATFORM_SCOPE,
                None,
                tuple(_platform_level(bounded)),
            )
        )
        result.grant(platform, principal, None)
    if scope is None or scope.endswith(":*"):
        result.note(
            f"{policy.name} ({policy.id}), attached "
            + (f"org-wide ({scope})" if scope else "with no scope")
            + f" to {principal}, now reaches the module scopes and features of the "
            "workspaces that existed at the upgrade only: attach it again for a "
            "workspace made later."
        )
    for place in _places(world, scope):
        if not _known(world, place):
            continue
        statements = statements_at(bounded, scope, place.org, place.workspace)
        if not statements:
            continue
        key = result.add(
            NewPolicy(
                f"at:{policy.id}:{scope}:{place.scope}",
                policy.name,
                f"What {policy.id}, attached at {scope or 'no scope'}, granted in "
                f"{place.scope}: its modules and features within that place's access." + MADE,
                place.scope,
                _node(place),
                tuple(statements),
            )
        )
        result.grant(key, principal, place.scope)
    if whole:
        result.removed.append(Grant(policy.id, principal, scope))


def _for_accounts(
    world: World,
    result: Plan,
    source: str,
    name: str,
    statements: Sequence[Statement],
    scope: str | None,
    accounts: Sequence[str],
) -> None:
    """``statements``, granted at ``scope``, for service accounts: never bounded
    by a set, but refused, as everyone was, what a workspace had turned off. So
    at each place the grant reached, a copy cut to that place: in a workspace a
    sub-policy of its "turned off" policy (``_turned_off_parent``), at the
    organization's own scope or the platform's one with no parent."""
    if scope == PLATFORM_SCOPE or (scope is None and _reaches_platform(statements)):
        own = list(statements) if scope == PLATFORM_SCOPE else _platform_level(statements)
        key = result.add(
            NewPolicy(
                f"sa:{source}:{scope}:platform",
                f"{name} (service accounts)",
                f"What {source}, attached at {scope or 'no scope'}, granted service "
                "accounts at the platform level, which no set bounded." + MADE,
                PLATFORM_SCOPE,
                None,
                tuple(own),
            )
        )
        for account in accounts:
            result.grant(key, account, scope)
    for place in _places(world, scope):
        if not _known(world, place):
            continue
        cut = statements_at(statements, scope, place.org, place.workspace)
        if not cut:
            continue
        parent = _turned_off_parent(world, result, place) if place.workspace != "-" else None
        key = result.add(
            NewPolicy(
                f"sa:{source}:{scope}:{place.scope}",
                f"{name} (service accounts)",
                f"What {source}, attached at {scope or 'no scope'}, granted service "
                f"accounts in {place.scope}: no set bounded them, what the workspace "
                "had turned off did." + MADE,
                f"abi:{place.org}:-",
                parent,
                tuple(cut),
            )
        )
        for account in accounts:
            result.grant(key, account, place.scope)


def _turned_off_parent(world: World, result: Plan, place: Place) -> str:
    """A workspace's toggles alone, as a parent: every module scope and feature,
    the apps it had turned on, none of what it had turned off."""
    return result.add(
        NewPolicy(
            f"off:{place.org}:{place.workspace}",
            f"{world.workspace_names.get(place.workspace) or place.workspace} toggles "
            "(service accounts)",
            f"What workspace {place.workspace} had not turned off, for the service "
            "accounts that use it: no set bounded them." + MADE,
            f"abi:{place.org}:-",
            None,
            tuple(
                access_statements(
                    Legacy(),
                    world.declared(),
                    turned_off=world.turned_off.get(place.workspace, TurnedOff()),
                )
            ),
        )
    )


def _custom_agents(world: World, result: Plan) -> None:
    """The agents a workspace built itself and had turned off (``nexus:UseAgent``
    on ``nexus:agent/<id>``): a Deny attached at the workspace to whoever held a
    role there (directly, through a group, org-wide, invited): the toggle
    refused them to everyone."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    for workspace, off in sorted(world.turned_off.items()):
        if not off.custom_off:
            continue
        org = world.workspaces[workspace]
        scope = f"abi:{org}:{workspace}"
        resources = [
            "${scope}:"
            + nexus_resource("agent", org=org, workspace=workspace, id=agent).removeprefix(
                f"{scope}:"
            )
            for agent in sorted(off.custom_off)
        ]
        key = result.add(
            NewPolicy(
                f"custom:{org}:{workspace}",
                f"Agents turned off in {world.workspace_names.get(workspace) or workspace}",
                f"The agents workspace {workspace} built itself and had turned off, "
                "denied to who held a role there." + MADE,
                scope,
                None,
                tuple(
                    Statement("Deny", ("nexus:UseAgent",), chunk, sid="TurnedOffAgents")
                    for chunk in _chunks(resources)
                ),
            )
        )
        for policy_id, held_at, principal in _grantees(world):
            if policy_id not in roles.ROLES or held_at is None:
                continue
            org_level = held_at == f"abi:{org}:-" and principal.startswith("pending:")
            if held_at in (scope, f"abi:{org}:*") or (
                org_level and policy_id in ROLES_WITH_MODULES
            ):
                result.grant(key, principal, scope)


def _check_managed(
    world: World, policy: Any, bounds: Bounds, held: Sequence[tuple[str | None, str]]
) -> None:
    """A managed policy the sets bounded for a user: only the roles (moved
    above) and the platform admin's (never bounded) may be one."""
    if policy.id in (*roles.ROLES, roles.PLATFORM_ADMIN):
        return
    users = [
        principal
        for _, principal in held
        if principal.startswith("pending:") or world.kinds.get(principal) != "service_account"
    ]
    if policy.id == roles.SELF:
        users = ["everyone"]
    if users and any(
        bounds.split(s).bounded is not None
        for s in policy.document.statements
        if s.effect == "Allow"
    ):
        raise UpgradeStop(
            f"Managed policy {policy.id} grants module scopes or features to users: "
            "the sets bounded it, nothing would any more"
        )


def _reaches_platform(statements: Sequence[Statement]) -> bool:
    return any(
        within_place(r, place_prefix("-", "-"))
        for s in statements
        for r in s.resources
        if "${scope}" not in r
    )


def _platform_level(statements: Sequence[Statement]) -> list[Statement]:
    """Unscoped ``statements`` kept for the platform's own names (``abi:-:-:...``)."""
    found: list[Statement] = []
    for statement in statements:
        resources = [
            f"{PLATFORM_SCOPE}:{rest}"
            for r in statement.resources
            if "${scope}" not in r
            for rest in within_place(r, place_prefix("-", "-"))
        ]
        if resources:
            found.append(
                Statement(statement.effect, statement.actions, tuple(resources), sid=statement.sid)
            )
    return found


# Every policy the move makes says so: a later start finds it again, and never
# moves it as a customer policy.
MADE = " (Made when the sets and the workspace toggles became policies.)"


def made_by_move(policy: Any) -> bool:
    return str(policy.description or "").endswith(MADE)


# -- applying it ---------------------------------------------------------------------------


@dataclass
class Report:
    policies: int = 0
    reparented: int = 0
    rewritten: int = 0
    granted: int = 0
    removed: int = 0
    carried: dict[str, list[str]] = field(default_factory=dict)  # old grant -> new grants
    notes: tuple[str, ...] = NOTES


def apply(iam: Any, world: World, steps: Plan) -> Report:
    """Make the plan true; every step may run again (policies are found by
    owner, name, description and statements before they are made; attaching
    what is attached grants nothing new). Run as the engine."""
    report = Report(notes=(*NOTES, *steps.notes))
    made: dict[str, str] = {}
    existing = {(p.owner_scope, p.name, p.description): p for p in world.policies}
    for key in _ordered(steps.policies):
        spec = steps.policies[key]
        parent = made.get(spec.parent, spec.parent) if spec.parent else None
        document = PolicyDocument(statements=spec.statements)
        found = existing.get((spec.owner, spec.name, spec.description))
        if found is not None:
            if found.document.statements != spec.statements or (found.parent_id or None) != parent:
                found = iam.update_policy(
                    found.id,
                    expected_revision=found.revision,
                    document=document,
                    parent=parent or "",
                )
            made[key] = found.id
            continue
        created = iam.create_policy(
            spec.name,
            document,
            description=spec.description,
            scope=None if spec.owner == PLATFORM_SCOPE else spec.owner,
            parent=parent,
        )
        made[key] = created.id
        report.policies += 1
    for policy_id, key in sorted(steps.reparent.items()):
        policy = iam.get_policy(policy_id)
        if policy.parent_id != made[key]:
            iam.update_policy(policy_id, expected_revision=policy.revision, parent=made[key])
            report.reparented += 1
    pending = {g.id: g for g in world.pending}
    for grant in steps.grants:
        policy_id = made.get(grant.policy, grant.policy)
        if grant.principal.startswith("pending:"):
            old = pending[grant.principal.removeprefix("pending:")]
            new = _pending_grant(iam, old, policy_id, grant.scope)
            report.carried.setdefault(old.id, []).append(new)
        else:
            iam.attach_policy(policy_id, grant.principal, grant.scope)
        report.granted += 1
    for grant in steps.removed:
        if grant.principal.startswith("pending:"):
            if iam.revoke_pending_grant(grant.principal.removeprefix("pending:")):
                report.removed += 1
        elif iam.detach_policy(grant.policy, grant.principal, grant.scope):
            report.removed += 1
    for policy_id, statements in sorted(steps.documents.items()):
        # Last: until here the policy still grants what moved, so a start that
        # fails before finds it whole and plans the same move again.
        current = iam.get_policy(policy_id)
        if current.document.statements != statements:
            iam.update_policy(
                policy_id,
                expected_revision=current.revision,
                document=PolicyDocument(statements=statements),
            )
            report.rewritten += 1
    return report


def _ordered(policies: Mapping[str, NewPolicy]) -> list[str]:
    """Parents before their sub-policies."""
    done: list[str] = []

    def visit(key: str) -> None:
        if key in done:
            return
        parent = policies[key].parent
        if parent in policies:
            visit(parent)
        done.append(key)

    for key in sorted(policies):
        visit(key)
    return done


def _pending_grant(iam: Any, old: Any, policy_id: str, scope: str | None) -> str:
    for found in iam.list_pending_grants(provider=old.provider, email=old.email):
        if found.policy_id == policy_id and found.scope == scope:
            return str(found.id)
    return str(iam.create_pending_grant(old.provider, old.email, policy_id, scope).id)


# -- reading what is in force ------------------------------------------------------------


async def _has_table(db: AsyncSession, name: str) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: inspect(sync).has_table(name))


async def _has_column(db: AsyncSession, table: str, column: str) -> bool:
    connection = await db.connection()

    def check(sync: Any) -> bool:
        found = inspect(sync)
        return found.has_table(table) and column in {c["name"] for c in found.get_columns(table)}

    return await connection.run_sync(check)


async def read_nexus(db: AsyncSession) -> dict[str, Any]:
    """What Nexus holds of the toggles, its orgs and workspaces, and the feature
    sets the overrides' move kept in its report (an install that moved them with
    this version: an older one put them in IAM's sets)."""
    orgs = {
        str(org_id): str(name or org_id)
        for org_id, name in (await db.execute(text("SELECT id, name FROM organizations"))).all()
    }
    workspaces: dict[str, str] = {}
    names: dict[str, str] = {}
    slugs: dict[str, str | None] = {}
    seeds: dict[str, Any] = {}
    for workspace_id, org_id, name, slug, seed in (
        await db.execute(
            text("SELECT id, organization_id, name, slug, catalog_seed FROM workspaces")
        )
    ).all():
        workspace_id = str(workspace_id)
        workspaces[workspace_id] = str(org_id) if org_id else NO_ORG
        names[workspace_id] = str(name or workspace_id)
        slugs[workspace_id] = slug
        seeds[workspace_id] = seed
    raw = (
        await db.execute(
            text("SELECT report FROM iam_migrations WHERE name = :n"), {"n": OVERRIDES_MOVE}
        )
    ).scalar()
    overrides = {
        str(ws): [str(k) for k in features]
        for ws, features in (json.loads(raw or "{}").get("feature_sets") or {}).items()
        if str(ws) in workspaces
    }
    return {
        "orgs": orgs,
        "workspaces": workspaces,
        "names": names,
        "turned_off": await _turned_off_rows(db, workspaces, slugs, seeds),
        "overrides": overrides,
    }


async def _turned_off_rows(
    db: AsyncSession,
    workspaces: Mapping[str, str],
    slugs: Mapping[str, str | None],
    seeds: Mapping[str, Any],
) -> dict[str, TurnedOff]:
    """Each workspace's toggles, as the old visibility read them."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
        effective_seed_apps,
        parse_catalog_seed,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.scopes import app_scope

    states: dict[str, dict[str, bool]] = {}
    if await _has_column(db, "app_configs", "enabled"):
        for workspace_id, app_id, enabled in (
            await db.execute(text("SELECT workspace_id, app_id, enabled FROM app_configs"))
        ).all():
            states.setdefault(str(workspace_id), {})[str(app_id)] = bool(enabled)
    agent_rows: dict[str, list[tuple[str, str | None, bool]]] = {}
    custom_off: dict[str, set[str]] = {}
    if await _has_column(db, "agent_configs", "enabled"):
        for agent_id, workspace_id, class_name, provider, enabled in (
            await db.execute(
                text("SELECT id, workspace_id, class_name, provider, enabled FROM agent_configs")
            )
        ).all():
            if class_name is None:
                # An agent the workspace built itself: turned off, refused to all.
                if not enabled:
                    custom_off.setdefault(str(workspace_id), set()).add(str(agent_id))
                continue
            agent_rows.setdefault(str(workspace_id), []).append(
                (str(class_name), provider, bool(enabled))
            )
    processes: dict[str, set[tuple[str, str, str]]] = {}
    if await _has_table(db, "workflow_visibility"):
        for workspace_id, type_name, module_id, name, enabled in (
            await db.execute(
                text("SELECT workspace_id, type, module_id, name, enabled FROM workflow_visibility")
            )
        ).all():
            if not enabled:
                processes.setdefault(str(workspace_id), set()).add(
                    (str(type_name), str(module_id), str(name))
                )
    resolve = _agent_resolver() if agent_rows else None
    found: dict[str, TurnedOff] = {}
    for workspace_id in workspaces:
        raw = seeds.get(workspace_id)
        seed = raw if isinstance(raw, dict) or raw is None else parse_catalog_seed(raw)
        seeded = effective_seed_apps(slugs.get(workspace_id), seed)
        stored = states.get(workspace_id, {})
        apps_on = {
            (scope.module, scope.name)
            for app_id in {*stored, *seeded}
            if (stored[app_id] if app_id in stored else app_id in seeded)
            and (scope := app_scope(app_id)) is not None
        }
        shown: dict[tuple[str, str], bool] = {}
        for class_name, provider, enabled in agent_rows.get(workspace_id, []):
            scope = (
                resolve(class_name, provider, strict=not enabled) if resolve is not None else None
            )
            if scope is not None:
                key = (scope.module, scope.name)
                shown[key] = shown.get(key, False) or enabled
        found[workspace_id] = TurnedOff(
            frozenset(apps_on),
            frozenset(key for key, on in shown.items() if not on),
            frozenset(processes.get(workspace_id, set())),
            frozenset(custom_off.get(workspace_id, set())),
        )
    return found


def _agent_resolver() -> Any:
    """``(class_name, provider)`` to the agent's module scope, as the roster
    resolved it; raises when the engine's agents cannot be read (the move waits:
    an agent turned off must stay off). A turned-off engine agent whose class the
    engine did not load (``strict``) stops the move: its scope would be guessed
    from its Python path, and a Deny under a wrong name refuses nothing once its
    module loads again."""
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary import (
        agents__primary_adapter__FastAPI as agents_api,
    )
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import REMOTE_PROVIDER
    from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import agent_scope

    classes = agents_api._get_agent_class_registry()
    module_of = agents_api.agent_class_modules()

    def resolve(class_name: str, provider: str | None, *, strict: bool = False) -> Any:
        if strict and provider != REMOTE_PROVIDER and class_name not in classes:
            raise UpgradeStop(
                f"The agent {class_name}, turned off in a workspace, is of a module the "
                "engine did not load: load the module, or delete the agent's row, and "
                "start again"
            )
        return agent_scope(
            SimpleNamespace(class_name=class_name, provider=provider), classes, module_of
        )

    return resolve


def read_iam(iam: Any) -> dict[str, Any]:
    """What IAM holds, read as the engine."""
    policies: list[Any] = []
    after: str | None = None
    while True:
        page = iam.list_policies(limit=500, after=after)
        policies += page.items
        after = page.next_after
        if after is None:
            break
    attachments = iam.list_attachments()
    pending = iam.list_pending_grants()
    principals = {a.principal_id for a in attachments}
    kinds: dict[str, str] = {}
    members: dict[str, list[str]] = {}
    for principal_id in sorted(principals):
        try:
            record = iam.get_principal(principal_id)
        except Exception:  # noqa: BLE001 - a stale attachment: no kind, treated as a user
            continue
        kinds[principal_id] = record.kind
        if record.kind == "group":
            members[principal_id] = list(iam.list_group_members(principal_id))
            for member in members[principal_id]:
                if member not in kinds:
                    try:
                        kinds[member] = iam.get_principal(member).kind
                    except Exception:  # noqa: BLE001
                        continue
    sets = {
        (found.org, found.workspace): Legacy(found.modules, found.features)
        for found in iam.legacy_scope_sets()
    }
    return {
        "policies": policies,
        "attachments": attachments,
        "pending": pending,
        "kinds": kinds,
        "members": members,
        "sets": sets,
        "registry": iam.catalogs,
    }


def build_world(nexus: Mapping[str, Any], held: Mapping[str, Any]) -> World:
    sets = dict(held["sets"])
    for workspace_id, features in nexus["overrides"].items():
        org = nexus["workspaces"][workspace_id]
        current = sets.get((org, workspace_id), Legacy())
        if current.features is None:
            sets[(org, workspace_id)] = Legacy(current.modules, tuple(features))
    return World(
        workspaces=nexus["workspaces"],
        org_names=nexus["orgs"],
        workspace_names=nexus["names"],
        sets=sets,
        turned_off=nexus["turned_off"],
        registry=held["registry"],
        policies=held["policies"],
        attachments=held["attachments"],
        pending=held["pending"],
        kinds=held["kinds"],
        members=held["members"],
    )


async def migrate_sets(db: AsyncSession) -> Report | None:
    """Turn the sets and the toggles into policies, once (see the module).
    Returns the report, None when it did not run (done already, or waiting for
    the moves before it). ``pending()`` stays true until it is recorded."""
    if await recorded(db, MIGRATION_NAME):
        set_pending(False)
        await _drop_what_was_read(db)
        return None
    set_pending(True)
    for before in AFTER:
        if not await recorded(db, before):
            _log.warning(
                "The sets wait for %s: module scopes and features are refused until "
                "a start moves them",
                before,
            )
            return None

    def work(nexus: Mapping[str, Any]) -> Report:
        iam = runtime.iam()
        with as_service_account("engine"):
            world = build_world(nexus, read_iam(iam))
            return apply(iam, world, plan(world))

    try:
        report = await run_in_threadpool(work, await read_nexus(db))
    except UpgradeStop as stop:
        _log.error(
            "The sets were not moved into policies: %s. Module scopes and features are "
            "refused until a start moves them.",
            stop,
        )
        return None
    except Exception:  # noqa: BLE001 - nothing recorded: refused until the next start
        _log.exception(
            "The sets were not moved into policies: module scopes and features are "
            "refused until a start moves them"
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
                    "policies": report.policies,
                    "reparented": report.reparented,
                    "rewritten": report.rewritten,
                    "granted": report.granted,
                    "removed": report.removed,
                    "invitations": invitations,
                    "notes": list(report.notes),
                }
            ),
        },
    )
    await db.commit()
    set_pending(False)
    await _drop_what_was_read(db)
    _log.info(
        "The sets and the workspace toggles became policies: %d made, %d moved under "
        "them, %d grants. %s",
        report.policies,
        report.reparented,
        report.granted,
        " ".join(report.notes),
    )
    return report


async def _drop_what_was_read(db: AsyncSession) -> None:
    """Once recorded: IAM's legacy sets and the workflows' toggles go. A failure
    is retried at the next start; nothing reads them meanwhile."""
    try:
        if await _has_table(db, "workflow_visibility"):
            await db.execute(text("DROP TABLE workflow_visibility"))
            await db.commit()

        def drop() -> bool:
            with as_service_account("engine"):
                return runtime.iam().drop_legacy_scope_sets()

        await run_in_threadpool(drop)
    except Exception:  # noqa: BLE001 - only leftovers: the next start drops them
        await db.rollback()
        _log.warning(
            "What the sets left was not dropped; the next start tries again", exc_info=True
        )


async def _carry_into_invitations(db: AsyncSession, carried: Mapping[str, Sequence[str]]) -> int:
    """List each new pending grant on the Nexus invitation of the one it came
    with, so revoking or renewing the invitation withdraws it too, and take off
    one the move revoked (no longer pending in IAM)."""
    if not await _has_table(db, "invitations"):
        return 0

    def still_pending() -> set[str]:
        with as_service_account("engine"):
            return {str(g.id) for g in runtime.iam().list_pending_grants()}

    pending_now = await run_in_threadpool(still_pending)
    changed = 0
    rows = (
        await db.execute(text("SELECT id, grant_ids FROM invitations WHERE status = 'pending'"))
    ).all()
    for invitation_id, raw in rows:
        grants = [str(g) for g in json.loads(raw or "[]")]
        kept = [g for g in grants if g in pending_now]
        for old in grants:
            for new in carried.get(old, ()):
                if new not in kept:
                    kept.append(new)
        if kept != grants:
            await db.execute(
                text("UPDATE invitations SET grant_ids = :g WHERE id = :i"),
                {"g": json.dumps(kept), "i": invitation_id},
            )
            changed += 1
    return changed


__all__ = [
    "AFTER",
    "MIGRATION_NAME",
    "NOTES",
    "Legacy",
    "Plan",
    "Report",
    "TurnedOff",
    "UpgradeStop",
    "World",
    "access_statements",
    "apply",
    "build_world",
    "migrate_sets",
    "pending",
    "plan",
    "read_iam",
    "read_nexus",
    "set_pending",
    "statements_at",
    "within_place",
]
