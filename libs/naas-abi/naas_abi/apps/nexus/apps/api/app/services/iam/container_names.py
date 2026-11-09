"""The move of IAM's stored names to container paths, once, at start.

Before container paths a name was ``abi:<org>:<ws>:<service>:<type>/<id>``: the
org and the workspace were Nexus's, fixed in the grammar. Now a name is a path
of containers, and Nexus's organizations and workspaces are containers of its
``nexus`` catalog (core ``services/iam/AGENTS.md``, "Resource names",
"Migrating an existing install"). IAM knows no organization, so the old fields
are Nexus's to read: this move registers every organization and workspace as a
container, then has IAM rewrite every stored name with ``LegacyNames`` in one
transaction (``iam.rewrite_names``): policy documents and their ``${scope}:``
patterns, owners, attachments, placements, keys' narrowing, manifests, pending
grants and IdP bindings (groups and their attachments).

Nobody gains or loses access: each old pattern becomes the patterns that name,
in the new grammar, exactly the resources it named, the organization and the
workspace themselves included:

* ``abi:-:-:R`` is ``abi:R``; ``abi:%2A:%2A:iam:...`` (the platform's own) is
  ``abi:iam:...``; ``abi:O:-:R`` is ``<O>/R``; ``abi:O:W:R`` is ``<W>/R`` (``W``
  the workspace's container, in its organization or at the platform);
  ``abi:O:%2A:...`` (an org-wide attachment) is named at ``<O>``;
* a field ``*`` is every container of its level: ``abi:*:*:R`` is
  ``names.anywhere(R)``, ``abi:O:*:R`` is ``<O>/R`` and ``<O>/*/R``; any other
  wildcard in a field is each organization or workspace it matched;
* the singletons ``nexus:organization/-`` (at an org) and ``nexus:workspace/-``
  (at a workspace) are the containers themselves, for the actions on those
  types; ``nexus:CreateWorkspace``, which was decided on the organization, is
  decided on ``<O>/nexus:workspace/*``, and ``nexus:CreateOrganization`` on
  ``abi:nexus:organization/*``;
* a pattern of the platform's or an organization's own level is cut to the types
  that are no container there (``*`` crosses into what a container holds now),
  each named: a service a later version adds is not reached (the report says so).

Scopes: ``abi:O:W`` is the workspace's container, ``abi:O:-`` the organization's,
``abi:O:*`` below the organization's, ``abi:-:-`` the platform (``abi:``); the
owner ``abi:_none:-`` (what the moves made for the workspaces in none) is the
platform too, the scope (an attachment there named nothing) is left as it was. A
scope or a pattern naming an organization or a workspace Nexus does not know any
more is left as it was: it decides nothing (``names.UNRESOLVED``), never more.

Everything already a path is kept, so the move may run again. It runs after the
moves that still write the old grammar (``policy_tree.AFTER`` and the sets'),
and until it is recorded Nexus refuses every module scope and feature
(``authz.upgrading``).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import (
    ContainerRecord,
    LegacyPlacement,
    NameRewriter,
)
from naas_abi_core.services.iam.names import (
    PLATFORM,
    anywhere,
    below,
    container_name,
    has_wildcard,
    is_old_scope,
    matches,
)
from naas_abi_core.services.iam.policy import MAX_PATTERNS, MAX_STATEMENTS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

MIGRATION_NAME = "container_names_v1"
# The moves that write the old grammar run first.
AFTER = ("policy_tree_v1",)
SERVICE = "nexus"
ORGANIZATION = "organization"
WORKSPACE = "workspace"
# The org of a workspace in no organization, in the old grammar.
NO_ORG = "_none"
# The org-wide marker of the old grammar (an org-wide attachment's workspace),
# and the platform's own (``abi:%2A:%2A:iam:...``).
EVERY = "%2A"
_ORG_SINGLETON = f"{SERVICE}:{ORGANIZATION}/-"
_WORKSPACE_SINGLETON = f"{SERVICE}:{WORKSPACE}/-"
_CREATE_WORKSPACE = f"{SERVICE}:CreateWorkspace"
_CREATE_ORGANIZATION = f"{SERVICE}:CreateOrganization"
_OLD_SCOPE_PREFIX = "${scope}:"
_SERVICE = re.compile(r"^[a-z][a-z0-9_]*$")
_STEP = re.compile(r"[a-z][a-z0-9_]*:[a-z][a-z0-9_]*/")

# Set while a start has the move to make: Nexus refuses module scopes and features.
_pending = False


def pending() -> bool:
    """Whether the names still wait to be rewritten."""
    return _pending


def set_pending(value: bool) -> None:
    global _pending
    _pending = value


class UpgradeStop(Exception):
    """A name the move cannot rewrite exactly: nothing is recorded."""


# -- what a pattern becomes ------------------------------------------------------

# What a rewritten pattern is for: every action of its statement (``None``), the
# actions on the organization or the workspace type (the container itself), or
# the one create action decided elsewhere now.
Kind = str | None


@dataclass(frozen=True)
class Place:
    """An org and a workspace field of the old grammar, and the container they
    named (``abi:`` for the platform)."""

    org: str
    workspace: str
    container: str
    # The level holds containers (the platform holds organizations and workspaces
    # in none, an organization its workspaces): a pattern there is cut to the
    # types that are none.
    holds_containers: bool
    # The singleton that is this level's container itself, if any.
    singleton: str | None = None


def derive(glob: str, literal: str) -> set[str]:
    """The globs ``x`` such that ``literal + x`` matches ``glob`` exactly when
    ``x`` matches one of them (a glob's derivative by a literal prefix), but the
    empty one."""

    def close(states: Iterable[int]) -> set[int]:
        found: set[int] = set()
        stack = list(states)
        while stack:
            index = stack.pop()
            if index in found:
                continue
            found.add(index)
            if index < len(glob) and glob[index] == "*":
                stack.append(index + 1)
        return found

    states = close({0})
    for char in literal:
        after: set[int] = set()
        for index in states:
            if index == len(glob):
                continue
            current = glob[index]
            if current == "*":
                after.add(index)
            elif current == "?" or current == char:
                after.add(index + 1)
        states = close(after)
        if not states:
            return set()
    # An empty rest names no resource (no id is empty): left out.
    return {glob[index:] for index in states} - {""}


@dataclass
class LegacyNames(NameRewriter):
    """Nexus's reading of the names before container paths (see the module)."""

    orgs: Sequence[str]
    # Each workspace's org, None for a workspace in no organization.
    workspaces: Mapping[str, str | None]
    catalogs: CatalogRegistry
    notes: list[str] = field(default_factory=list)

    # -- containers ----------------------------------------------------------------

    def org_container(self, org: str) -> str:
        return container_name(SERVICE, ORGANIZATION, org)

    def workspace_container(self, workspace: str) -> str:
        org = self.workspaces[workspace]
        parent = self.org_container(org) if org is not None else PLATFORM
        return container_name(SERVICE, WORKSPACE, workspace, parent=parent)

    def containers(self) -> Sequence[ContainerRecord]:
        found = [ContainerRecord(SERVICE, ORGANIZATION, org) for org in self.orgs]
        found += [
            ContainerRecord(
                SERVICE,
                WORKSPACE,
                workspace,
                self.org_container(org) if org is not None else PLATFORM,
            )
            for workspace, org in sorted(self.workspaces.items())
        ]
        return found

    def places(self) -> list[Place]:
        """Every org and workspace field pair a stored name may hold."""
        found = [
            Place("-", "-", PLATFORM, True),
            Place(EVERY, EVERY, PLATFORM, True),
        ]
        for org in self.orgs:
            container = self.org_container(org)
            found.append(Place(org, "-", container, True, _ORG_SINGLETON))
            found.append(Place(org, EVERY, container, True))
        for workspace, org in sorted(self.workspaces.items()):
            found.append(
                Place(
                    org or NO_ORG,
                    workspace,
                    self.workspace_container(workspace),
                    False,
                    _WORKSPACE_SINGLETON,
                )
            )
        return found

    # -- scopes and owners ------------------------------------------------------------

    def _scope(self, scope: str, *, owner: bool) -> str:
        if not is_old_scope(scope):
            return scope
        org, workspace = scope[len("abi:") :].split(":")
        if (org, workspace) == ("-", "-"):
            return PLATFORM
        if workspace == "-" and org in self.orgs:
            return self.org_container(org)
        if workspace == "*" and org in self.orgs and not owner:
            return below(self.org_container(org))
        if workspace in self.workspaces and (self.workspaces[workspace] or NO_ORG) == org:
            return self.workspace_container(workspace)
        self.notes.append(
            f"{scope} names no organization or workspace Nexus knows: left as it "
            "was, it decides nothing"
        )
        return scope

    def scope(self, scope: str | None) -> str | None:
        return None if scope is None else self._scope(scope, owner=False)

    def owner(self, owner: str) -> str:
        if owner == f"abi:{NO_ORG}:-":
            # What the moves made for the workspaces in none, owned by their "org":
            # those workspaces are at the platform now, and only its admins
            # managed that level (nobody holds a role there).
            return PLATFORM
        return self._scope(owner, owner=True)

    def placement(self, placement: LegacyPlacement) -> str:
        return self._scope(placement.scope, owner=True)

    # -- patterns ---------------------------------------------------------------------

    def is_old_pattern(self, pattern: str) -> bool:
        """Whether ``pattern`` is written in the grammar before container paths:
        ``${scope}:``, or ``abi:`` and an org field (three fields before the first
        "/", or a first field no service is named: ``-``, ``%2A``, an org id)."""
        if pattern.startswith(_OLD_SCOPE_PREFIX):
            return True
        if not pattern.startswith("abi:"):
            return False
        fields = pattern[len("abi:") :].split("/", 1)[0].split(":")
        if len(fields) >= 3:
            return True
        first = fields[0]
        return len(fields) == 2 and (
            first in ("-", EVERY, NO_ORG)
            or first in self.orgs
            or not (has_wildcard(first) or _SERVICE.match(first))
        )

    def pattern(self, pattern: str) -> list[tuple[Kind, str]]:
        """What an absolute pattern of the old grammar names now: patterns, each
        with the kind of actions it is for."""
        if not self.is_old_pattern(pattern):
            return [(None, pattern)]
        if pattern.startswith(_OLD_SCOPE_PREFIX):
            return self._scoped(pattern[len(_OLD_SCOPE_PREFIX) :])
        fields = pattern[len("abi:") :].split(":", 2)
        if len(fields) == 3 and (fields[0], fields[1]) == ("*", "*"):
            return self._everywhere(fields[2])
        if len(fields) == 3 and fields[1] == "*" and fields[0] in self.orgs:
            return self._below_org(fields[0], fields[2])
        found: list[tuple[Kind, str]] = []
        for place in self.places():
            for rest in sorted(derive(pattern, f"abi:{place.org}:{place.workspace}:")):
                found += self._at(place, rest)
        if any(has_wildcard(f) for f in fields[:2]):
            self.notes.append(
                f"{pattern}: its wildcard fields are spelled out for the organizations "
                "and workspaces of today; one made later is not reached"
            )
        return _unique(found)

    def _everywhere(self, rest: str) -> list[tuple[Kind, str]]:
        """``abi:*:*:R``: R at every level, the containers themselves included."""
        found: list[tuple[Kind, str]] = [(None, p) for p in anywhere(rest)]
        found += self._creates(rest, "abi:*/", "abi:")
        return _unique(found)

    def _below_org(self, org: str, rest: str) -> list[tuple[Kind, str]]:
        """``abi:O:*:R``: R at the organization and in each of its workspaces."""
        container = self.org_container(org)
        found: list[tuple[Kind, str]] = []
        if _rest_matches(rest, _ORG_SINGLETON):
            found.append((ORGANIZATION, container))
        if _rest_matches(rest, _WORKSPACE_SINGLETON):
            found.append((WORKSPACE, f"{container}/{SERVICE}:{WORKSPACE}/*"))
        if rest.startswith("*"):
            # Every level of the organization: what it holds, at any depth.
            found.append((None, f"{container}/{rest}"))
        elif _STEP.match(rest):
            found += self._cut(container, rest)
            found.append((None, f"{container}/*/{rest}"))
        else:
            found += self._cut(container, rest)
            found += [
                (None, f"{self.workspace_container(w)}/{rest}")
                for w, o in sorted(self.workspaces.items())
                if o == org
            ]
            self.notes.append(f"{rest} in {container}: spelled out for its workspaces of today")
        found += self._creates(rest, f"{container}/", None)
        return _unique(found)

    def _at(self, place: Place, rest: str) -> list[tuple[Kind, str]]:
        """``rest`` (a glob over ``<service>:<type>/<id>``) at one old place."""
        if not rest or rest.count(":") > 1:
            return []  # one ":" in a rest: a wildcard that spanned fields names none
        if (place.org, place.workspace) == (EVERY, EVERY) or (
            place.workspace == EVERY and place.org != "-"
        ):
            # The platform's own policies, groups and attachments, and org-wide
            # attachments: named at the platform, or at the organization.
            return [(None, f"{_prefix(place.container)}{r}") for r in _iam_owned(rest)]
        found: list[tuple[Kind, str]] = []
        if place.singleton is not None and _rest_matches(rest, place.singleton):
            kind = ORGANIZATION if place.singleton == _ORG_SINGLETON else WORKSPACE
            found.append((kind, place.container))
        if place.holds_containers:
            found += self._cut(place.container, rest)
            if place.container == PLATFORM:
                found += self._creates(rest, None, "abi:")
            else:
                found += self._creates(rest, f"{place.container}/", None)
        else:
            step = _STEP.match(rest)
            named = tuple(step.group(0)[:-1].split(":")) if step else None
            if named not in self._container_types():
                found.append((None, f"{_prefix(place.container)}{rest}"))
        return found

    def _creates(
        self, rest: str, in_org: str | None, at_platform: str | None
    ) -> list[tuple[Kind, str]]:
        """The create actions that moved: CreateWorkspace was decided on the
        organization singleton, CreateOrganization on the platform's."""
        found: list[tuple[Kind, str]] = []
        if in_org is not None and _rest_matches(rest, _ORG_SINGLETON):
            found.append((_CREATE_WORKSPACE, f"{in_org}{SERVICE}:{WORKSPACE}/*"))
        if at_platform is not None and _rest_matches(rest, _ORG_SINGLETON):
            found.append((_CREATE_ORGANIZATION, f"{at_platform}{SERVICE}:{ORGANIZATION}/*"))
        return found

    def _container_types(self) -> set[tuple[str, str]]:
        return set(self.catalogs.container_types())

    def _cut(self, container: str, rest: str) -> list[tuple[Kind, str]]:
        """``rest`` at a level that holds containers, cut to the types that are
        none: each pattern stays at that level, as the old one did."""
        prefix = _prefix(container)
        containers = self._container_types()
        step = _STEP.match(rest)
        if step is not None:
            service, type_name = step.group(0)[:-1].split(":")
            if (service, type_name) in containers:
                return []  # only its singleton (above) was at that level
            return [(None, prefix + rest)]
        found: list[tuple[Kind, str]] = []
        services = {s for s, _t in containers}
        for catalog in self.catalogs.all():
            if catalog.service not in services:
                for derived in sorted(derive(rest, f"{catalog.service}:")):
                    if ":" not in derived:
                        found.append((None, f"{prefix}{catalog.service}:{derived}"))
                continue
            for resource_type in catalog.resource_types:
                if resource_type.container:
                    continue
                literal = f"{catalog.service}:{resource_type.name}/"
                for derived in sorted(derive(rest, literal)):
                    if ":" not in derived:
                        found.append((None, f"{prefix}{literal}{derived}"))
        if has_wildcard(rest.split(":", 1)[0]):
            where = "${scope}" if container == _SCOPE_MARK else container
            self.notes.append(
                f"{rest} at {where}: spelled out for the services of today; a "
                "service added later is not reached"
            )
        return found

    def _scoped(self, rest: str) -> list[tuple[Kind, str]]:
        """``${scope}:R``: the same at whatever scope the policy is attached, the
        container itself for its singleton, cut to the types that are no
        container (at an organization ``*`` would now reach its workspaces)."""
        found: list[tuple[Kind, str]] = []
        if _rest_matches(rest, _ORG_SINGLETON):
            found.append((ORGANIZATION, "${scope}"))
        if _rest_matches(rest, _WORKSPACE_SINGLETON):
            found.append((WORKSPACE, "${scope}"))
        found += [
            (kind, "${scope}/" + pattern.removeprefix(_SCOPE_MARK + "/"))
            for kind, pattern in self._cut(_SCOPE_MARK, rest)
        ]
        found += self._creates(rest, "${scope}/", None)
        return _unique(found)

    # -- statements and documents -------------------------------------------------------

    def _actions_of(self, patterns: Sequence[str], kind: str) -> list[str]:
        """The registered actions ``patterns`` match that a kind of pattern is for."""
        if kind in (_CREATE_WORKSPACE, _CREATE_ORGANIZATION):
            return [kind] if any(matches(p, kind) for p in patterns) else []
        catalog = self.catalogs.get(SERVICE)
        if catalog is None:
            return []
        return [
            catalog.qualified(a.name)
            for a in catalog.actions
            if kind in a.resource_types
            and not a.creates
            and any(matches(p, catalog.qualified(a.name)) for p in patterns)
        ]

    def _types_of(self, actions: Sequence[str]) -> set[tuple[str, str]] | None:
        """The resource types the actions are on; None when one is a wildcard or
        unknown (then every type may be)."""
        types: set[tuple[str, str]] = set()
        for action in actions:
            service, _, name = action.partition(":")
            catalog = self.catalogs.get(service)
            spec = catalog.action(name) if catalog is not None and name else None
            if has_wildcard(action) or spec is None:
                return None
            types.update((service, t) for t in spec.resource_types)
        return types

    def statement(self, raw: Mapping[str, Any]) -> list[dict[str, Any]]:
        resources = [r for r in raw.get("resources", ()) if isinstance(r, str)]
        actions = [a for a in raw.get("actions", ()) if isinstance(a, str)]
        if not any(self.is_old_pattern(r) for r in resources):
            return [dict(raw)]
        plain: list[str] = []
        special: dict[str, list[str]] = {}
        for resource in resources:
            for kind, pattern in self.pattern(resource):
                if kind is None:
                    plain.append(pattern)
                else:
                    special.setdefault(kind, []).append(pattern)
        types = self._types_of(actions)
        if types is not None:
            # Only the types its actions are on: the rest names nothing for them.
            plain = [p for p in plain if _on_types(p, types)]
        found: list[dict[str, Any]] = []
        base = {k: v for k, v in raw.items() if k not in ("resources", "actions", "sid")}
        sid = raw.get("sid")
        for part, chunk in enumerate(_chunks(_dedup(plain))):
            found.append(_statement(base, actions, chunk, sid, part))
        for kind, patterns in sorted(special.items()):
            kept = self._actions_of(actions, kind)
            if kept:
                for chunk in _chunks(_dedup(patterns)):
                    found.append(_statement(base, kept, chunk, sid, len(found)))
        if not found:
            # It named nothing that exists: kept as written, it still names nothing.
            return [dict(raw)]
        return found

    def statements(self, statements: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
        found: list[dict[str, Any]] = []
        for raw in statements:
            found += self.statement(raw)
        return found

    def document(self, document: Mapping[str, Any]) -> Mapping[str, Any]:
        statements = document.get("statements")
        if not isinstance(statements, list):
            return document
        rewritten = list(self.statements(statements))
        if rewritten == statements:
            return document
        if len(rewritten) > MAX_STATEMENTS:
            raise UpgradeStop(
                f"a policy would need {len(rewritten)} statements (more than {MAX_STATEMENTS})"
            )
        return {**document, "statements": rewritten}


# A stand-in for ``${scope}`` while a scoped pattern is cut.
_SCOPE_MARK = "abi:\x00scope"


def _prefix(container: str) -> str:
    return "abi:" if container == PLATFORM else f"{container}/"


_LAST_STEP = re.compile(r"(?:^abi:|/)([a-z][a-z0-9_]*):([^/:]*)")


def _on_types(pattern: str, types: set[tuple[str, str]]) -> bool:
    """Whether a pattern's last step may be one of ``types`` (a pattern with no
    literal step may be any)."""
    steps = _LAST_STEP.findall(pattern)
    if not steps:
        return True
    service, type_glob = steps[-1]
    return any(s == service and matches(type_glob or "*", t) for s, t in types)


def _rest_matches(rest: str, name: str) -> bool:
    return matches(rest, name)


def _iam_owned(rest: str) -> list[str]:
    """``rest`` cut to what ``%2A`` named: IAM's policies, groups, attachments."""
    found: list[str] = []
    for type_name in ("policy", "group", "attachment"):
        literal = f"iam:{type_name}/"
        found += [literal + d for d in sorted(derive(rest, literal)) if ":" not in d]
    return found


def _unique(found: list[tuple[Kind, str]]) -> list[tuple[Kind, str]]:
    return list(dict.fromkeys(found))


def _dedup(patterns: list[str]) -> list[str]:
    return list(dict.fromkeys(patterns))


def _chunks(patterns: list[str]) -> list[list[str]]:
    return [patterns[i : i + MAX_PATTERNS] for i in range(0, len(patterns), MAX_PATTERNS)]


def _statement(
    base: Mapping[str, Any],
    actions: Sequence[str],
    resources: Sequence[str],
    sid: Any,
    part: int,
) -> dict[str, Any]:
    found = dict(base)
    if isinstance(sid, str):
        found["sid"] = sid if part == 0 else f"{sid}{part + 1}"[:64]
    found["actions"] = list(actions)
    found["resources"] = list(resources)
    return found


# -- the move -------------------------------------------------------------------------------


@dataclass
class Report:
    counts: dict[str, int]
    notes: list[str]


async def recorded(db: AsyncSession, name: str) -> bool:
    return (
        await db.execute(text("SELECT 1 FROM iam_migrations WHERE name = :n"), {"n": name})
    ).first() is not None


async def refresh_pending(db: AsyncSession) -> bool:
    """Stop waiting for each move another API process has recorded since this
    one's start (whose own move failed, or waited for it): whether this process
    still refuses module scopes and features (``authz.upgrading``)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree

    if policy_tree.pending() and await recorded(db, policy_tree.MIGRATION_NAME):
        policy_tree.set_pending(False)
    if pending() and await recorded(db, MIGRATION_NAME):
        set_pending(False)
    return policy_tree.pending() or pending()


# The PostgreSQL advisory lock the start-up moves hold: a number of Nexus's own.
MOVES_LOCK = 0x4E58_4D4F_5645_5331


@asynccontextmanager
async def moves_lock(engine: AsyncEngine) -> AsyncIterator[None]:
    """Hold the start-up moves to one API process at a time. On PostgreSQL, a
    session advisory lock on a connection of its own: the other processes wait
    for it, then find each move recorded and skip it. SQLite has no lock between
    processes: an install on it runs one API process for the start that upgrades
    (``AGENTS.md``)."""
    if engine.dialect.name != "postgresql":
        yield
        return
    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MOVES_LOCK})
        try:
            yield
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MOVES_LOCK})


async def read_nexus(db: AsyncSession) -> tuple[list[str], dict[str, str | None]]:
    """Nexus's organizations, and each workspace's organization."""
    orgs = [str(row[0]) for row in (await db.execute(text("SELECT id FROM organizations"))).all()]
    workspaces = {
        str(row[0]): (str(row[1]) if row[1] else None)
        for row in (await db.execute(text("SELECT id, organization_id FROM workspaces"))).all()
    }
    known = set(orgs)
    return orgs, {w: (o if o in known else None) for w, o in workspaces.items()}


def rewrite(iam: Any, orgs: Sequence[str], workspaces: Mapping[str, str | None]) -> Report:
    """Register the containers and rewrite every stored name, as the engine."""
    with as_service_account("engine"):
        rewriter = LegacyNames(list(orgs), dict(workspaces), iam.catalogs)
        counts = iam.rewrite_names(rewriter)
    return Report(counts, list(dict.fromkeys(rewriter.notes)))


# The roles an organization's own role is held below it too (Nexus mirrors them).
_MIRRORED = ("builtin.owner", "builtin.admin")


async def role_data_pending(db: AsyncSession) -> bool:
    """Whether Nexus still keeps memberships IAM does not hold: the move of the
    role data (``bootstrap.migrate_role_data``) is not recorded, and there is
    something for it to move. The moves before container paths read the roles
    IAM holds, so they wait for it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import bootstrap

    if await recorded(db, bootstrap.MIGRATION_NAME):
        return False
    for query in (
        "SELECT 1 FROM organizations WHERE owner_id IS NOT NULL",
        "SELECT 1 FROM workspaces WHERE owner_id IS NOT NULL",
        "SELECT 1 FROM organization_members",
        "SELECT 1 FROM workspace_members",
    ):
        if (await db.execute(text(query + " LIMIT 1"))).first() is not None:
            return True
    return False


def mirror_old_org_wide(iam: Any) -> int:
    """Hold, in the grammar before container paths, the org-wide role
    (``abi:<org>:*``) each organization owner's and admin's own one
    (``abi:<org>:-``) brings: what the moves below read as reaching the
    organization's workspaces, as Nexus kept it before. Made as ``api`` for no
    user, which IAM takes the old grammar from. How many were missing."""
    made = 0
    with as_service_account("api"):
        held = {(a.policy_id, a.principal_id, a.scope) for a in iam.list_attachments()}
        for policy_id, principal_id, scope in sorted(held, key=lambda h: (h[0], h[1], h[2] or "")):
            if policy_id not in _MIRRORED or not is_old_scope(scope):
                continue
            org, workspace = (scope or "")[len("abi:") :].split(":")
            if workspace != "-" or org in ("-", NO_ORG):
                continue
            wide = f"abi:{org}:*"
            if (policy_id, principal_id, wide) not in held:
                iam.attach_policy(policy_id, principal_id, wide)
                made += 1
    return made


async def before_names(db: AsyncSession, moves: Callable[[], Awaitable[None]]) -> bool:
    """Run the moves written for the grammar before container paths (``moves``),
    unless the names are rewritten already. They read the roles IAM holds: while
    Nexus still keeps memberships IAM does not (``role_data_pending``), nothing
    runs and nothing is recorded, and False says so (an install that old upgrades
    through a version that moved them first). Org-wide mirrors missing are made
    first."""
    if await recorded(db, MIGRATION_NAME):
        return True
    if await role_data_pending(db):
        _log.error(
            "Nexus still keeps memberships IAM does not hold (the move of the role "
            "data, iam_roles_v1, is not recorded): the moves to container paths wait, "
            "and module scopes and features are refused. Upgrade through a version "
            "that moved the role data into IAM first (feat/permission-system)."
        )
        return False
    made = await run_in_threadpool(mirror_old_org_wide, runtime.iam())
    if made:
        _log.info("Org-wide roles of the old grammar given to %d owner(s) and admin(s)", made)
    await moves()
    return True


async def migrate_names(db: AsyncSession) -> Report | None:
    """Rewrite IAM's stored names, once (see the module). None when it did not run
    (done already, or waiting for the moves before it); ``pending()`` stays true
    until it is recorded."""
    if await recorded(db, MIGRATION_NAME):
        set_pending(False)
        return None
    set_pending(True)
    for before in AFTER:
        if not await recorded(db, before):
            _log.warning(
                "The names wait for %s: module scopes and features are refused until a "
                "start moves them",
                before,
            )
            return None
    orgs, workspaces = await read_nexus(db)
    try:
        report = await run_in_threadpool(rewrite, runtime.iam(), orgs, workspaces)
    except Exception:  # noqa: BLE001 - nothing recorded: refused until the next start
        _log.exception(
            "IAM's names were not rewritten to container paths: module scopes and "
            "features are refused until a start rewrites them"
        )
        return None
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at, report) VALUES (:n, :at, :r)"),
        {
            "n": MIGRATION_NAME,
            "at": datetime.now(UTC).replace(tzinfo=None),
            "r": json.dumps({"counts": report.counts, "notes": report.notes}),
        },
    )
    await db.commit()
    set_pending(False)
    for note in report.notes:
        _log.warning("Container paths: %s", note)
    return report
