"""The access move (#1587, ADR ``20261120_access_levels_and_groups``, decision 9):
per-person attachments become groups, once, with a report of every access change.

Before, a person held what they could do in each workspace as attachments made to
them one by one: a built-in role at the workspace (and, for an organization's
owners and admins, below it), "Features of <role>", "<W> modules (...)". Now
**where** they work is a membership group ("<W> workspace", "<O> people") and
**what** they do a level ("Members", "Viewers"; ``levels``), and the workspace's
ceiling "<W> access" is its offer, an allow-list (``workspace_offer``).
``migrate_access`` (``iam_migrations`` ``access_model_v1``, at start, under the
moves' lock) builds that target from what IAM holds now:

| Held now (directly) | Groups after |
|---|---|
| ``builtin.platform_admin`` | "Platform admins" (nothing else: it covers every container) |
| owner or admin at O (and below O) | "<O> people", "<O> admins" |
| owner or admin at W | "Members", "<W> workspace", "<W> admins" |
| member at W | "Members", "<W> workspace" |
| viewer at W | "Viewers", "<W> workspace" |
| member or viewer at O, no workspace of O, or invited to O | "<O> people", that level |
| member or viewer at O, a workspace of O, never invited to O | nothing at O: the org Member role goes |

A level is one choice: the highest a person held anywhere (a viewer here and a
member there is a Member, a widening the report names). Then:

- **Records** made before #1585 ("<X> members" in place of the membership group)
  are converted to the grouped shape (``container_defaults.group_attachments``).
- **Ceilings to offers.** Each "<W> access" becomes an allow-list: what it
  allowed (its module patterns, wildcards expanded over the deployment's
  modules) minus what it denied, and its features. Statements of no offer section
  (a module's declared actions) are dropped, named in the report; the result is
  checked with ``workspace_offer.in_offer_form``.
- **Per-person attachments go**: the built-in roles at organizations and
  workspaces, "Features of <role>", "<W> modules (...)", "Feature · <X>" held by
  "<X> members"; every attachment of a platform admin beyond the group. A
  customer policy attached to someone, and a Deny Nexus made for one person
  ("Agents turned off in <W>"), stay: they are exceptions, listed in the report.
- **Shared graph grants** stay per person (S2: a workspace's group cannot hold
  them) and are re-synced: read for W's people, write for its admins.
- **Retired:** "Features of <role>", "<W> modules (...)", "Feature · <X>" left
  attached to nobody, and the emptied "<X> members" groups. One still held by a
  group or an invitation stays, listed.
- **Workspaces left with no admin** get the deployment's default admin
  (``nexus_config.migration.default_workspace_admin``), or are listed.

**The report is IAM's own decisions.** The plan is applied first to a copy of
IAM (``shadow_iam``); every person's decisions (Nexus's actions, features, the
module items of the deployment, shared graphs, models) are compared before and
after, each change classified (``REASONS``: the intended ones flagged). A dry run
stops there and writes nothing. A plan the copy refuses, or a shape this move does
not know (``AccessModelStop``), stops everything: nothing is recorded and nothing
retired. The report is kept (``access_model_v1_planned``) before the real IAM is
changed, so a start interrupted half way is finished by the next one with the
report of the whole move; every step is idempotent. Afterwards the real IAM's
decisions are compared with the copy's (``unverified`` names any difference).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam import platform_files, runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import NEXUS_CATALOG
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    NOTHING_SID,
    DefaultsRecord,
    SqlDefaultsStore,
    group_attachments,
    is_user,
    members_name,
    membership_name,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    MIGRATION_NAME as DEFAULTS_MIGRATION,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import (
    LEVELS,
    MEMBER,
    VIEWER,
    Levels,
    find_levels,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_org_container,
    is_workspace_container,
    nexus_resource,
    org_container,
    org_of,
    workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    KIND_OF_TYPE,
    SECTIONS,
    TYPE_OF_KIND,
    WHOLE_MODULE,
    Item,
    Offer,
    in_offer_form,
    offer_of,
    offer_section,
    with_offer,
)
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE, PLATFORM, is_below
from sqlalchemy import inspect as sql_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "access_model_v1"
# The report of a move under way, kept before the real IAM changes: a start that
# finishes an interrupted move reports the whole of it.
PLANNED_NAME = "access_model_v1_planned"
AFTER = (DEFAULTS_MIGRATION,)

ROLE_POLICIES = {f"builtin.{r}": r for r in ("owner", "admin", "member", "viewer")}
ADMIN_ROLES = frozenset({"owner", "admin"})
LEVEL_OF_ROLE = {"owner": MEMBER, "admin": MEMBER, "member": MEMBER, "viewer": VIEWER}
_LEVEL_RANK = {VIEWER: 1, MEMBER: 2}
USE_FEATURE = "nexus:UseFeature"
FEATURE = "feature"
RUN_ACTIONS = frozenset(
    f"{module_scopes.SERVICE}:{a}"
    for t in (module_scopes.WORKFLOW, module_scopes.PIPELINE)
    for a in (module_scopes.USE_ACTION[t], module_scopes.RUNS_ACTION[t])
)
# What a model probe asks (``model_sets``): a chat and an embedding.
MODEL_ACTIONS = ("model_registry:Chat", "model_registry:Embed")
OTHER_MODEL = "access-move/any-other-model"

# The policies this move retires, recognised by name and description.
FEATURES_OF = "Features of "
FEATURES_OF_DESCRIPTION = "The features the "
MODULES_OF_PEOPLE = " modules (its people)"
MODULES_OF_ADMINS = " modules (admins and owners)"
FEATURE_POLICY = "Feature · "
FEATURE_POLICY_DESCRIPTION = "Who may use "
PER_PERSON_DENY = "Agents turned off in "
# What core IAM keeps in step with a person's roles (and drops with the last one).
COMPANIONS = frozenset({roles.PLATFORM_MEMBER, roles.PLATFORM_VIEWER, roles.PLATFORM_ADMIN})
GRAPH_GRANT_PREFIX = "workspace."
GRAPH_GRANT_INFIX = ".graphs."

# Why a decision changed: (label, intended). Intended: the narrowings and widenings
# the ADR lists; the others are what the model is, named so none is silent.
REASONS: dict[str, tuple[str, bool]] = {
    "members_lose_workflows": (
        "Members lose workflows and pipelines (unless they are in Workflow runners)",
        True,
    ),
    "members_gain_datasets": ("Members gain the datasets feature", True),
    "model_sets": ("Model sets apply (Viewer none, Member the member set, admins all)", True),
    "owners_lose_delete": (
        "Owners lose delete: Owner is no longer assigned (org admins delete workspaces, "
        "the platform admins organizations)",
        True,
    ),
    "org_member_role": (
        "The org Member role goes: reached the organization only through a workspace",
        True,
    ),
    "level_global": ("A level is one choice: the highest held anywhere applies everywhere", False),
    "level_features": ("The level's features, within what the workspace offers", False),
    "viewer_features": (
        "Viewers use the Viewer level's features (apps, datasets): a feature their role's "
        "features gave beyond those goes",
        False,
    ),
    "level_instances": ("The level's agents and apps, within what the workspace offers", False),
    "module_actions": ("A module's declared actions are not part of a workspace's offer", False),
    "shared_graphs": (
        "Shared graphs: read for the workspace's people, write for its admins",
        False,
    ),
    "org_admins": ("Org admins use the organization's offer in every workspace", False),
    "platform_admin": ("A platform admin holds builtin.platform_admin and nothing else", False),
    "default_admin": (
        "The deployment's default workspace admin (nexus_config.migration.default_workspace_admin)",
        False,
    ),
    "unexplained": ("Not explained by the access model: check it", False),
}


class AccessModelStop(RuntimeError):
    """A shape this move does not know: nothing is recorded, nothing retired."""


# -- inputs ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Universe:
    """The module items of the deployment (what a ceiling's wildcard named) and the
    services of the catalogs modules declare."""

    agents: frozenset[Item] = frozenset()
    apps: frozenset[Item] = frozenset()
    workflows: frozenset[Item] = frozenset()
    pipelines: frozenset[Item] = frozenset()
    declared: frozenset[str] = frozenset()
    # ("<service>:<Action>", resource type) of each action a module declares.
    declared_actions: frozenset[tuple[str, str]] = frozenset()

    def items(self, kind: str) -> frozenset[Item]:
        return frozenset(getattr(self, kind))

    def modules(self, kind: str) -> set[str]:
        return {m for m, _n in self.items(kind)}

    def of_module(self, kind: str, module: str) -> set[str]:
        return {n for m, n in self.items(kind) if m == module and n != WHOLE_MODULE}

    def merged(self, other: Universe) -> Universe:
        return Universe(
            **{k: self.items(k) | other.items(k) for k in SECTIONS},
            declared=self.declared | other.declared,
            declared_actions=self.declared_actions | other.declared_actions,
        )


@dataclass
class Inputs:
    """What Nexus says (its tables and configuration) beside what IAM holds."""

    orgs: dict[str, str]  # org id -> name
    workspaces: dict[str, tuple[str | None, str]]  # workspace id -> (org id, name)
    records: dict[str, DefaultsRecord]  # container -> record
    org_invited: set[tuple[str, str]] = field(default_factory=set)  # (user id, org id)
    default_admin: str | None = None  # a Nexus user id
    default_admin_email: str | None = None
    enabled_features: tuple[str, ...] = ()
    universe: Universe = field(default_factory=Universe)
    member_models: tuple[str, ...] = ()

    def org_label(self, org_id: str) -> str:
        return self.orgs.get(org_id, org_id)

    def containers(self) -> dict[str, str]:
        """``{container: label}`` of every organization and workspace, orgs first."""
        found = {org_container(o): name for o, name in sorted(self.orgs.items())}
        for ws, (org, name) in sorted(self.workspaces.items()):
            found[workspace_container(org, ws)] = name
        return found

    def workspaces_of(self, org_id: str) -> list[str]:
        return [
            workspace_container(org, ws)
            for ws, (org, _name) in sorted(self.workspaces.items())
            if org == org_id
        ]


# -- the report -----------------------------------------------------------------------


@dataclass
class Change:
    """A person's decisions that changed at one container, for one reason."""

    user_id: str
    principal_id: str
    container: str  # "" for the platform
    kind: str  # "narrowing" | "widening"
    reason: str
    label: str
    intended: bool
    what: list[str] = field(default_factory=list)  # "<action> on <resource>"


@dataclass
class Report:
    dry_run: bool = False
    applied: bool = False
    people: int = 0
    changes: list[Change] = field(default_factory=list)
    memberships: list[str] = field(default_factory=list)  # "<user> joined <group name>"
    detached: int = 0
    converted_records: list[str] = field(default_factory=list)
    converted_ceilings: list[str] = field(default_factory=list)
    dropped_from_ceilings: dict[str, list[str]] = field(default_factory=dict)
    # Features a container's "Features of <role>" gave, added to its offer.
    offered_features: dict[str, list[str]] = field(default_factory=dict)
    retired_policies: list[str] = field(default_factory=list)
    retired_groups: list[str] = field(default_factory=list)
    kept_policies: list[str] = field(default_factory=list)
    kept_attachments: list[str] = field(default_factory=list)
    org_roles_removed: list[str] = field(default_factory=list)  # "<user> at <org>"
    org_only: list[str] = field(default_factory=list)  # "<user> in <org>"
    empty_workspaces: list[str] = field(default_factory=list)
    no_admin: list[str] = field(default_factory=list)
    default_admin: str | None = None
    default_admin_added: list[str] = field(default_factory=list)
    drive_flags: list[dict[str, Any]] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Report:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        known["changes"] = [Change(**c) for c in data.get("changes") or ()]
        return cls(**known)

    def narrowings(self) -> list[Change]:
        return [c for c in self.changes if c.kind == "narrowing"]

    def unexplained(self) -> list[Change]:
        return [c for c in self.changes if c.reason == "unexplained"]

    def lines(self) -> list[str]:
        """The report as text: for the log and the CLI."""
        out = [
            f"Access move ({'dry run' if self.dry_run else 'applied' if self.applied else 'planned'}):"
            f" {self.people} people, {len(self.memberships)} memberships, {self.detached} "
            f"attachments detached, {len(self.retired_policies)} policies and "
            f"{len(self.retired_groups)} groups retired, {len(self.converted_ceilings)} ceilings "
            "made offers."
        ]
        by_person: dict[str, list[Change]] = {}
        for change in self.changes:
            by_person.setdefault(change.user_id, []).append(change)
        for user, changes in sorted(by_person.items()):
            out.append(f"  {user}:")
            for change in changes:
                flag = "intended" if change.intended else "model"
                where = change.container or "the platform"
                out.append(
                    f"    {change.kind} at {where} ({flag}: {change.label}): "
                    + "; ".join(change.what[:6])
                    + (f" (+{len(change.what) - 6})" if len(change.what) > 6 else "")
                )
        for title, items in (
            ("Org Member roles removed", self.org_roles_removed),
            ("Org-only people", self.org_only),
            ("Workspaces with an empty workspace group", self.empty_workspaces),
            ("Workspaces with no admin", self.no_admin),
            ("Given the default workspace admin", self.default_admin_added),
            (
                "Dropped from ceilings",
                [f"{c}: {', '.join(v)}" for c, v in self.dropped_from_ceilings.items()],
            ),
            (
                "Features added to offers",
                [f"{c}: {', '.join(v)}" for c, v in self.offered_features.items()],
            ),
            ("Kept (still held by a group or an invitation)", self.kept_policies),
            ("Per-person attachments kept (exceptions)", self.kept_attachments),
            ("Drive flags", [json.dumps(r, sort_keys=True, default=str) for r in self.drive_flags]),
            ("Not as the copy said", self.unverified),
            ("Notes", self.notes),
        ):
            if items:
                out.append(f"  {title}:")
                out += [f"    {item}" for item in items]
        return out


# -- reading IAM ----------------------------------------------------------------------


def _pages(listing: Any, **kwargs: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after, **kwargs)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _group(iam: Any, group_id: str | None) -> Any | None:
    if not group_id:
        return None
    try:
        group = iam.get_group(group_id)
    except (IAMNotFoundError, ResourceNotFoundError):
        return None
    return None if group.status == "deleted" else group


def _own_groups(iam: Any, container: str) -> dict[str, Any]:
    return {
        str(g.name): g
        for g in _pages(iam.list_groups, scope=container)
        if g.owner_scope == container and g.status != "deleted"
    }


def _user_id(iam: Any, principal_id: str) -> str:
    """The id Nexus names the person by (``Memberships._user_id``)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    try:
        return MEMBERSHIPS._user_id(iam, principal_id)
    except (IAMNotFoundError, ResourceNotFoundError):
        return principal_id


def is_retired_kind(policy: Any) -> str | None:
    """Which retired kind ``policy`` is ("features", "modules", "feature"), or None."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree import MADE

    name, description = str(policy.name), str(policy.description or "")
    if name.startswith(FEATURES_OF) and description.startswith(FEATURES_OF_DESCRIPTION):
        return "features"
    if (
        name.endswith(MODULES_OF_PEOPLE) or name.endswith(MODULES_OF_ADMINS)
    ) and description.endswith(MADE):
        return "modules"
    if name.startswith(FEATURE_POLICY) and description.startswith(FEATURE_POLICY_DESCRIPTION):
        return "feature"
    return None


# -- ceilings to offers ---------------------------------------------------------------

_MODULE_PREFIX = f"${{scope}}/{module_scopes.SERVICE}:"
_FEATURE_PREFIX = "${scope}/nexus:feature/"


def _module_pattern(pattern: str) -> tuple[str, str, str] | None:
    """``(kind, module, name)`` of ``${scope}/module:<type>/...``: ``*`` for a
    wildcard (``(kind, "*", "*")`` for every module of the type); None for another."""
    if not pattern.startswith(_MODULE_PREFIX):
        return None
    type_name, _, rest = pattern[len(_MODULE_PREFIX) :].partition("/")
    kind = KIND_OF_TYPE.get(type_name)
    if kind is None:
        if type_name == "*" and rest == "":
            return ("*", "*", "*")
        return None
    if rest == "*":
        return (kind, "*", "*")
    module, _, name = rest.partition("/")
    if not module or not name or "/" in name or module == "*":
        return None
    return (kind, unquote(module), WHOLE_MODULE if name == "*" else unquote(name))


def ceiling_offer(
    document: Any, *, universe: Universe, features: Sequence[str]
) -> tuple[Offer, list[str]]:
    """The offer a ceiling of an older version makes: everything it allowed (its
    module patterns, a wildcard of every module expanded over ``universe``; its
    features, ``*`` being ``features``) minus everything it denied, beside the offer
    sections it already holds. Also what is dropped (a module's declared actions).
    ``AccessModelStop`` on a statement of a shape no older ceiling had."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
        _statement_parts,
        _statements_of,
    )

    allowed: dict[str, set[Item]] = {kind: set() for kind in SECTIONS}
    denied: dict[str, set[Item]] = {kind: set() for kind in SECTIONS}
    every: set[str] = set()
    wanted_features: set[str] = set()
    dropped: list[str] = []
    held = Offer()
    for statement in _statements_of(document):
        sid, effect, actions, resources = _statement_parts(statement)
        if offer_section(sid) is not None and effect == "Allow":
            held = held.merged(offer_of({"statements": [statement]}))
            continue
        if sid == NOTHING_SID:
            continue
        for resource in resources:
            found = _module_pattern(resource)
            if found is not None:
                kind, module, name = found
                kinds = list(SECTIONS) if kind == "*" else [kind]
                for each in kinds:
                    if effect == "Deny":
                        if module == "*":
                            raise AccessModelStop(
                                f"a ceiling denies every {each} ({resource}): not an older ceiling"
                            )
                        denied[each].add((module, name))
                    elif module == "*":
                        every.add(each)
                    else:
                        allowed[each].add((module, name))
                continue
            if resource.startswith(_FEATURE_PREFIX) and any(
                a in (USE_FEATURE, "nexus:*", "*") for a in actions
            ):
                key = resource[len(_FEATURE_PREFIX) :]
                if effect == "Deny":
                    raise AccessModelStop(f"a ceiling denies a feature ({resource})")
                if key == "*":
                    wanted_features.update(features)
                else:
                    wanted_features.add(unquote(key))
                continue
            service = resource.removeprefix("${scope}/").partition(":")[0]
            if (
                effect == "Allow"
                and resource == f"${{scope}}/{service}:*"
                and all(a.partition(":")[0] == service for a in actions)
            ):
                dropped.append(f"{', '.join(actions)} on {resource}")
                continue
            raise AccessModelStop(
                f"a ceiling statement ({sid or 'no sid'}, {effect} {resource}) is none an "
                "older version wrote"
            )
    offered: dict[str, set[Item]] = {}
    for kind in SECTIONS:
        items = set(allowed[kind])
        if kind in every:
            items |= {(m, WHOLE_MODULE) for m in universe.modules(kind)}
        for module, name in sorted(denied[kind]):
            if name == WHOLE_MODULE:
                items = {i for i in items if i[0] != module}
                continue
            if (module, WHOLE_MODULE) in items:
                items.discard((module, WHOLE_MODULE))
                items |= {(module, n) for n in universe.of_module(kind, module)}
            items.discard((module, name))
        items |= set(held.items(kind))
        offered[kind] = items
    offer = Offer(
        **{kind: frozenset(items) for kind, items in offered.items()},
        features=frozenset(wanted_features | set(held.features)),
    )
    return offer, dropped


# -- what each person holds and gets --------------------------------------------------


@dataclass
class PersonPlan:
    """One person: what they hold now and the groups they get."""

    principal_id: str
    user_id: str
    platform_admin: bool = False
    roles: dict[str, str] = field(default_factory=dict)  # container -> best role before
    level_before: str | None = None
    level: str | None = None
    org_admin_of: set[str] = field(default_factory=set)  # org ids
    org_people_of: set[str] = field(default_factory=set)  # org ids
    org_roles_removed: set[str] = field(default_factory=set)  # org ids
    workspaces: set[str] = field(default_factory=set)  # workspace containers
    admin_of: set[str] = field(default_factory=set)  # workspace containers
    default_admin_of: set[str] = field(default_factory=set)
    workflow_runner: bool = False
    joins: list[str] = field(default_factory=list)  # group ids, in order
    leaves: list[str] = field(default_factory=list)
    detach: list[tuple[str, str | None]] = field(default_factory=list)  # (policy, scope)
    kept: list[str] = field(default_factory=list)

    def containers(self, inputs: Inputs) -> set[str]:
        """Where their decisions are compared: every container they held a role in
        or belong to afterwards, and every workspace of the organizations they
        administer."""
        found = set(self.roles) | set(self.workspaces)
        for org in self.org_admin_of | self.org_people_of | self.org_roles_removed:
            found.add(org_container(org))
        for org in self.org_admin_of:
            found.update(inputs.workspaces_of(org))
        for container in list(found):
            if is_below(container):
                found.discard(container)
        return found


def _best(found: Iterable[str]) -> str | None:
    order = ("viewer", "member", "admin", "owner")
    ranked = [r for r in found if r in order]
    return max(ranked, key=order.index) if ranked else None


def _higher(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if _LEVEL_RANK[a] >= _LEVEL_RANK[b] else b


@dataclass
class _Reading:
    """What IAM holds now, read once (as ``api``)."""

    direct: dict[str, list[Any]]  # principal -> its own attachments
    groups: dict[str, set[str]]  # principal -> its groups
    members: dict[str, set[str]]  # group -> its members


def _read(iam: Any, groups_of_interest: Iterable[str]) -> _Reading:
    direct: dict[str, list[Any]] = {}
    for attachment in iam.list_attachments():
        if is_user(attachment.principal_id):
            direct.setdefault(attachment.principal_id, []).append(attachment)
    members: dict[str, set[str]] = {}
    groups: dict[str, set[str]] = {}
    for group_id in dict.fromkeys(g for g in groups_of_interest if g):
        try:
            found = set(iam.list_group_members(group_id))
        except (IAMNotFoundError, ResourceNotFoundError):
            found = set()
        members[group_id] = found
        for member in found:
            groups.setdefault(member, set()).add(group_id)
    return _Reading(direct, groups, members)


def plan_people(
    iam: Any,
    inputs: Inputs,
    records: Mapping[str, DefaultsRecord],
    levels: Levels,
    old_groups: Mapping[str, str],
) -> dict[str, PersonPlan]:
    """Every person who holds a role at an organization or a workspace (directly or
    through its groups) or ``builtin.platform_admin``: what they hold, the groups
    they get, what is detached. Read as ``api``; changes nothing."""
    by_group: dict[str, tuple[str, str]] = {}  # group -> (container, "membership"|"admins")
    for container, record in records.items():
        by_group[str(record.members_group_id)] = (container, "membership")
        by_group[str(record.admins_group_id)] = (container, "admins")
    runners = {}
    for org in inputs.orgs:
        from naas_abi.apps.nexus.apps.api.app.services.iam.capabilities import find_capability

        found = find_capability(iam, org, "workflow_runners")
        if found:
            runners[org] = found
    reading = _read(
        iam,
        [
            *by_group,
            *levels.level_groups,
            levels.platform_admins,
            levels.workspace_admins,
            *runners.values(),
            *old_groups.values(),
        ],
    )
    known = set(inputs.containers())
    policies = _pages(iam.list_policies)
    policy_names = {str(p.id): str(p.name) for p in policies}
    retired = _retired_policies(iam, policies)
    people: set[str] = set(reading.direct)
    for group in (*by_group, *levels.level_groups, levels.platform_admins):
        people |= {m for m in reading.members.get(group, set()) if is_user(m)}
    plans: dict[str, PersonPlan] = {}
    for principal_id in sorted(people):
        plan = PersonPlan(principal_id, _user_id(iam, principal_id))
        mine = reading.groups.get(principal_id, set())
        attachments = reading.direct.get(principal_id, [])
        org_roles: dict[str, str] = {}
        ws_roles: dict[str, str] = {}
        held: dict[str, list[str]] = {}
        for attachment in attachments:
            if attachment.policy_id == roles.PLATFORM_ADMIN and attachment.scope is None:
                plan.platform_admin = True
            role = ROLE_POLICIES.get(attachment.policy_id)
            if role is None:
                continue
            scope = attachment.scope
            if scope is None or scope == MY_CONTAINERS_SCOPE:
                raise AccessModelStop(
                    f"{principal_id} holds {attachment.policy_id} at {scope or 'no scope'}"
                )
            where = scope.removesuffix("/*") if is_below(scope) else scope
            if where not in known or (is_below(scope) and not is_org_container(where)):
                raise AccessModelStop(
                    f"{principal_id} holds {attachment.policy_id} at {scope}, which names no "
                    "organization or workspace Nexus has"
                )
            held.setdefault(scope, []).append(role)
        if levels.platform_admins in mine:
            plan.platform_admin = True
        for scope, names in held.items():
            best = _best(names) or "viewer"
            if is_below(scope):
                org = org_of(scope) or ""
                if best in ADMIN_ROLES:
                    org_roles[org] = _best([org_roles.get(org, "viewer"), best]) or best
                continue
            plan.roles[scope] = best
            if is_org_container(scope):
                org_roles[org_of(scope) or ""] = best
            else:
                ws_roles[scope] = best
        if levels.members in mine:
            plan.level_before = MEMBER
        elif levels.viewers in mine:
            plan.level_before = VIEWER
        # Already in the groups (a container grouped since #1585, or a move that
        # stopped half way): what they hold through them.
        for group in mine:
            where = by_group.get(group)
            if where is None:
                continue
            container, kind = where
            if is_org_container(container):
                org = org_of(container) or ""
                if kind == "admins":
                    org_roles[org] = "admin"
                    plan.roles[container] = (
                        _best([plan.roles.get(container, "viewer"), "admin"]) or "admin"
                    )
                else:
                    plan.org_people_of.add(org)
                    plan.roles.setdefault(container, plan.level_before or "viewer")
            elif kind == "admins":
                ws_roles[container] = "admin"
                plan.roles[container] = (
                    _best([plan.roles.get(container, "viewer"), "admin"]) or "admin"
                )
            else:
                plan.workspaces.add(container)
                plan.roles.setdefault(container, plan.level_before or "viewer")
        plan.workflow_runner = any(g in mine for g in runners.values())
        if plan.platform_admin:
            _plan_platform_admin(plan, attachments, levels, mine)
        else:
            _plan_member(
                plan,
                inputs,
                records,
                levels,
                mine,
                org_roles,
                ws_roles,
                attachments,
                retired,
                policy_names,
            )
        plans[principal_id] = plan
    return plans


def _plan_platform_admin(
    plan: PersonPlan, attachments: Sequence[Any], levels: Levels, mine: set[str]
) -> None:
    """ "Platform admins", and no attachment of their own: ``builtin.platform_admin``
    covers every container."""
    if levels.platform_admins not in mine:
        plan.joins.append(levels.platform_admins)
    plan.detach = [(a.policy_id, a.scope) for a in attachments]


def _plan_member(
    plan: PersonPlan,
    inputs: Inputs,
    records: Mapping[str, DefaultsRecord],
    levels: Levels,
    mine: set[str],
    org_roles: Mapping[str, str],
    ws_roles: Mapping[str, str],
    attachments: Sequence[Any],
    retired: Mapping[str, str],
    names: Mapping[str, str],
) -> None:
    level = plan.level_before
    for container, role in ws_roles.items():
        level = _higher(level, LEVEL_OF_ROLE[role])
        plan.workspaces.add(container)
        if role in ADMIN_ROLES:
            plan.admin_of.add(container)
    workspace_orgs = {org_of(c) for c in ws_roles if org_of(c)}
    for org, role in org_roles.items():
        if role in ADMIN_ROLES:
            plan.org_admin_of.add(org)
            plan.org_people_of.add(org)
            continue
        direct = plan.roles.get(org_container(org)) == role and org not in plan.org_people_of
        if direct and org in workspace_orgs and (plan.user_id, org) not in inputs.org_invited:
            plan.org_roles_removed.add(org)
            continue
        plan.org_people_of.add(org)
        level = _higher(level, LEVEL_OF_ROLE[role])
    plan.level = level
    wanted: list[str] = []
    for org in sorted(plan.org_people_of):
        record = records[org_container(org)]
        wanted.append(str(record.members_group_id))
    for container in sorted(plan.workspaces):
        wanted.append(str(records[container].members_group_id))
    for org in sorted(plan.org_admin_of):
        wanted.append(str(records[org_container(org)].admins_group_id))
    for container in sorted(plan.admin_of):
        wanted.append(str(records[container].admins_group_id))
    if level is not None:
        wanted.append(levels.group_of(level))
        other = levels.group_of(VIEWER if level == MEMBER else MEMBER)
        if other in mine:
            plan.leaves.append(other)
    if plan.org_admin_of or plan.admin_of:
        wanted.append(levels.workspace_admins)
    plan.joins = [g for g in dict.fromkeys(wanted) if g not in mine]
    for attachment in attachments:
        if attachment.policy_id in ROLE_POLICIES:
            plan.detach.append((attachment.policy_id, attachment.scope))
        elif attachment.policy_id in retired and retired[attachment.policy_id] != "feature":
            plan.detach.append((attachment.policy_id, attachment.scope))
        elif (
            attachment.policy_id not in COMPANIONS
            and roles.retired_role(str(attachment.policy_id)) is None
            and not _is_graph_grant(str(attachment.policy_id), names)
        ):
            name = names.get(str(attachment.policy_id), str(attachment.policy_id))
            plan.kept.append(f"{name} ({attachment.policy_id}) at {attachment.scope or 'no scope'}")


def _is_graph_grant(policy_id: str, names: Mapping[str, str]) -> bool:
    """A workspace's shared-graph policy (``graph_grants.policy_name``): per person,
    kept in step by ``_sync_graph_grants``."""
    name = names.get(policy_id, "")
    return name.startswith(GRAPH_GRANT_PREFIX) and GRAPH_GRANT_INFIX in name


def _retired_policies(iam: Any, policies: Sequence[Any] | None = None) -> dict[str, str]:
    """``{policy id: kind}`` of the policies this move retires (``is_retired_kind``)."""
    listed = _pages(iam.list_policies) if policies is None else policies
    return {str(p.id): kind for p in listed if (kind := is_retired_kind(p)) is not None}


# -- applying it ----------------------------------------------------------------------


@dataclass
class Outcome:
    """What ``apply`` did (or would do, on a copy)."""

    records: dict[str, DefaultsRecord] = field(default_factory=dict)
    converted: list[str] = field(default_factory=list)
    plans: dict[str, PersonPlan] = field(default_factory=dict)
    report: Report = field(default_factory=Report)
    graph_policies: list[str] = field(default_factory=list)


def convert_record(
    iam: Any, container: str, label: str, record: DefaultsRecord, levels: Levels
) -> tuple[DefaultsRecord, str | None]:
    """The record of ``container`` in the grouped shape: its membership group
    ("<W> workspace", "<O> people": the record's when it is one, else found by
    name, else made), its admins group (a membership group of W for a workspace),
    and what they hold (``group_attachments``, with the access policy: W's bound).
    A workspace's admins group no longer holds the access policy at W (an older
    record's). Returns the record and the retired "<X> members" group, if any. As
    ``api``."""
    if not record.access_policy_id or not record.admins_group_id:
        raise AccessModelStop(f"{container}'s record names no access policy or admins group")
    try:
        iam.get_policy(record.access_policy_id)
    except (IAMNotFoundError, ResourceNotFoundError) as exc:
        raise AccessModelStop(f"{container}'s access policy is gone") from exc
    admins = _group(iam, record.admins_group_id)
    if admins is None:
        raise AccessModelStop(f"{container}'s admins group is gone")
    current = _group(iam, record.members_group_id)
    old: str | None = None
    if current is not None and current.membership_of == container:
        membership = str(current.id)
    else:
        own = _own_groups(iam, container)
        if current is not None:
            old = str(current.id)
        elif (found := own.get(members_name(label))) is not None and not found.membership_of:
            old = str(found.id)
        named = own.get(membership_name(container, label))
        if named is not None and named.membership_of not in (None, container):
            raise AccessModelStop(f"{named.id} is a membership group of another container")
        if named is None:
            named = iam.create_group(
                membership_name(container, label), scope=container, membership_of=container
            )
        elif named.membership_of != container:
            iam.mark_group(named.id, membership_of=container, level=bool(named.level_group))
        membership = str(named.id)
    if is_workspace_container(container) and admins.membership_of != container:
        if admins.membership_of is not None:
            raise AccessModelStop(f"{admins.id} is a membership group of another container")
        iam.mark_group(admins.id, membership_of=container, level=bool(admins.level_group))
    converted = DefaultsRecord(container, record.access_policy_id, membership, str(admins.id))
    held: dict[str, set[tuple[str, str | None]]] = {}
    for policy_id, group_id, scope in group_attachments(container, converted, levels, access=True):
        if group_id not in held:
            held[group_id] = {
                (a.policy_id, a.scope) for a in iam.list_attachments(principal_id=group_id)
            }
        if (policy_id, scope) not in held[group_id]:
            iam.attach_policy(policy_id, group_id, scope)
    if is_workspace_container(container):
        for attachment in iam.list_attachments(principal_id=str(admins.id)):
            if attachment.policy_id == record.access_policy_id and attachment.scope == container:
                iam.detach_policy(attachment.policy_id, str(admins.id), container)
    return converted, old


def chosen_features(iam: Any, containers: Iterable[str]) -> dict[str, set[str]]:
    """``{container: features}`` the "Features of <role>" policies give there: what
    each organization and workspace chose for its people. A policy counts where it
    is attached or owned; one attached below an organization (its org-wide holders)
    counts for the organization. As ``api``."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import _feature_of

    known = set(containers)
    found: dict[str, set[str]] = {}
    for policy_id, kind in _retired_policies(iam).items():
        if kind != "features":
            continue
        try:
            policy = iam.get_policy(policy_id)
        except (IAMNotFoundError, ResourceNotFoundError):
            continue
        features = {
            key
            for statement in policy.document.statements
            if statement.effect == "Allow" and USE_FEATURE in statement.actions
            for resource in statement.resources
            if (key := _feature_of(resource)) is not None
        }
        if not features:
            continue
        places = {str(policy.owner_scope)}
        places |= {str(a.scope) for a in iam.list_attachments(policy_id=policy_id) if a.scope}
        for place in places:
            where = place.removesuffix("/*") if is_below(place) else place
            if where in known:
                found.setdefault(where, set()).update(features)
    return found


def offer_features(
    iam: Any, container: str, policy_id: str, features: set[str], report: Report
) -> bool:
    """``features`` added to the offer sections of ``container``'s access policy, its
    other statements kept (an organization's is not an offer: S3). Whether it
    changed. As ``api``."""
    policy = iam.get_policy(policy_id)
    held = offer_of(policy.document)
    if features <= set(held.features):
        return False
    document = with_offer(policy.document, held.merged(Offer(features=frozenset(features))))
    iam.update_policy(policy.id, expected_revision=policy.revision, document=document)
    report.offered_features[container] = sorted(features - set(held.features))
    return True


def convert_ceiling(
    iam: Any,
    container: str,
    policy_id: str,
    inputs: Inputs,
    report: Report,
    features: Iterable[str] = (),
) -> bool:
    """ "<W> access" as W's offer (``ceiling_offer``), with the features W chose for
    its people (``chosen_features``), checked with ``in_offer_form``. Whether it
    changed. As ``api``."""
    chosen = set(features)
    policy = iam.get_policy(policy_id)
    if in_offer_form(policy.document):
        return offer_features(iam, container, policy_id, chosen, report)
    offer, dropped = ceiling_offer(
        policy.document, universe=inputs.universe, features=inputs.enabled_features
    )
    if not chosen <= set(offer.features):
        report.offered_features[container] = sorted(chosen - set(offer.features))
    offer = offer.merged(Offer(features=frozenset(chosen)))
    document = with_offer({"statements": []}, offer)
    if not in_offer_form(document):
        raise AccessModelStop(f"the offer of {container} is not in offer form")
    iam.update_policy(policy.id, expected_revision=policy.revision, document=document)
    report.converted_ceilings.append(container)
    if dropped:
        report.dropped_from_ceilings[container] = dropped
    return True


def _join(iam: Any, group_id: str, principal_id: str) -> bool:
    if principal_id in iam.list_group_members(group_id):
        return False
    iam.add_group_member(group_id, principal_id)
    return True


def apply(iam: Any, inputs: Inputs, levels: Levels, *, dry_run: bool) -> Outcome:
    """Make the target true in ``iam`` (the real one, or a copy): records, ceilings,
    memberships, shared graphs, detaches, retirements, the default admin. Every step
    may run again. As ``api`` (retiring as the engine)."""
    outcome = Outcome(report=Report(dry_run=dry_run))
    report = outcome.report
    labels = inputs.containers()
    old_groups: dict[str, str] = {}
    with as_service_account("api"):
        for container, label in labels.items():
            record = inputs.records.get(container)
            if record is None:
                raise AccessModelStop(f"{container} has no access policy and groups yet")
            converted, old = convert_record(iam, container, label, record, levels)
            if converted != record:
                outcome.converted.append(container)
                report.converted_records.append(container)
            if old:
                old_groups[container] = old
            outcome.records[container] = converted
        # The features chosen for each container's people ("Features of <role>")
        # become its offer's; an organization's offers its workspaces' too, which
        # its access bounds.
        chosen = chosen_features(iam, outcome.records)
        for container, record in outcome.records.items():
            if is_org_container(container):
                wanted = set(chosen.get(container, set()))
                for workspace in inputs.workspaces_of(org_of(container) or ""):
                    wanted |= chosen.get(workspace, set())
                offer_features(iam, container, str(record.access_policy_id), wanted, report)
        for container, record in outcome.records.items():
            if is_workspace_container(container):
                convert_ceiling(
                    iam,
                    container,
                    str(record.access_policy_id),
                    inputs,
                    report,
                    chosen.get(container, ()),
                )
        plans = plan_people(iam, inputs, outcome.records, levels, old_groups)
        outcome.plans = plans
        report.people = len(plans)
        names = {
            g: str(getattr(_group(iam, g), "name", g))
            for p in plans.values()
            for g in [*p.joins, *p.leaves]
        }
        # Memberships first (a person's first tie to an organization is its
        # membership group), then the admins groups, then the level.
        for plan in plans.values():
            for group_id in plan.joins:
                if _join(iam, group_id, plan.principal_id):
                    report.memberships.append(
                        f"{plan.user_id} joined {names.get(group_id, group_id)}"
                    )
            for group_id in plan.leaves:
                iam.remove_group_member(group_id, plan.principal_id)
            for org in sorted(plan.org_roles_removed):
                report.org_roles_removed.append(
                    f"{plan.user_id} at {inputs.org_label(org)} ({org})"
                )
            report.kept_attachments += [f"{plan.user_id}: {k}" for k in plan.kept]
        _default_admin(iam, inputs, outcome, levels)
        outcome.graph_policies = _sync_graph_grants(iam, inputs, outcome)
        for plan in plans.values():
            for policy_id, scope in plan.detach:
                if iam.detach_policy(policy_id, plan.principal_id, scope):
                    report.detached += 1
    with as_service_account("engine"):
        _retire(iam, outcome, old_groups)
    _list_who_is_where(iam, inputs, outcome)
    return outcome


def _default_admin(iam: Any, inputs: Inputs, outcome: Outcome, levels: Levels) -> None:
    """The deployment's default admin joins each workspace left with no admin; or the
    workspaces are listed (``no_admin``)."""
    report = outcome.report
    report.default_admin = inputs.default_admin_email
    empty = [
        c
        for c, r in sorted(outcome.records.items())
        if is_workspace_container(c) and not iam.list_group_members(str(r.admins_group_id))
    ]
    if not empty:
        return
    if not inputs.default_admin:
        report.no_admin = empty
        return
    principal = iam.resolve_user(inputs.default_admin)
    if principal is None:
        from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

        principal = iam.ensure_user(
            LEGACY_NEXUS_ISSUER,
            inputs.default_admin,
            provider="nexus",
            email=inputs.default_admin_email,
        )
    principal_id = str(principal.id)
    plan = outcome.plans.get(principal_id) or PersonPlan(principal_id, _user_id(iam, principal_id))
    outcome.plans[principal_id] = plan
    mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
    for container in empty:
        record = outcome.records[container]
        for group_id in (str(record.members_group_id), str(record.admins_group_id)):
            _join(iam, group_id, principal_id)
        plan.workspaces.add(container)
        plan.admin_of.add(container)
        plan.default_admin_of.add(container)
        report.default_admin_added.append(container)
    if levels.members not in mine and not plan.platform_admin:
        if levels.viewers in mine:
            iam.remove_group_member(levels.viewers, principal_id)
        _join(iam, levels.members, principal_id)
        plan.level = MEMBER
    _join(iam, levels.workspace_admins, principal_id)


def _sync_graph_grants(iam: Any, inputs: Inputs, outcome: Outcome) -> list[str]:
    """Each workspace's shared-graph policies (``graph_grants``) held by exactly its
    people (read) and its admins (write), unscoped, as Nexus keeps them. Returns the
    policies' ids."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
        READ,
        WRITE,
        policy_name,
    )

    by_name = {
        str(p.name): str(p.id)
        for p in _pages(iam.list_policies)
        if str(p.name).startswith("workspace.") and p.owner_scope == PLATFORM
    }
    found: list[str] = []
    for container, record in sorted(outcome.records.items()):
        workspace = workspace_of(container)
        if not workspace or not is_workspace_container(container):
            continue
        people = set(iam.list_group_members(str(record.members_group_id)))
        admins = set(iam.list_group_members(str(record.admins_group_id)))
        for kind, holders in ((READ, people | admins), (WRITE, admins)):
            policy_id = by_name.get(policy_name(workspace, kind))
            if policy_id is None:
                continue
            found.append(policy_id)
            held = {
                a.principal_id
                for a in iam.list_attachments(policy_id=policy_id)
                if a.scope is None and is_user(a.principal_id)
            }
            for principal_id in sorted(holders - held):
                iam.attach_policy(policy_id, principal_id)
            for principal_id in sorted(held - holders):
                iam.detach_policy(policy_id, principal_id)
    return found


def _retire(iam: Any, outcome: Outcome, old_groups: Mapping[str, str]) -> None:
    """The emptied "<X> members" groups and the retired policies: deleted once
    nothing holds them. One still held by a group, a service account or an
    invitation stays, listed."""
    report = outcome.report
    for container, group_id in sorted(old_groups.items()):
        group = _group(iam, group_id)
        if group is None:
            continue
        for member in list(iam.list_group_members(group_id)):
            iam.remove_group_member(group_id, member)
        for attachment in iam.list_attachments(principal_id=group_id):
            iam.detach_policy(attachment.policy_id, group_id, attachment.scope)
        iam.delete_group(group_id)
        report.retired_groups.append(f"{group.name} ({container})")
    retired = _retired_policies(iam)
    for policy_id, kind in sorted(retired.items()):
        try:
            policy = iam.get_policy(policy_id)
        except (IAMNotFoundError, ResourceNotFoundError):
            continue
        held = iam.list_attachments(policy_id=policy_id)
        pending = iam.list_pending_grants(policy_id=policy_id)
        subs = iam.list_sub_policies(policy_id)
        if held or pending or subs:
            if kind != "feature" or held:
                report.kept_policies.append(
                    f"{policy.name} ({policy.owner_scope}): held by "
                    + ", ".join(
                        [
                            *(a.principal_id for a in held[:5]),
                            *(f"invitation {g.id}" for g in pending[:5]),
                        ]
                        or [f"{len(subs)} sub-policies"]
                    )
                )
            continue
        try:
            iam.delete_policy(policy_id)
        except IAMConflictError as exc:
            report.kept_policies.append(f"{policy.name} ({policy.owner_scope}): {exc}")
            continue
        report.retired_policies.append(f"{policy.name} ({policy.owner_scope})")


def _list_who_is_where(iam: Any, inputs: Inputs, outcome: Outcome) -> None:
    report = outcome.report
    with as_service_account("api"):
        for container, record in sorted(outcome.records.items()):
            if not is_workspace_container(container):
                continue
            if not iam.list_group_members(str(record.members_group_id)):
                report.empty_workspaces.append(container)
    for plan in outcome.plans.values():
        for org in sorted(plan.org_people_of - plan.org_admin_of):
            if not any(org_of(w) == org for w in plan.workspaces):
                report.org_only.append(f"{plan.user_id} in {inputs.org_label(org)} ({org})")


# -- decisions ------------------------------------------------------------------------


def _probe_id(kind: str) -> Any:
    if kind == "singleton":
        return ()
    if kind == "path":
        return ("probe", "x")
    return "probe"


def _nexus_probes(container: str) -> list[tuple[str, str]]:
    """``(action, resource)`` of every Nexus action whose resource sits in
    ``container`` (or is it), one resource each."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import TYPES_BY_NAME

    found: list[tuple[str, str]] = []
    org = is_org_container(container)
    for spec in NEXUS_CATALOG.actions:
        type_name = spec.resource_types[0]
        resource_type = TYPES_BY_NAME.get(type_name)
        if resource_type is None or resource_type.placement == "platform" or resource_type.personal:
            continue
        if type_name == FEATURE:
            continue
        try:
            if resource_type.container:
                is_type = (type_name == "organization") == org
                if spec.creates:
                    if org and type_name == "workspace":
                        found.append(
                            (
                                f"nexus:{spec.name}",
                                nexus_resource(type_name, container=container, id="probe"),
                            )
                        )
                    continue
                if is_type:
                    found.append((f"nexus:{spec.name}", container))
                continue
            found.append(
                (
                    f"nexus:{spec.name}",
                    nexus_resource(type_name, container=container, id=_probe_id(resource_type.id)),
                )
            )
        except (ValueError, KeyError):
            continue
    return found


def _platform_probes(inputs: Inputs) -> list[tuple[str, str]]:
    from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import TYPES_BY_NAME
    from naas_abi.apps.nexus.apps.api.app.services.iam.model_sets import model_resource

    found: list[tuple[str, str]] = []
    for spec in NEXUS_CATALOG.actions:
        resource_type = TYPES_BY_NAME.get(spec.resource_types[0])
        if resource_type is None or resource_type.placement != "platform" or resource_type.personal:
            continue
        try:
            found.append(
                (
                    f"nexus:{spec.name}",
                    nexus_resource(resource_type.name, id=_probe_id(resource_type.id)),
                )
            )
        except (ValueError, KeyError):
            continue
    for model in (*inputs.member_models, OTHER_MODEL):
        for action in MODEL_ACTIONS:
            found.append((action, model_resource(model)))
    return found


def _workspace_probes(container: str, inputs: Inputs) -> list[tuple[str, str]]:
    found = [
        (USE_FEATURE, nexus_resource(FEATURE, container=container, id=key))
        for key in inputs.enabled_features
    ]
    for kind in SECTIONS:
        type_name = TYPE_OF_KIND[kind]
        actions = [module_scopes.USE_ACTION[type_name]]
        if type_name in module_scopes.RUNS_ACTION:
            actions.append(module_scopes.RUNS_ACTION[type_name])
        for module, name in sorted(inputs.universe.items(kind)):
            if name == WHOLE_MODULE:
                continue
            resource = module_scopes.scope_resource(type_name, module, name, container=container)
            found += [(f"{module_scopes.SERVICE}:{a}", resource) for a in actions]
    for action, type_name in sorted(inputs.universe.declared_actions):
        service = action.partition(":")[0]
        found.append((action, f"{container}/{service}:{type_name}/probe"))
    return found


def _graph_probes(iam: Any, policy_ids: Iterable[str]) -> list[tuple[str, str]]:
    """Each literal resource the shared-graph policies name, with their actions."""
    found: list[tuple[str, str]] = []
    for policy_id in dict.fromkeys(policy_ids):
        try:
            policy = iam.get_policy(policy_id)
        except (IAMNotFoundError, ResourceNotFoundError):
            continue
        for statement in policy.document.statements:
            literal = [r for r in statement.resources if "*" not in r and "$" not in r]
            for resource in literal[:3]:
                found += [(a, resource) for a in statement.actions if "*" not in a]
    return found


def probes_of(
    plan: PersonPlan, inputs: Inputs, graph: Sequence[tuple[str, str]]
) -> list[tuple[str, str, str]]:
    """``(container, action, resource)`` asked for ``plan``'s person."""
    found: list[tuple[str, str, str]] = [("", a, r) for a, r in _platform_probes(inputs)]
    found += [("", a, r) for a, r in graph]
    for container in sorted(plan.containers(inputs)):
        found += [(container, a, r) for a, r in _nexus_probes(container)]
        if is_workspace_container(container):
            found += [(container, a, r) for a, r in _workspace_probes(container, inputs)]
    return found


Decisions = dict[tuple[str, str, str, str], bool]


def decisions(
    iam: Any,
    plans: Mapping[str, PersonPlan],
    inputs: Inputs,
    graph: Sequence[tuple[str, str]],
) -> Decisions:
    """What ``iam`` decides for each person, as Nexus asks it (``api`` on their
    behalf): ``(principal, container, action, resource) -> allowed``."""
    found: Decisions = {}
    for principal_id, plan in sorted(plans.items()):
        probes = probes_of(plan, inputs, graph)
        by_action: dict[str, list[str]] = {}
        for _container, action, resource in probes:
            by_action.setdefault(action, []).append(resource)
        context = CallContext(
            principal=service_account("api"),
            on_behalf_of=Principal(id=principal_id, kind="user"),
        )
        allowed: set[tuple[str, str]] = set()
        with use_call_context(context):
            for action, resources in by_action.items():
                unique = list(dict.fromkeys(resources))
                allowed |= {(action, r) for r in iam.filter(action, unique).allowed}
        for container, action, resource in probes:
            found[(principal_id, container, action, resource)] = (action, resource) in allowed
    return found


# -- classifying ----------------------------------------------------------------------


def _deletes(action: str) -> bool:
    name = action.removeprefix("nexus:")
    return any(
        spec.name == name and (spec.owner_only or spec.deletes) for spec in NEXUS_CATALOG.actions
    )


def reason_of(
    plan: PersonPlan, container: str, action: str, resource: str, after: bool, inputs: Inputs
) -> str:
    """Why one decision of ``plan``'s person changed (a key of ``REASONS``)."""
    org = org_of(container) if container else None
    if container in plan.default_admin_of:
        return "default_admin"
    if plan.platform_admin:
        return "platform_admin"
    if action.startswith("model_registry:"):
        return "model_sets"
    if org and is_org_container(container) and org in plan.org_roles_removed:
        return "org_member_role"
    if not after and action.startswith("nexus:") and _deletes(action):
        return "owners_lose_delete"
    if action.startswith("triple_store:"):
        return "shared_graphs"
    if org and org in plan.org_admin_of:
        return "org_admins"
    role = plan.roles.get(container)
    if after and role == "viewer" and plan.level == MEMBER:
        return "level_global"
    if action in RUN_ACTIONS and not after and container not in plan.admin_of:
        return "members_lose_workflows"
    if (
        action == USE_FEATURE
        and after
        and resource.endswith("/nexus:feature/datasets")
        and plan.level == MEMBER
    ):
        return "members_gain_datasets"
    service = action.partition(":")[0]
    if service in inputs.universe.declared or (
        service not in ("nexus", "module", "triple_store", "model_registry")
        and f"/{service}:" in resource
    ):
        return "module_actions"
    if action == USE_FEATURE and not after and plan.level == VIEWER:
        return "viewer_features"
    if action == USE_FEATURE:
        return "level_features"
    if action.startswith(f"{module_scopes.SERVICE}:"):
        return "level_instances"
    return "unexplained"


def changes_of(
    before: Decisions, after: Decisions, plans: Mapping[str, PersonPlan], inputs: Inputs
) -> list[Change]:
    """Every decision that changed, grouped by person, container, direction and
    reason."""
    grouped: dict[tuple[str, str, str, str], Change] = {}
    for key in sorted(set(before) | set(after)):
        was, now = before.get(key, False), after.get(key, False)
        if was == now:
            continue
        principal_id, container, action, resource = key
        plan = plans[principal_id]
        reason = reason_of(plan, container, action, resource, now, inputs)
        kind = "widening" if now else "narrowing"
        label, intended = REASONS[reason]
        change = grouped.setdefault(
            (principal_id, container, kind, reason),
            Change(plan.user_id, principal_id, container, kind, reason, label, intended),
        )
        change.what.append(f"{action} on {resource}")
    return list(grouped.values())


def merged_changes(planned: Sequence[Change], found: Sequence[Change]) -> list[Change]:
    """An interrupted move's report (``planned``, from the state before it) with what
    the start finishing it found: a decision already reported keeps its first
    report."""
    seen = {(c.principal_id, c.container, w) for c in planned for w in c.what}
    merged = [Change(**asdict(c)) for c in planned]
    for change in found:
        rest = [w for w in change.what if (change.principal_id, change.container, w) not in seen]
        if rest:
            merged.append(Change(**{**asdict(change), "what": rest}))
    return merged


# -- the move -------------------------------------------------------------------------


@dataclass
class Trial:
    """The move tried on a copy of IAM: its report, and what the copy decides after."""

    report: Report
    plans: dict[str, PersonPlan]
    graph: list[tuple[str, str]]
    after: Decisions
    levels: Levels
    copy: Any = None


def _levels(iam: Any) -> Levels:
    levels = find_levels(iam)
    if levels is None:
        with as_service_account("api"):
            levels = LEVELS.get(iam)
    return levels


def trial(iam: Any, inputs: Inputs) -> Trial:
    """The move on a copy of ``iam`` (``shadow_iam``), in IAM's thread: the report
    is the copy's decisions against ``iam``'s, classified. ``AccessModelStop`` when
    the copy refuses the plan. ``iam`` is not changed."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.shadow_iam import shadow_of

    levels = _levels(iam)
    copy = shadow_of(iam)
    try:
        tried = apply(copy, inputs, levels, dry_run=True)
    except AccessModelStop:
        raise
    except Exception as exc:  # noqa: BLE001 - whatever the copy refuses stops the move
        raise AccessModelStop(f"the plan failed on a copy of IAM: {exc!r}") from exc
    graph = _graph_probes(copy, tried.graph_policies)
    before = decisions(iam, tried.plans, inputs, graph)
    after = decisions(copy, tried.plans, inputs, graph)
    report = tried.report
    report.changes = changes_of(before, after, tried.plans, inputs)
    return Trial(report, tried.plans, graph, after, levels, copy)


def apply_tried(
    iam: Any, inputs: Inputs, tried: Trial
) -> tuple[dict[str, DefaultsRecord], list[str]]:
    """The move ``tried`` made on ``iam`` itself, in IAM's thread; then ``iam``'s
    decisions compared with the copy's. Returns the records to write and the
    decisions that differ from the copy's."""
    done = apply(iam, inputs, tried.levels, dry_run=False)
    platform_files.sync_platform_files(iam)
    real = decisions(iam, tried.plans, inputs, tried.graph)
    unverified = [
        f"{key}: {real[key]} (the copy: {tried.after.get(key)})"
        for key in sorted(real)
        if tried.after.get(key) != real[key]
    ][:200]
    return done.records, unverified


def merged_report(planned: Report | None, found: Report) -> Report:
    """The report of a move: ``found`` (this start's trial), or, for a move a start
    began and did not finish, the report it kept (``planned``, from the state before
    it) with what this start found besides."""
    if planned is None:
        return found
    merged = Report.from_dict(planned.to_dict())
    merged.changes = merged_changes(planned.changes, found.changes)
    return merged


# -- Nexus's side ---------------------------------------------------------------------


async def _recorded(db: AsyncSession, name: str) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_names import recorded

    return await recorded(db, name)


async def _has_table(db: AsyncSession, name: str) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: sql_inspect(sync).has_table(name))


async def read_inputs(
    db: AsyncSession, *, universe: Universe | None = None, settings: Any = None
) -> Inputs:
    """Nexus's organizations, workspaces, records, who was invited to an
    organization, the deployment's choices and the modules' items."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        enabled_features,
        read_nexus,
    )

    orgs, workspaces = await read_nexus(db)
    records = {r.container: r for r in await SqlDefaultsStore(db).all()}
    users = {
        str(row[0]): str(row[1] or "").strip().lower()
        for row in (await db.execute(text("SELECT id, email FROM users"))).all()
    }
    by_email = {email: user for user, email in users.items() if email}
    invited: set[tuple[str, str]] = set()
    if await _has_table(db, "invitations"):
        rows = await db.execute(
            text(
                "SELECT organization_id, org_role, accepted_user_id, email, status "
                "FROM invitations WHERE organization_id IS NOT NULL AND org_role IS NOT NULL"
            )
        )
        for org_id, _role, accepted, email, status in rows.all():
            if status == "revoked":
                continue
            user = str(accepted) if accepted else by_email.get(str(email or "").strip().lower())
            if user:
                invited.add((user, str(org_id)))
    if settings is None:
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

        settings = live_settings()
    migration = getattr(settings, "migration", None)
    email = getattr(migration, "default_workspace_admin", None) if migration else None
    email = str(email).strip().lower() if email else None
    default_admin = by_email.get(email) if email else None
    models = getattr(settings, "models", None)
    member_models = tuple(getattr(models, "member_set", None) or ()) if models else ()
    flags = getattr(settings, "feature_flags", None)
    if flags is not None:
        from naas_abi.apps.nexus.apps.api.app.core.feature_flags import enabled_feature_catalog

        features = tuple(enabled_feature_catalog(flags))
    else:
        features = tuple(enabled_features())
    inputs = Inputs(
        orgs=orgs,
        workspaces=workspaces,
        records=records,
        org_invited=invited,
        default_admin=default_admin,
        default_admin_email=email,
        enabled_features=features,
        universe=universe if universe is not None else await engine_universe(),
        member_models=member_models,
    )
    if email and default_admin is None:
        _log.warning(
            "nexus_config.migration.default_workspace_admin names %s, whom Nexus does not "
            "know: workspaces with no admin are listed instead",
            email,
        )
    return inputs


async def engine_universe() -> Universe:
    """The module items the engine lists (``modules/scopes.gather``) and those IAM's
    policies name: what a ceiling's wildcard of every module stood for."""
    from naas_abi.apps.nexus.apps.api.app.services.modules import scopes

    unavailable: set[str] = set()
    try:
        modules = await scopes.gather(unavailable)
    except Exception:  # noqa: BLE001 - the policies' names alone, named in the log
        _log.exception("The modules' items could not be listed: the policies name them")
        modules = []
    found: dict[str, set[Item]] = {kind: set() for kind in SECTIONS}
    declared: set[str] = set()
    for entry in modules:
        for kind in SECTIONS:
            for item in entry.get(kind) or ():
                found[kind].add((str(entry["module"]), str(item["name"])))
        if entry.get("declared"):
            declared.add(str(entry["declared"]["service"]))
    if unavailable:
        _log.warning(
            "Listing the modules' %s failed: the policies name them", ", ".join(unavailable)
        )
    return Universe(**{k: frozenset(v) for k, v in found.items()}, declared=frozenset(declared))


def named_universe(iam: Any) -> Universe:
    """The module items IAM's policies name one by one (an offer, a Deny of another
    workspace's agents, a customer's grant) and the declared catalogs' services."""
    found: dict[str, set[Item]] = {kind: set() for kind in SECTIONS}
    for policy in _pages(iam.list_policies):
        for statement in policy.document.statements:
            for resource in statement.resources:
                tail = resource.rpartition(f"{module_scopes.SERVICE}:")[2]
                if tail == resource:
                    continue
                parsed = _module_pattern(f"{_MODULE_PREFIX}{tail}")
                if parsed and parsed[1] != "*" and parsed[2] != WHOLE_MODULE and parsed[0] != "*":
                    found[parsed[0]].add((parsed[1], parsed[2]))
    catalogs = [c for c in iam.list_catalogs() if c.module]
    actions = {
        (f"{c.service}:{a.name}", a.resource_types[0])
        for c in catalogs
        for a in c.actions
        if a.resource_types
    }
    return Universe(
        **{k: frozenset(v) for k, v in found.items()},
        declared=frozenset(c.service for c in catalogs),
        declared_actions=frozenset(actions),
    )


async def convert_drive_flags(
    iam: Any, db: AsyncSession, *, apply: bool = True
) -> list[dict[str, Any]]:
    """The drive flags the holding table kept, converted by Platform Files
    (``platform_files.convert_legacy_drive_flags``, #1590), which owns that table and
    drops it: its rows (workspace, flag, action, detail). ``apply=False``: the report
    alone, nothing changed, the table kept."""
    changes = await platform_files.convert_legacy_drive_flags(iam, db, apply=apply)
    return [asdict(change) for change in changes]


async def _planned(db: AsyncSession) -> Report | None:
    row = (
        await db.execute(
            text("SELECT report FROM iam_migrations WHERE name = :n"), {"n": PLANNED_NAME}
        )
    ).first()
    if row is None or not row[0]:
        return None
    try:
        return Report.from_dict(json.loads(row[0]))
    except (TypeError, ValueError):
        _log.warning("The planned access move's report could not be read: reported anew")
        return None


async def _keep(db: AsyncSession, name: str, report: Report) -> None:
    await db.execute(text("DELETE FROM iam_migrations WHERE name = :n"), {"n": name})
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {"n": name, "at": datetime.now(UTC).replace(tzinfo=None), "r": report.to_json()},
    )


def log_report(report: Report) -> None:
    for line in report.lines():
        _log.info(line)
    for change in report.unexplained():
        _log.warning(
            "Access move: %s's access changed at %s for no reason the model gives: %s",
            change.user_id,
            change.container or "the platform",
            "; ".join(change.what[:5]),
        )
    for line in report.unverified[:20]:
        _log.error("Access move: IAM decides otherwise than its copy did: %s", line)


async def migrate_access(
    db: AsyncSession,
    *,
    dry_run: bool = False,
    force: bool = False,
    universe: Universe | None = None,
    settings: Any = None,
    iam: Any = None,
) -> Report | None:
    """The access move (see the module), once: None when ``iam_migrations`` records
    it (``force``: run anyway) or it waits for ``container_defaults_v1``. A dry run
    reports and writes nothing. Run under the moves' lock (``main``)."""
    if not force and not dry_run and await _recorded(db, MIGRATION_NAME):
        return None
    for before in AFTER:
        if not await _recorded(db, before):
            _log.warning("The access move waits for %s", before)
            return None
    iam = iam if iam is not None else runtime.iam()
    inputs = await read_inputs(db, universe=universe, settings=settings)
    named = await run_in_threadpool(lambda: _as_engine(lambda: named_universe(iam)))
    inputs.universe = inputs.universe.merged(named)
    planned = None if dry_run else await _planned(db)
    try:
        tried = await run_in_threadpool(lambda: trial(iam, inputs))
    except AccessModelStop as stop:
        _log.error("The access move stopped, nothing changed or recorded: %s", stop)
        return None
    report = merged_report(planned, tried.report)
    report.dry_run = dry_run
    if dry_run:
        try:
            report.drive_flags = await convert_drive_flags(tried.copy, db, apply=False)
        except Exception as exc:  # noqa: BLE001 - reported; the rest of the report stands
            _log.exception("The drive flags could not be read")
            report.notes.append(f"The drive flags could not be read: {exc}")
        log_report(report)
        return report
    # The whole move's report, kept before the real IAM changes: a start that
    # finishes it reports the move from the state before it.
    if planned is None:
        await _keep(db, PLANNED_NAME, report)
        await db.commit()
    try:
        records, unverified = await run_in_threadpool(lambda: apply_tried(iam, inputs, tried))
    except Exception:  # noqa: BLE001 - nothing recorded: the next start finishes it
        _log.exception("The access move stopped half way: the next start finishes it")
        await db.rollback()
        return None
    store = SqlDefaultsStore(db)
    for record in records.values():
        await store.put(record)
        CONTAINER_DEFAULTS.remember(record)
    CONTAINER_DEFAULTS.forget_grouped()
    report.applied = True
    report.unverified = unverified
    try:
        report.drive_flags = await convert_drive_flags(iam, db) or report.drive_flags
    except Exception as exc:  # noqa: BLE001 - reported; the people's move stands
        _log.exception("The drive flags were not converted")
        report.notes.append(f"The drive flags were not converted: {exc}")
    await _keep(db, MIGRATION_NAME, report)
    await db.execute(text("DELETE FROM iam_migrations WHERE name = :n"), {"n": PLANNED_NAME})
    await db.commit()
    log_report(report)
    return report


def _as_engine(work: Any) -> Any:
    with as_service_account("engine"):
        return work()


async def migrate_from_cli(
    database_url: str,
    services: Any,
    *,
    settings: Any = None,
    universe: Universe | None = None,
) -> Report | None:
    """``abi iam migrate-access --dry-run``: the report of the move as it would be
    now, written nowhere (None when it waits for ``container_defaults_v1`` or stops:
    logged). ``services`` are the engine's the CLI opened, ``settings`` the project's
    ``nexus_config`` (the default admin, the model set, the features). The modules'
    items are those IAM's policies name (the CLI loads no module)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    previous = runtime.configure(lambda: services.iam)
    try:
        async with sessions() as db:
            return await migrate_access(
                db,
                dry_run=True,
                universe=universe if universe is not None else Universe(),
                settings=settings,
                iam=services.iam,
            )
    finally:
        runtime.configure(previous)
        await engine.dispose()


__all__ = [
    "AccessModelStop",
    "Change",
    "Inputs",
    "MIGRATION_NAME",
    "PLANNED_NAME",
    "REASONS",
    "Report",
    "Universe",
    "ceiling_offer",
    "decisions",
    "migrate_access",
    "migrate_from_cli",
    "trial",
]
