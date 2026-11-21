"""Memberships: who works where, and at which level (#1585, levels as groups).

In an organization or a workspace whose defaults are groups (``container_defaults``,
``grouped``), a person holds nothing directly:

- **where**: "<W> workspace" (a membership group of W), "<O> people" (of O);
- **what**: their level, one choice applying everywhere: "Members" or "Viewers"
  (``levels``); and "<W> admins" / "<O> admins" for who administers W or O.

The role-based API (``grant``, ``revoke``, ``roles_of``…) is kept for its callers
(the people service's ``AccessGateway``, the routes) and is mapped onto the groups
(``grant``'s table). A role is read back from what IAM holds: a ``builtin.<role>``
attached to the person, or to one of their groups, at a scope, or at
``${my workspaces}`` (each of their membership containers, within the group's owner).

A container recorded before #1585 (its "<X> members" group) keeps the roles of
before: ``builtin.<role>`` attached to the user's principal at the organization's or
the workspace's container, an organization's owners and admins mirrored below it
(``<org container>/*``), until the access move (#1587) converts it.

A Nexus user the built-in login created holds IAM's user of issuer ``urn:abi:nexus``
(subject: its Nexus id); a user of an identity provider is its principal id
(``usr_…``) itself.

Reads run as ``api`` for no user, after the route authorized its caller with the
Nexus action (``ListWorkspaceMembers``). A change is checked as the caller (``api``
on their behalf: IAM's ``iam:AddGroupMember`` / ``iam:RemoveGroupMember`` on each
group, ``iam:DetachPolicy`` on each role of before), then the container's groups
are written as ``api`` for no user (the first membership of someone who belongs to
nothing yet is Nexus's to make: core "The first tie") and the level on the caller's
behalf (IAM's level-group rule decides it and audits it). Seeding and the admin of
a new organization or workspace are written as ``api`` for no user.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    DefaultsRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import LEVELS, MEMBER, VIEWER, Levels
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    ORGANIZATION,
    PLATFORM,
    SERVICE,
    WORKSPACE,
    is_org_container,
    is_workspace_container,
    org_below,
    org_container,
    org_of,
    workspace_container,
    workspace_of,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import (
    LEGACY_NEXUS_ISSUER,
    attachment_resource,
    group_resource,
)
from naas_abi_core.services.iam.names import is_membership_scope, within_owner
from starlette.concurrency import run_in_threadpool

_T = TypeVar("_T")
_PRINCIPAL_ID = re.compile(r"^usr_[0-9a-z]{26}$")

ROLE_NAMES = ("owner", "admin", "member", "viewer")
# Organization owners and admins reach every workspace of their organization
# (``services/iam/AGENTS.md``, "Org owners and admins reach every workspace"): the
# org role is also held below the organization (``<org container>/*``), which IAM
# reaches into every workspace. Members and viewers of an organization inherit
# nothing.
INHERITING_ROLES = ("owner", "admin")
_RANK = {name: len(ROLE_NAMES) - index for index, name in enumerate(ROLE_NAMES)}
_POLICY_OF = {name: f"builtin.{name}" for name in ROLE_NAMES}
# Who a held-check probe names (``Memberships._probe_held``): nobody who signs in.
_PROBE_PROVIDER = "nexus-check"
_PROBE_EMAIL = "held-check@invalid.example"


class MembershipDenied(PermissionError):
    """IAM refused a change of roles to the caller."""


class LastOrgAdminError(ValueError):
    """The change would leave the organization with no admin (an Org Admin, or an
    owner of before): 409."""

    def __init__(self, scope: str) -> None:
        super().__init__(f"{scope} keeps at least one admin")
        self.scope = scope

    def __str__(self) -> str:
        return "last_org_admin"


@dataclass(frozen=True)
class Member:
    user_id: str
    role: str
    principal_id: str
    since: datetime | None = None
    # Their level ("member", "viewer"), one choice for every container; None when
    # they are in no level group (a role of before, held directly).
    level: str | None = None


@dataclass(frozen=True)
class DirectoryEntry:
    """One person of an organization's directory: who holds a role at the
    organization's container, below it, or at one of its workspaces' containers.

    ``role``: their organization role (None: workspace access only, which grants
    nothing in the organization). ``source``: ``"organization"`` when they hold a
    role at (or below) the organization, else ``"workspace"``. ``workspace_ids``:
    the workspaces of the organization they hold a role in directly. ``org_wide``:
    they reach every workspace through their org role (an owner or admin)."""

    user_id: str
    principal_id: str
    role: str | None
    source: str
    workspace_ids: tuple[str, ...] = ()
    org_wide: bool = False
    since: datetime | None = None
    # Their level ("member", "viewer"; #1585), one choice for every workspace.
    level: str | None = None


def wide_scope(scope: str) -> str | None:
    """The scope below an organization (``<org container>/*``) of the
    organization's own container; None for any other scope."""
    org = org_of(scope)
    return org_below(org) if org is not None and is_org_container(scope) else None


def role_of_policy(policy_id: str) -> str | None:
    name = policy_id.removeprefix("builtin.")
    return name if policy_id.startswith("builtin.") and name in _RANK else None


def best(role_names: list[str]) -> str | None:
    return max(role_names, key=_RANK.__getitem__, default=None)


RolesListener = Callable[[str, bool], Awaitable[None]]


def _all_groups(iam: Any) -> list[Any]:
    """Every group IAM keeps (as ``api``: the whole truth)."""
    found: list[Any] = []
    after: str | None = None
    while True:
        page = iam.list_groups(limit=500, after=after)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _asker(by: Any) -> str | None:
    """The id of who asked (a ``User``, an id), None for the system."""
    if by is None:
        return None
    return str(getattr(by, "id", by))


def _now() -> datetime:
    return datetime.now(UTC)


class UnknownUserError(ValueError):
    """The id names no user Nexus (or IAM) knows, or not a user at all."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"{user_id} is not a known user")
        self.user_id = user_id


def directories_of(by_scope: dict[str, list[Member]]) -> dict[str, list[DirectoryEntry]]:
    """Each organization's directory, from who holds what at each container
    (``Memberships.members_by_scope``): the holders at the organization's container
    or below it, and at each of its workspaces' containers. A workspace in no
    organization belongs to no directory."""
    org_roles: dict[tuple[str, str], Member] = {}
    wide: dict[tuple[str, str], Member] = {}
    workspaces: dict[tuple[str, str], set[str]] = {}
    seen: dict[tuple[str, str], Member] = {}
    levels: dict[str, str] = {}
    for scope, members in by_scope.items():
        org = org_of(scope)
        if org is None:
            continue
        workspace = workspace_of(scope) if is_workspace_container(scope) else None
        if is_org_container(scope):
            target = org_roles
        elif scope == org_below(org):
            target = wide
        elif workspace is None:
            continue  # a module's container in the organization: not a membership
        else:
            target = {}
        for member in members:
            key = (org, member.user_id)
            if member.level is not None:
                levels[member.user_id] = member.level
            if workspace is not None:
                workspaces.setdefault(key, set()).add(workspace)
            else:
                target[key] = member
            first = seen.get(key)
            if first is None or (
                member.since is not None and (first.since is None or member.since < first.since)
            ):
                seen[key] = member
    found: dict[str, list[DirectoryEntry]] = {}
    for key, earliest in seen.items():
        org, user_id = key
        held = org_roles.get(key) or wide.get(key)
        found.setdefault(org, []).append(
            DirectoryEntry(
                user_id=user_id,
                principal_id=earliest.principal_id,
                role=held.role if held is not None else None,
                source="organization" if held is not None else "workspace",
                workspace_ids=tuple(sorted(workspaces.get(key, ()))),
                org_wide=key in wide,
                since=earliest.since,
                level=levels.get(user_id),
            )
        )
    return {
        org: sorted(
            entries,
            key=lambda e: (e.role is None, -_RANK[e.role] if e.role else 0, e.user_id),
        )
        for org, entries in found.items()
    }


# The groups the people flows put someone in (#1589), by kind.
MEMBERSHIP = "membership"  # "<W> workspace", "<O> people": where they work
ADMINS = "admins"  # "<W> admins", "<O> admins": what they administer
CAPABILITY = "capability"  # a group adding one thing to a level, by id
SEAT_KINDS = (MEMBERSHIP, ADMINS, CAPABILITY)
ADD_MEMBER = "iam:AddGroupMember"
REMOVE_MEMBER = "iam:RemoveGroupMember"


@dataclass(frozen=True)
class Seat:
    """One group the people flows put a person in, named by the container it is
    named in: the container's membership group or admins group, or a capability
    group (``group_id``; ``container``, the organization or workspace it is given
    in). In a container recorded before #1585 (roles as attachments), a seat is
    the role it stands for there: membership the person's level ("member" at an
    organization), admins "admin"."""

    container: str
    kind: str
    group_id: str | None = None


@dataclass(frozen=True)
class GroupChange:
    """A join or a leave of a group made for someone, for the audit: IAM writes it as
    ``api`` (after Nexus checked the caller), so its own audit names ``api``; this
    names who asked (``by``; None: the system, a seed or a take-back)."""

    action: str  # ADD_MEMBER, REMOVE_MEMBER
    group_id: str
    member_id: str
    container: str | None
    by: str | None
    at: datetime


AuditSink = Callable[[GroupChange], Awaitable[None]]


@dataclass(frozen=True)
class AccessSummary:
    """Where a person works and what they do (#1589): their level, the organizations
    they administer or belong to, their workspaces (with the ones they administer),
    their capability groups and whether they are a platform admin. From their
    groups; a container recorded before #1585 is read from its roles."""

    user_id: str
    principal_id: str
    level: str | None
    platform_admin: bool
    organizations: tuple[tuple[str, bool], ...]  # (org id, org admin)
    workspaces: tuple[tuple[str | None, str, bool], ...]  # (org id, workspace id, admin)
    capabilities: tuple[tuple[str, str, str], ...]  # (group id, name, owner scope)


@dataclass(frozen=True)
class _Plan:
    """A change of one person's groups at one container (``Memberships._plan``)."""

    principal_id: str
    joins: list[str]
    leaves: list[str]
    level_join: str | None
    level_leave: str | None
    # ``(policy, scope)``: roles of before at the container, and their mirror below
    # an organization (made as ``api``, taken as ``api``).
    detach: list[tuple[str, str]]
    mirrored: list[tuple[str, str]]
    # At an organization: whether the person is its admin afterwards.
    org_admin_after: bool | None = None


class _Reading:
    """One read of who holds what through groups, as ``api`` (IAM's thread): the
    groups, their members and the people's membership containers, each read once."""

    def __init__(self, iam: Any) -> None:
        self.iam = iam
        self._groups: dict[str, Any] = {}
        self._members: dict[str, list[str]] = {}
        self._containers: dict[str, list[str]] = {}
        self._levels: Levels | None = None

    def group(self, group_id: str) -> Any:
        if group_id not in self._groups:
            with as_service_account("api"):
                try:
                    self._groups[group_id] = self.iam.get_group(group_id)
                except (IAMNotFoundError, ResourceNotFoundError):
                    self._groups[group_id] = None
        return self._groups[group_id]

    def members(self, group_id: str) -> list[str]:
        if group_id not in self._members:
            with as_service_account("api"):
                try:
                    self._members[group_id] = list(self.iam.list_group_members(group_id))
                except (IAMNotFoundError, ResourceNotFoundError):
                    self._members[group_id] = []
        return self._members[group_id]

    def containers(self, principal_id: str) -> list[str]:
        """The containers ``principal_id`` is a member of (its membership groups)."""
        if principal_id not in self._containers:
            with as_service_account("api"):
                self._containers[principal_id] = sorted(
                    {m.container for m in self.iam.list_memberships(principal_id)}
                )
        return self._containers[principal_id]

    def levels(self) -> Levels | None:
        """The levels, never made by a read (None while nobody made them)."""
        if self._levels is None:
            self._levels = LEVELS.peek(self.iam)
        return self._levels

    def reached_through(self, group_id: str, scope: str) -> list[tuple[str, str]]:
        """``(member, container)`` a group's attachment at ``scope`` reaches: each
        member at ``scope``, or at ``${my workspaces}`` at each of their membership
        containers within the group's owner. A deleted group reaches nothing."""
        group = self.group(group_id)
        if group is None or group.status == "deleted":
            return []
        found: list[tuple[str, str]] = []
        for member in self.members(group_id):
            if not is_membership_scope(scope):
                found.append((member, scope))
                continue
            for container in self.containers(member):
                if within_owner(group.owner_scope, container):
                    found.append((member, container))
        return found

    def roles_of(self, principal_id: str) -> dict[str, list[str]]:
        """``{scope: [role]}`` the principal holds: its own role attachments and
        those of its groups (``reached_through``)."""
        held: dict[str, list[str]] = {}
        with as_service_account("api"):
            own = self.iam.list_attachments(principal_id=principal_id)
            groups = self.iam.list_principal_groups(principal_id)
        for attachment in own:
            role = role_of_policy(attachment.policy_id)
            if role is not None and attachment.scope and not is_membership_scope(attachment.scope):
                held.setdefault(attachment.scope, []).append(role)
        for group in groups:
            self._groups.setdefault(str(group.id), group)
            with as_service_account("api"):
                attachments = self.iam.list_attachments(principal_id=group.id)
            for attachment in attachments:
                role = role_of_policy(attachment.policy_id)
                if role is None or not attachment.scope:
                    continue
                if not is_membership_scope(attachment.scope):
                    held.setdefault(attachment.scope, []).append(role)
                    continue
                for container in self.containers(principal_id):
                    if within_owner(group.owner_scope, container):
                        held.setdefault(container, []).append(role)
        return held

    def levels_of(self, principals: Any) -> dict[str, str]:
        """``{principal: level}`` of those in a level group, the higher first."""
        levels = self.levels()
        if levels is None:
            return {}
        found: dict[str, str] = {}
        for level, group_id in ((VIEWER, levels.viewers), (MEMBER, levels.members)):
            for member in self.members(group_id):
                found[member] = level
        wanted = set(principals)
        return {p: level for p, level in found.items() if p in wanted}


class Memberships:
    def __init__(self, authz: Authz = AUTHZ) -> None:
        self._authz = authz
        self._listeners: list[RolesListener] = []
        # Whether a (legacy) Nexus user id is a user Nexus has; set where the
        # users live (the application's startup). None: every id is vouched for.
        self.known_user: Callable[[str], Awaitable[bool]] | None = None
        # Where each join and leave made for someone is recorded with who asked
        # (#1589): the Nexus audit log, set at the application's start.
        self.audit_sinks: list[AuditSink] = []

    async def _audit(self, changes: list[GroupChange]) -> None:
        for change in changes:
            logger.info(
                f"Group change: {change.action} {change.member_id} in {change.group_id}"
                f"{f' at {change.container}' if change.container else ''}, asked by "
                f"{change.by or 'the system'}"
            )
            for sink in list(self.audit_sinks):
                try:
                    await sink(change)
                except Exception:  # noqa: BLE001 - the audit never fails the change
                    logger.exception(f"Audit sink {sink!r} failed")

    def on_workspace_roles_changed(self, listener: RolesListener) -> RolesListener:
        """``await listener(workspace_id, dropped)`` after roles of a workspace
        changed (or, with ``dropped``, the workspace was deleted): what is derived
        from who belongs to it (shared graphs) follows."""
        self._listeners.append(listener)
        return listener

    async def changed(self, scope: str) -> None:
        """Tell the listeners that roles at ``scope`` changed without going through
        ``grant`` (the engine claimed an invitation's pending grants at a sign-in)."""
        await self._notify(scope)

    async def _notify(self, scope: str, *, dropped: bool = False) -> None:
        if not dropped:
            # "<X> members" and "<X> admins" follow the roles held at X.
            await CONTAINER_DEFAULTS.sync_scope(scope)
        workspace = workspace_of(scope) if is_workspace_container(scope) else None
        if workspace is None:
            return
        for listener in list(self._listeners):
            try:
                await listener(workspace, dropped)
            except Exception:  # noqa: BLE001 - a derived view never fails the change
                logger.exception(f"Roles listener {listener!r} failed for {scope}")

    # -- users and principals ----------------------------------------------------

    async def _vouched(self, user_id: str) -> bool:
        """Whether ``user_id`` names a user Nexus knows. An id from a request
        path must not become an IAM principal on its own: only a real user's does."""
        if _PRINCIPAL_ID.match(user_id) or self.known_user is None:
            return True  # an IAM id is looked up (never created); no check configured
        return await self.known_user(user_id)

    def _find_principal(self, iam: Any, user_id: str, *, vouched: bool) -> str | None:
        """The IAM user of a Nexus user: found, or (a user Nexus vouches for)
        created on first sight. An unknown id yields None and creates nothing."""
        with as_service_account("api"):
            if _PRINCIPAL_ID.match(user_id):
                try:
                    record = iam.get_principal(user_id)
                except (IAMNotFoundError, ResourceNotFoundError):
                    return None
                # Roles are for users: never a service account or a group.
                return str(record.id) if record.kind == "user" else None
            # Found as it is first: ensuring it would write the profile of the old
            # login over the one an identity provider vouches for (a linked user).
            record = iam.resolve_user(user_id)
            if record is not None:
                return str(record.id) if record.kind == "user" else None
            if not vouched:
                return None
            return str(iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus").id)

    def _principal_id(self, iam: Any, user_id: str) -> str:
        """The IAM user of a user the caller vouches for (a row, the configuration)."""
        found = self._find_principal(iam, user_id, vouched=True)
        if found is None:
            raise UnknownUserError(user_id)
        return found

    def _user_id(self, iam: Any, principal_id: str) -> str:
        with as_service_account("api"):
            record = iam.get_principal(principal_id)
        if record.issuer == LEGACY_NEXUS_ISSUER and record.subject:
            return str(record.subject)
        return str(record.id)

    async def principal_id(self, user_id: str) -> str:
        """The IAM principal of a Nexus user (a user Nexus knows), created on first sight."""
        if not await self._vouched(user_id):
            raise UnknownUserError(user_id)
        return await self._run(lambda iam: self._principal_id(iam, user_id))

    async def _run(self, work: Callable[[Any], _T], *, as_api: bool = True, user: Any = None) -> _T:
        """Run ``work(iam)`` in a worker thread: as ``api`` for no user, or in the
        caller's context (``api`` on behalf of ``user``) when ``as_api`` is False."""
        context = self._authz.context(user) if not as_api else None

        def run() -> _T:
            iam = runtime.iam()
            if context is None:
                with as_service_account("api"):
                    return work(iam)
            with use_call_context(context):
                return work(iam)

        return await run_in_threadpool(run)

    # -- reads -------------------------------------------------------------------

    async def _grouped_of(self, containers: Sequence[str]) -> dict[str, DefaultsRecord]:
        """The records of those of ``containers`` whose people are groups (#1585)."""
        found: dict[str, DefaultsRecord] = {}
        for container in dict.fromkeys(containers):
            record = await CONTAINER_DEFAULTS.grouped_record(container)
            if record is not None:
                found[container] = record
        return found

    async def _containers(self, org_id: str | None = None) -> list[str]:
        """The organizations' and workspaces' containers IAM registers (of ``org_id``
        alone when given)."""

        def work(iam: Any) -> list[str]:
            return sorted(
                c.name
                for c in iam.list_containers()
                if (is_org_container(c.name) or is_workspace_container(c.name))
                and (org_id is None or org_of(c.name) == org_id)
            )

        return await self._run(work)

    async def members(self, scope: str) -> list[Member]:
        """Who holds a role at ``scope``, each with the highest they hold."""
        grouped = await self._grouped_of([scope])
        return await self._run(
            lambda iam: self.members_by_scope(iam, scope, grouped=grouped).get(scope, [])
        )

    async def members_of(self, scopes: list[str]) -> dict[str, list[Member]]:
        """Who holds a role at each of ``scopes``, in one pass over the roles'
        attachments (``members`` would make one per scope)."""
        wanted = set(scopes)
        grouped = await self._grouped_of(scopes)

        def work(iam: Any) -> dict[str, list[Member]]:
            found = self.members_by_scope(iam, grouped=grouped)
            return {scope: found.get(scope, []) for scope in wanted}

        return await self._run(work)

    def members_by_scope(
        self,
        iam: Any,
        scope: str | None = None,
        *,
        org: str | None = None,
        grouped: dict[str, DefaultsRecord] | None = None,
    ) -> dict[str, list[Member]]:
        """Who holds a role at each container (at ``scope`` alone when given, at the
        containers of ``org`` alone when given), each with the highest they hold
        there and their level, in one pass over the roles' attachments: to a person,
        and to a group (each of its members; at ``${my workspaces}``, each member's
        membership containers within the group's owner). The one reading of who holds
        what, for ``members`` and the default groups (``container_defaults``). A
        principal Nexus cannot name is left out. In IAM's thread (``iam`` is the
        service).

        ``grouped``: containers whose people are groups (#1589), read from them too:
        "<X> admins" are its admins (an organization's also below it), everyone else
        in its membership group ("<W> workspace", "<O> people") holds their level
        there (Viewer for someone with none)."""
        reading = _Reading(iam)
        held: dict[tuple[str, str], list[str]] = {}
        since: dict[tuple[str, str], datetime] = {}

        def add(where: str, principal_id: str, role: str, at: datetime | None) -> None:
            if scope is not None and where != scope:
                return
            if org is not None and org_of(where) != org:
                return  # named only for the org asked for: each name is a read
            key = (where, principal_id)
            held.setdefault(key, []).append(role)
            if at is not None:
                since[key] = min(at, since.get(key, at))

        for role, policy in _POLICY_OF.items():
            for attachment in iam.list_attachments(policy_id=policy):
                if attachment.scope is None:
                    continue
                if not attachment.principal_id.startswith("grp_"):
                    if not is_membership_scope(attachment.scope):
                        add(attachment.scope, attachment.principal_id, role, attachment.created_at)
                    continue
                for member, where in reading.reached_through(
                    attachment.principal_id, attachment.scope
                ):
                    add(where, member, role, None)
        for container, record in (grouped or {}).items():
            admins = (
                set(reading.members(record.admins_group_id)) if record.admins_group_id else set()
            )
            people = (
                set(reading.members(record.members_group_id)) if record.members_group_id else set()
            )
            known = reading.levels_of(people | admins)
            wide = wide_scope(container)
            for principal in sorted(people | admins):
                add(
                    container,
                    principal,
                    "admin" if principal in admins else known.get(principal, VIEWER),
                    None,
                )
                if wide is not None and principal in admins:
                    add(wide, principal, "admin", None)
        levels = reading.levels_of(principal for _where, principal in held)
        users: dict[str, str | None] = {}
        found: dict[str, list[Member]] = {}
        for (where, principal_id), names in held.items():
            if principal_id not in users:
                try:
                    users[principal_id] = self._user_id(iam, principal_id)
                except (IAMNotFoundError, ResourceNotFoundError):
                    users[principal_id] = None
            user_id = users[principal_id]
            if user_id is None:
                continue
            found.setdefault(where, []).append(
                Member(
                    user_id,
                    best(names) or "viewer",
                    principal_id,
                    since.get((where, principal_id)),
                    levels.get(principal_id),
                )
            )
        return {
            where: sorted(members, key=lambda m: (-_RANK[m.role], m.user_id))
            for where, members in found.items()
        }

    async def org_directory(self, org_id: str) -> list[DirectoryEntry]:
        """The organization's directory (``DirectoryEntry``): its members, then the
        people who hold a role only in one of its workspaces. Read from the groups of
        the organization and its workspaces ("<O> admins", "<O> people", each "<W>
        workspace" and "<W> admins"; #1589), and from the role attachments of the
        containers recorded before #1585, in one pass."""
        grouped = await self._grouped_of(await self._containers(org_id))
        return await self._run(
            lambda iam: directories_of(self.members_by_scope(iam, org=org_id, grouped=grouped)).get(
                org_id, []
            )
        )

    async def org_directories(self) -> dict[str, list[DirectoryEntry]]:
        """Every organization's directory, by org id, in one pass over the roles'
        attachments (``members_by_scope``)."""
        grouped = await self._grouped_of(await self._containers())
        return await self._run(
            lambda iam: directories_of(self.members_by_scope(iam, grouped=grouped))
        )

    async def platform_admins(self) -> set[str]:
        """The users who hold ``builtin.platform_admin``, by the id Nexus names them."""

        def work(iam: Any) -> set[str]:
            found: set[str] = set()
            principals = {
                a.principal_id
                for a in iam.list_attachments(policy_id=roles.PLATFORM_ADMIN)
                if not a.principal_id.startswith("grp_")
            }
            levels = LEVELS.peek(iam)
            if levels is not None:
                principals |= set(iam.list_group_members(levels.platform_admins))
            for principal_id in principals:
                try:
                    found.add(self._user_id(iam, principal_id))
                except (IAMNotFoundError, ResourceNotFoundError):
                    continue
            return found

        return await self._run(work)

    async def set_platform_admin(self, user_id: str, on: bool, *, by: Any = None) -> None:
        """Attach or detach ``builtin.platform_admin`` for a user Nexus knows. Done
        as ``by`` (``api`` on their behalf), so IAM decides whether they may."""
        vouched = await self._vouched(user_id)

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                raise UnknownUserError(user_id)
            group = LEVELS.get(iam).platform_admins
            if on:
                # "Platform admins" holds builtin.platform_admin (#1585).
                iam.add_group_member(group, principal_id)
                return
            with as_service_account("api"):  # the whole truth, to take back both
                direct = any(
                    a.scope is None
                    for a in iam.list_attachments(
                        principal_id=principal_id, policy_id=roles.PLATFORM_ADMIN
                    )
                )
                member = principal_id in iam.list_group_members(group)
            if member:
                iam.remove_group_member(group, principal_id)
            if direct:  # one attached before #1585
                iam.detach_policy(roles.PLATFORM_ADMIN, principal_id)

        await self._run(work, as_api=by is None, user=by)

    async def role_at(self, user_id: str, scope: str) -> str | None:
        """The highest role the user holds directly at ``scope``."""
        return (await self.roles_of(user_id)).get(scope)

    async def inherited_role(self, user_id: str, org_id: str) -> str | None:
        """The role the user holds in every workspace of ``org_id`` through their
        organization role (an owner or admin of the organization), if any."""
        return (await self.roles_of(user_id)).get(org_below(org_id))

    async def org_wide_orgs_of(self, user_id: str) -> list[str]:
        """The orgs whose every workspace the user reaches (they hold a role
        below the organization: an org owner or admin)."""
        found = []
        for scope in await self.roles_of(user_id):
            org = org_of(scope)
            if org is not None and scope == org_below(org):
                found.append(org)
        return sorted(found)

    async def sync_org_wide_roles(self, user_id: str | None = None) -> int:
        """Hold the organization-wide role of every org owner and admin (of one user,
        when given: after the sign-in that claimed their invitation). Idempotent,
        and it only adds: run at start, it gives the owners and admins of an older
        install their reach; an organization-wide role someone attached on purpose
        is left alone. Returns how many attachments were made."""

        def work(iam: Any) -> int:
            made = 0
            only = self._find_principal(iam, user_id, vouched=False) if user_id else None
            if user_id and only is None:
                return 0
            with as_service_account("api"):
                for role in INHERITING_ROLES:
                    for attachment in iam.list_attachments(policy_id=_POLICY_OF[role]):
                        if only is not None and attachment.principal_id != only:
                            continue
                        wide = wide_scope(attachment.scope) if attachment.scope else None
                        if wide is None or role in self._held(iam, attachment.principal_id, wide):
                            continue
                        iam.attach_policy(_POLICY_OF[role], attachment.principal_id, wide)
                        made += 1
            return made

        return await self._run(work)

    async def roles_of(self, user_id: str) -> dict[str, str]:
        """``{scope: role}`` of every role the user holds directly."""

        vouched = await self._vouched(user_id)

        def work(iam: Any) -> dict[str, str]:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return {}  # no such user: no roles, and nothing is created
            held = _Reading(iam).roles_of(principal_id)
            return {scope: best(names) or "viewer" for scope, names in held.items()}

        return await self._run(work)

    async def workspaces_of(self, user_id: str) -> list[tuple[str | None, str]]:
        """``(org, workspace)`` of every workspace the user holds a role in directly
        (``None`` for a workspace in no organization)."""
        found = []
        for scope in await self.roles_of(user_id):
            workspace = workspace_of(scope) if is_workspace_container(scope) else None
            if workspace is not None:
                found.append((org_of(scope), workspace))
        return sorted(found, key=lambda pair: (pair[0] or "", pair[1]))

    async def scopes_of(self, user_id: str, *, level: str) -> dict[str, str]:
        """The user's roles at ``level``: ``"org"`` (an organization's container) or
        ``"workspace"`` (a workspace's), keyed by the org or workspace id."""
        found: dict[str, str] = {}
        for scope, role in (await self.roles_of(user_id)).items():
            if level == "org" and is_org_container(scope):
                found[org_of(scope) or ""] = role
            elif level == "workspace" and is_workspace_container(scope):
                found[workspace_of(scope) or ""] = role
        return found

    # -- changes -----------------------------------------------------------------

    @staticmethod
    def _held(iam: Any, principal_id: str, scope: str) -> list[str]:
        found = []
        with as_service_account("api"):  # the whole truth, not what the caller may list
            attachments = iam.list_attachments(principal_id=principal_id)
        for attachment in attachments:
            role = role_of_policy(attachment.policy_id)
            if role is not None and attachment.scope == scope:
                found.append(role)
        return found

    @staticmethod
    def mirror_org_wide(iam: Any, principal_id: str, scope: str, role: str | None) -> None:
        """Hold the role below the organization an organization ``role`` (``None``:
        no role) carries, and no other. Made as ``api`` for no user: an org admin
        holds nothing below the organization to grant there, so the change that
        asked for ``role`` was authorized at the organization's container first."""
        wide = wide_scope(scope)
        if wide is None:
            return
        Memberships.hold_wide(iam, principal_id, wide, role)

    @staticmethod
    def hold_wide(iam: Any, principal_id: str, wide: str, role: str | None) -> None:
        """Hold at ``wide``, the scope below an organization, the role its own
        ``role`` carries there (an owner's or an admin's), and no other."""
        wanted = role if role in INHERITING_ROLES else None
        with as_service_account("api"):
            held = Memberships._held(iam, principal_id, wide)
            if wanted is not None and wanted not in held:
                iam.attach_policy(_POLICY_OF[wanted], principal_id, wide)
            for other in held:
                if other != wanted:
                    iam.detach_policy(_POLICY_OF[other], principal_id, wide)

    @staticmethod
    def _require_all(
        iam: Any, principal_id: str, scope: str, needed: list[tuple[str, str]]
    ) -> None:
        for action, role in needed:
            try:
                iam.require(action, attachment_resource(_POLICY_OF[role], principal_id, scope))
            except (PermissionDeniedError, ResourceNotFoundError) as exc:
                raise MembershipDenied(role) from exc

    # -- in groups (#1585) ----------------------------------------------------------

    def _plan(
        self, iam: Any, principal_id: str, role: str | None, scope: str, record: DefaultsRecord
    ) -> _Plan:
        """What giving ``role`` at ``scope`` (None: taking every role there) changes
        in the groups of ``record``'s container (``grant``'s table), and the roles
        of before held there that the groups replace. As ``api``: the whole truth."""
        levels = LEVELS.get(iam)
        role = "admin" if role == "owner" else role  # Owner is no longer assigned
        membership, admins = str(record.members_group_id), str(record.admins_group_id)
        with as_service_account("api"):
            mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
        wanted: list[str] = []
        unwanted: list[str] = [membership, admins] if role is None else []
        if role is not None:
            wanted.append(membership)
            (wanted if role == "admin" else unwanted).append(admins)
        target: str | None = None
        if role in ("member", "viewer") or (role == "admin" and is_workspace_container(scope)):
            # A workspace admin is a Member with "<W> admins"; an org admin keeps
            # their level (none, or the one they have).
            target = MEMBER if role in ("admin", "member") else VIEWER
        level_join = level_leave = None
        if target is not None:
            if levels.group_of(target) not in mine:
                level_join = levels.group_of(target)
            other = levels.group_of(VIEWER if target == MEMBER else MEMBER)
            if other in mine:
                level_leave = other
        detach = [(_POLICY_OF[r], scope) for r in self._held(iam, principal_id, scope)]
        wide = wide_scope(scope)
        mirrored = (
            [(_POLICY_OF[r], wide) for r in self._held(iam, principal_id, wide)] if wide else []
        )
        return _Plan(
            principal_id=principal_id,
            joins=[g for g in wanted if g not in mine],
            leaves=[g for g in unwanted if g in mine],
            level_join=level_join,
            level_leave=level_leave,
            detach=detach,
            mirrored=mirrored,
            org_admin_after=role == "admin" if is_org_container(scope) else None,
        )

    def _require_plan(self, iam: Any, plan: _Plan, scope: str) -> None:
        """The caller may make ``plan``, or ``MembershipDenied``: each group's member
        change on the group as its container names it, a level change on the level
        group as named in the container (IAM's level-group rule), each role of before
        detached. In the caller's context; nothing is changed."""
        needed = [("iam:AddGroupMember", group_resource(g, scope)) for g in plan.joins]
        needed += [("iam:RemoveGroupMember", group_resource(g, scope)) for g in plan.leaves]
        needed += [
            ("iam:DetachPolicy", attachment_resource(policy, plan.principal_id, where))
            for policy, where in plan.detach
        ]
        try:
            for action, resource in needed:
                iam.require(action, resource)
            for action, group in (
                ("iam:AddGroupMember", plan.level_join),
                ("iam:RemoveGroupMember", plan.level_leave),
            ):
                if group is not None and not (
                    iam.authorize(action, group_resource(group)).allowed
                    or iam.authorize(action, group_resource(group, scope)).allowed
                ):
                    raise PermissionDeniedError(action, group_resource(group, scope))
        except (PermissionDeniedError, ResourceNotFoundError) as exc:
            raise MembershipDenied(str(exc)) from exc

    def _keep_an_org_admin(self, iam: Any, principal_id: str, scope: str, after: bool) -> None:
        """``LastOrgAdminError`` when ``principal_id``, an admin of the organization
        ``scope`` (or an owner of before), would stop being one (``after``) and no
        other admin is left."""
        if not is_org_container(scope) or after:
            return
        with as_service_account("api"):  # the whole truth, whoever asks
            admins = [
                m.principal_id
                for m in self.members_by_scope(iam, scope).get(scope, [])
                if m.role in INHERITING_ROLES
            ]
        if principal_id in admins and all(p == principal_id for p in admins):
            raise LastOrgAdminError(scope)

    def _apply_plan(
        self,
        iam: Any,
        plan: _Plan,
        *,
        by: Any = None,
        changes: list[GroupChange] | None = None,
        container: str | None = None,
    ) -> bool:
        """Make ``plan`` as ``api`` for no user (it was checked as the caller): the
        membership group first (the person's tie), then the level, then what is left
        and the roles of before. Whether anything changed. Each join and leave is
        added to ``changes``, for the audit."""
        record = changes if changes is not None else []
        asked = _asker(by)

        def note(action: str, group: str) -> None:
            record.append(GroupChange(action, group, plan.principal_id, container, asked, _now()))

        with as_service_account("api"):
            for group in plan.joins:
                iam.add_group_member(group, plan.principal_id)
                note(ADD_MEMBER, group)
            if plan.level_join:
                iam.add_group_member(plan.level_join, plan.principal_id)
                note(ADD_MEMBER, plan.level_join)
            if plan.level_leave:
                iam.remove_group_member(plan.level_leave, plan.principal_id)
                note(REMOVE_MEMBER, plan.level_leave)
            for group in plan.leaves:
                iam.remove_group_member(group, plan.principal_id)
                note(REMOVE_MEMBER, group)
            for policy, where in [*plan.detach, *plan.mirrored]:
                iam.detach_policy(policy, plan.principal_id, where)
            self._sync_admin_models(iam, plan.principal_id)
        if plan.level_join or plan.level_leave:
            logger.info(
                f"Level of {plan.principal_id}: joined {plan.level_join}, left "
                f"{plan.level_leave}, by {getattr(by, 'id', by) or 'the system'}"
            )
        return bool(
            plan.joins
            or plan.leaves
            or plan.level_join
            or plan.level_leave
            or plan.detach
            or plan.mirrored
        )

    @staticmethod
    def _sync_admin_models(iam: Any, principal_id: str) -> None:
        """Keep the person in "Workspace admins" (every model) while they are in a
        group holding ``builtin.admin`` ("<W> admins", "<O> admins"). As ``api``."""
        levels = LEVELS.get(iam)
        groups = iam.list_principal_groups(principal_id)
        admin = any(
            a.policy_id == roles.ADMIN
            for g in groups
            if str(g.id) != levels.workspace_admins
            for a in iam.list_attachments(principal_id=g.id)
        )
        member = any(str(g.id) == levels.workspace_admins for g in groups)
        if admin and not member:
            iam.add_group_member(levels.workspace_admins, principal_id)
        elif member and not admin:
            iam.remove_group_member(levels.workspace_admins, principal_id)

    async def level_of(self, user_id: str) -> str | None:
        """The person's level ("member", "viewer"), or None."""
        vouched = await self._vouched(user_id)

        def work(iam: Any) -> str | None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return None
            return _Reading(iam).levels_of([principal_id]).get(principal_id)

        return await self._run(work)

    # -- the people flows (#1589): seats in groups ---------------------------------------

    async def _seat_records(self, seats: Sequence[Seat]) -> dict[str, DefaultsRecord | None]:
        return {
            container: await CONTAINER_DEFAULTS.grouped_record(container)
            for container in dict.fromkeys(s.container for s in seats if s.kind != CAPABILITY)
        }

    @staticmethod
    def _seat_group(seat: Seat, record: DefaultsRecord | None) -> str | None:
        """The group a seat names; None in a container recorded before #1585."""
        if seat.kind == CAPABILITY:
            return seat.group_id
        if record is None:
            return None
        group = record.members_group_id if seat.kind == MEMBERSHIP else record.admins_group_id
        return str(group) if group else None

    @staticmethod
    def _legacy_role(seat: Seat, level: str | None) -> str:
        """The role a seat stands for in a container recorded before #1585."""
        if seat.kind == ADMINS:
            return "admin"
        if is_org_container(seat.container):
            return "member"  # an organization knows no viewer role
        return level or MEMBER

    @staticmethod
    def _model_group_ids(iam: Any) -> set[str]:
        levels = LEVELS.peek(iam)
        if levels is None:
            return set()
        return {levels.viewers, levels.members, levels.platform_admins, levels.workspace_admins}

    @staticmethod
    def _is_capability(iam: Any, group: Any, model_groups: set[str]) -> bool:
        """A group that adds something to a level: not one of the model's own (a level
        group, a membership group, "Platform admins", "Workspace admins"), holding at
        least one policy and no built-in role (an admins group holds
        ``builtin.admin``; the retired "<X> members" and synced "<X> admins" hold
        nothing). As ``api``."""
        if group.status == "deleted" or str(group.id) in model_groups:
            return False
        if getattr(group, "level_group", False) or getattr(group, "membership_of", None):
            return False
        held = iam.list_attachments(principal_id=group.id)
        return bool(held) and not any(a.policy_id.startswith("builtin.") for a in held)

    async def capability_groups(self, org_id: str | None) -> list[Any]:
        """The groups a person may be put in beside their level in ``org_id`` (None: a
        workspace in no organization): the organization's capability groups, then
        the platform's ("Models · all"), by name. As ``api`` (the route authorized
        its caller)."""
        owners = {PLATFORM} | ({org_container(org_id)} if org_id else set())

        def work(iam: Any) -> list[Any]:
            model_groups = self._model_group_ids(iam)
            found = [
                g
                for g in _all_groups(iam)
                if g.owner_scope in owners and self._is_capability(iam, g, model_groups)
            ]
            return sorted(found, key=lambda g: (g.owner_scope == PLATFORM, g.name, str(g.id)))

        return await self._run(work)

    async def held_seats(self, user_id: str, seats: Sequence[Seat]) -> set[Seat]:
        """Which of ``seats`` the person holds now."""
        records = await self._seat_records(seats)
        vouched = await self._vouched(user_id)

        def work(iam: Any) -> set[Seat]:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return set()
            mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
            roles: dict[str, str] | None = None
            held: set[Seat] = set()
            for seat in seats:
                group = self._seat_group(seat, records.get(seat.container))
                if group is not None:
                    if group in mine:
                        held.add(seat)
                    continue
                if roles is None:
                    roles = {
                        s: best(n) or "viewer"
                        for s, n in _Reading(iam).roles_of(principal_id).items()
                    }
                role = roles.get(seat.container)
                if role is not None and (seat.kind == MEMBERSHIP or role in INHERITING_ROLES):
                    held.add(seat)
            return held

        return await self._run(work)

    def _require_level(
        self,
        iam: Any,
        principal_id: str | None,
        level: str,
        where: Sequence[str],
    ) -> None:
        """In the caller's context: they may move the person to ``level`` (the level
        group on its platform name, or as named in one of ``where`` and the person's
        containers: IAM's level-group rule, S1). ``PermissionDeniedError``.

        ``where`` are the containers whose people are groups the person is being put
        in. With none of them and no membership of the person's, the level reaches
        nowhere yet (``${my workspaces}`` resolves to membership containers): where
        the person works is recorded before #1585, and there the level is the role
        attached, whose attachment the caller is checked for (``check_seats``)."""
        levels = LEVELS.get(iam)
        with as_service_account("api"):
            mine = (
                {str(g.id) for g in iam.list_principal_groups(principal_id)}
                if principal_id
                else set()
            )
            containers = (
                [m.container for m in iam.list_memberships(principal_id)] if principal_id else []
            )
        if not where and not containers:
            return
        target = levels.group_of(level)
        other = levels.group_of(VIEWER if level == MEMBER else MEMBER)
        named = list(dict.fromkeys([*where, *containers]))
        for action, group in ((ADD_MEMBER, target), (REMOVE_MEMBER, other)):
            if (group == target) == (group in mine):
                continue  # joined already, or not in it to leave
            if not (
                iam.authorize(action, group_resource(group)).allowed
                or any(iam.authorize(action, group_resource(group, c)).allowed for c in named)
            ):
                raise PermissionDeniedError(action, group_resource(group))

    async def check_seats(
        self,
        user_id: str | None,
        seats: Sequence[Seat],
        *,
        level: str | None,
        by: Any,
        org_id: str | None = None,
    ) -> None:
        """``MembershipDenied`` unless ``by`` may put the person (``None``: someone not
        made yet) in ``seats`` and at ``level``, changing nothing: each group's member
        change as its container names it, the level as IAM's level-group rule
        decides it, each capability group on the group itself. ``ValueError`` for a
        capability that is not one of ``org_id``'s (``capability_groups``)."""
        records = await self._seat_records(seats)
        vouched = await self._vouched(user_id) if user_id else False
        wanted = [s.group_id for s in seats if s.kind == CAPABILITY]
        allowed = {str(g.id) for g in await self.capability_groups(org_id)} if wanted else set()
        unknown = [g for g in wanted if g not in allowed]
        if unknown:
            raise ValueError(f"Not a capability group here: {', '.join(map(str, unknown))}")

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched) if user_id else None
            try:
                for seat in seats:
                    group = self._seat_group(seat, records.get(seat.container))
                    if seat.kind == CAPABILITY and group is not None:
                        with as_service_account("api"):
                            owner = iam.get_group(group).owner_scope
                        iam.require(ADD_MEMBER, group_resource(group, owner))
                    elif group is not None:
                        iam.require(ADD_MEMBER, group_resource(group, seat.container))
                    else:
                        role = self._legacy_role(seat, level)
                        held = self._held(iam, principal_id, seat.container) if principal_id else []
                        for other in held:
                            if other != role:
                                iam.require(
                                    "iam:DetachPolicy",
                                    attachment_resource(
                                        _POLICY_OF[other], str(principal_id), seat.container
                                    ),
                                )
                        if role not in held:
                            iam.require(
                                "iam:AttachPolicy",
                                attachment_resource(
                                    _POLICY_OF[role], principal_id or "-", seat.container
                                ),
                            )
                            if principal_id is None:
                                self._probe_held(iam, _POLICY_OF[role], seat.container)
                if level is not None:
                    where = [
                        s.container
                        for s in seats
                        if s.kind != CAPABILITY and records.get(s.container) is not None
                    ]
                    self._require_level(iam, principal_id, level, where)
            except (PermissionDeniedError, ResourceNotFoundError, IAMNotFoundError) as exc:
                raise MembershipDenied(str(exc)) from exc

        await self._run(work, as_api=by is None, user=by)

    @staticmethod
    def _probe_held(iam: Any, policy_id: str, scope: str) -> None:
        """``GrantNotHeldError`` unless the caller holds what ``policy_id`` grants at
        ``scope``, for someone not made yet: IAM checks that only on a write, so a
        pending grant to nobody is written as the caller and withdrawn at once."""
        probe = iam.create_pending_grant(_PROBE_PROVIDER, _PROBE_EMAIL, policy_id, scope)
        with as_service_account("api"):
            iam.revoke_pending_grant(str(probe.id))

    async def take_seat(self, user_id: str, seat: Seat, *, by: Any, level: str | None) -> bool:
        """Put the person in ``seat`` (checked first: ``check_seats``), as ``api`` for no
        user; a capability group on ``by``'s behalf, so IAM checks what it holds too.
        True when this call did. In a container recorded before #1585, the role the
        seat stands for (``_legacy_role``)."""
        record = (
            await CONTAINER_DEFAULTS.grouped_record(seat.container)
            if seat.kind != CAPABILITY
            else None
        )
        group = self._seat_group(seat, record)
        if group is None:
            role = self._legacy_role(seat, level)
            if await self.role_at(user_id, seat.container) == role:
                return False
            await self.grant(user_id, role, seat.container, by=by)
            return True
        if not await self._vouched(user_id):
            raise UnknownUserError(user_id)
        changes: list[GroupChange] = []
        found = group

        def work(iam: Any) -> bool:
            principal_id = self._principal_id(iam, user_id)
            with as_service_account("api"):
                if principal_id in iam.list_group_members(found):
                    return False
            if seat.kind == CAPABILITY and by is not None:
                iam.add_group_member(found, principal_id)  # as the caller: held-checked
            else:
                with as_service_account("api"):
                    iam.add_group_member(found, principal_id)
            with as_service_account("api"):
                self._sync_admin_models(iam, principal_id)
            changes.append(
                GroupChange(ADD_MEMBER, found, principal_id, seat.container, _asker(by), _now())
            )
            return True

        joined = await self._run(work, as_api=by is None, user=by)
        await self._audit(changes)
        if joined:
            await self._notify(seat.container)
        return joined

    async def leave_seat(self, user_id: str, seat: Seat, *, by: Any) -> bool:
        """Take the person out of ``seat``: checked as ``by`` (``None``: Nexus, a
        take-back), made as ``api``. ``LastOrgAdminError`` for an organization's last
        admin. In a container recorded before #1585: leaving the membership drops the
        role, leaving the admins keeps the person's level there. True when this call
        did."""
        record = (
            await CONTAINER_DEFAULTS.grouped_record(seat.container)
            if seat.kind != CAPABILITY
            else None
        )
        group = self._seat_group(seat, record)
        if group is None:
            if seat.kind == MEMBERSHIP:
                return await self.revoke(user_id, seat.container, by=by)
            if await self.role_at(user_id, seat.container) not in INHERITING_ROLES:
                return False
            level = await self.level_of(user_id)
            await self.grant(
                user_id,
                self._legacy_role(Seat(seat.container, MEMBERSHIP), level),
                seat.container,
                by=by,
            )
            return True
        vouched = await self._vouched(user_id)
        changes: list[GroupChange] = []
        found = group

        def work(iam: Any) -> bool:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return False
            with as_service_account("api"):
                if principal_id not in iam.list_group_members(found):
                    return False
                owner = iam.get_group(found).owner_scope
            if by is not None:
                named = owner if seat.kind == CAPABILITY else seat.container
                try:
                    iam.require(REMOVE_MEMBER, group_resource(found, named))
                except (PermissionDeniedError, ResourceNotFoundError) as exc:
                    raise MembershipDenied(str(exc)) from exc
            if seat.kind == ADMINS:
                self._keep_an_org_admin(iam, principal_id, seat.container, False)
            with as_service_account("api"):
                iam.remove_group_member(found, principal_id)
                self._sync_admin_models(iam, principal_id)
            changes.append(
                GroupChange(REMOVE_MEMBER, found, principal_id, seat.container, _asker(by), _now())
            )
            return True

        left = await self._run(work, as_api=by is None, user=by)
        await self._audit(changes)
        if left:
            await self._notify(seat.container)
        return left

    async def check_leaving(self, user_id: str, seats: Sequence[Seat], *, by: Any) -> None:
        """``MembershipDenied`` unless ``by`` may take the person out of each of
        ``seats`` they hold; ``LastOrgAdminError`` when it would leave an organization
        with no admin. Changes nothing."""
        records = await self._seat_records(seats)
        vouched = await self._vouched(user_id)

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return
            with as_service_account("api"):
                mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
            try:
                for seat in seats:
                    group = self._seat_group(seat, records.get(seat.container))
                    if group is None:
                        held = self._held(iam, principal_id, seat.container)
                        for role in held:
                            iam.require(
                                "iam:DetachPolicy",
                                attachment_resource(_POLICY_OF[role], principal_id, seat.container),
                            )
                        if seat.kind == ADMINS:
                            self._keep_an_org_admin(iam, principal_id, seat.container, False)
                        continue
                    if group not in mine:
                        continue
                    if by is not None:
                        with as_service_account("api"):
                            owner = iam.get_group(group).owner_scope
                        named = owner if seat.kind == CAPABILITY else seat.container
                        iam.require(REMOVE_MEMBER, group_resource(group, named))
                    if seat.kind == ADMINS:
                        self._keep_an_org_admin(iam, principal_id, seat.container, False)
            except (PermissionDeniedError, ResourceNotFoundError) as exc:
                raise MembershipDenied(str(exc)) from exc

        await self._run(work, as_api=by is None, user=by)

    async def set_level(
        self, user_id: str, level: str, *, by: Any, where: Sequence[str] = ()
    ) -> str | None:
        """Make ``level`` the person's, everywhere (one choice: they leave the other
        level group). Checked as ``by`` by IAM's level-group rule (S1): the platform
        admin, an org admin, or an admin of any of the person's containers (or of
        ``where``, those they are being put in); made as ``api``; audited with who
        asked. ``None`` for ``by``: the system (seeding, a take-back). Returns the
        level they had."""
        if level not in (MEMBER, VIEWER):
            raise ValueError(f"Unknown level {level!r}")
        if not await self._vouched(user_id):
            raise UnknownUserError(user_id)
        changes: list[GroupChange] = []
        asked = _asker(by)
        grouped_where = list(await self._grouped_of(where))

        def work(iam: Any) -> str | None:
            principal_id = self._principal_id(iam, user_id)
            levels = LEVELS.get(iam)
            if by is not None:
                try:
                    self._require_level(iam, principal_id, level, grouped_where)
                except (PermissionDeniedError, ResourceNotFoundError) as exc:
                    raise MembershipDenied(str(exc)) from exc
            with as_service_account("api"):
                mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
                before = next(
                    (levels.level_of_group(g) for g in levels.level_groups if g in mine), None
                )
                target = levels.group_of(level)
                if target not in mine:
                    iam.add_group_member(target, principal_id)
                    changes.append(
                        GroupChange(ADD_MEMBER, target, principal_id, None, asked, _now())
                    )
                for other in levels.level_groups:
                    if other != target and other in mine:
                        iam.remove_group_member(other, principal_id)
                        changes.append(
                            GroupChange(REMOVE_MEMBER, other, principal_id, None, asked, _now())
                        )
            return before

        before = await self._run(work, as_api=by is None, user=by)
        await self._audit(changes)
        return before

    async def clear_level(self, user_id: str) -> None:
        """Leave both level groups, as Nexus (the take-back of a person who had
        none)."""
        vouched = await self._vouched(user_id)
        changes: list[GroupChange] = []

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            levels = LEVELS.peek(iam)
            if principal_id is None or levels is None:
                return
            mine = {str(g.id) for g in iam.list_principal_groups(principal_id)}
            for group in levels.level_groups:
                if group in mine:
                    iam.remove_group_member(group, principal_id)
                    changes.append(
                        GroupChange(REMOVE_MEMBER, group, principal_id, None, None, _now())
                    )

        await self._run(work)
        await self._audit(changes)

    async def access_of(self, user_id: str) -> AccessSummary | None:
        """Where the person works and what they do (``AccessSummary``); None for an
        unknown user."""
        vouched = await self._vouched(user_id)

        def work(iam: Any) -> AccessSummary | None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return None
            reading = _Reading(iam)
            levels = reading.levels()
            groups = iam.list_principal_groups(principal_id)
            ids = {str(g.id) for g in groups}
            direct_admin = any(
                a.scope is None
                for a in iam.list_attachments(
                    principal_id=principal_id, policy_id=roles.PLATFORM_ADMIN
                )
            )
            roles_held = {s: best(n) or "viewer" for s, n in reading.roles_of(principal_id).items()}
            organizations = tuple(
                (org_of(scope) or "", role in INHERITING_ROLES)
                for scope, role in sorted(roles_held.items())
                if is_org_container(scope)
            )
            workspaces = tuple(
                (org_of(scope), workspace_of(scope) or "", role in INHERITING_ROLES)
                for scope, role in sorted(roles_held.items())
                if is_workspace_container(scope)
            )
            model_groups = self._model_group_ids(iam)
            capabilities = tuple(
                (str(g.id), str(g.name), str(g.owner_scope))
                for g in sorted(groups, key=lambda g: g.name)
                if self._is_capability(iam, g, model_groups)
            )
            return AccessSummary(
                user_id=self._user_id(iam, principal_id),
                principal_id=principal_id,
                level=reading.levels_of([principal_id]).get(principal_id),
                platform_admin=direct_admin
                or (levels is not None and levels.platform_admins in ids),
                organizations=organizations,
                workspaces=workspaces,
                capabilities=capabilities,
            )

        return await self._run(work)

    # -- changes (the role-based API) -------------------------------------------------

    async def check(self, user_id: str, role: str | None, scope: str, *, by: Any = None) -> None:
        """Raise ``MembershipDenied`` unless ``by`` may give the user ``role`` at
        ``scope`` (``None``: take their roles away), changing nothing; and
        ``LastOrgAdminError`` when it would leave an organization with no admin.
        Callers with rules of their own (an owner of before must remain) ask this
        first, so the caller's lack of rights is what they hear about."""

        vouched = await self._vouched(user_id)
        record = await CONTAINER_DEFAULTS.grouped_record(scope)

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return  # no such user: nothing is held, nothing to refuse
            if record is not None:
                plan = self._plan(iam, principal_id, role, scope, record)
                self._require_plan(iam, plan, scope)
                self._keep_an_org_admin(iam, principal_id, scope, bool(plan.org_admin_after))
                return
            held = self._held(iam, principal_id, scope)
            needed = [("iam:DetachPolicy", other) for other in held if other != role]
            if role is not None and role not in held:
                needed.append(("iam:AttachPolicy", role))
            self._require_all(iam, principal_id, scope, needed)
            self._keep_an_org_admin(iam, principal_id, scope, role in INHERITING_ROLES)

        await self._run(work, as_api=by is None, user=by)

    async def grant(
        self,
        user_id: str,
        role: str,
        scope: str,
        *,
        by: Any = None,
    ) -> None:
        """Hold ``role`` at ``scope`` and no other role there.

        In a grouped container (#1585) the role is mapped onto its groups:

        | role at a workspace W | groups |
        |---|---|
        | viewer | "Viewers" (level), "<W> workspace"; not "<W> admins" |
        | member | "Members" (level), "<W> workspace"; not "<W> admins" |
        | admin, owner | "Members" (level), "<W> workspace", "<W> admins" |

        | role at an organization O | groups |
        |---|---|
        | viewer, member | "<O> people", and that level; not "<O> admins" |
        | admin, owner | "<O> people", "<O> admins"; the level unchanged |

        A level is one choice: giving viewer or member somewhere changes it
        everywhere. The roles of before held at the scope are detached. Owner is no
        longer assigned (an admin is made). Elsewhere, ``builtin.<role>`` attached at
        the scope, as before.

        ``by``: the user making the change, whose rights IAM checks; ``None`` for
        the system (seeding, the admin of what was just created).
        """
        if role not in _RANK:
            raise ValueError(f"Unknown role {role!r}")

        if not await self._vouched(user_id):
            raise UnknownUserError(user_id)
        record = await CONTAINER_DEFAULTS.grouped_record(scope)

        changes: list[GroupChange] = []

        def work(iam: Any) -> None:
            principal_id = self._principal_id(iam, user_id)
            if record is not None:
                plan = self._plan(iam, principal_id, role, scope, record)
                self._require_plan(iam, plan, scope)
                self._keep_an_org_admin(iam, principal_id, scope, bool(plan.org_admin_after))
                self._apply_plan(iam, plan, by=by, changes=changes, container=scope)
                return
            held = self._held(iam, principal_id, scope)
            needed = [("iam:DetachPolicy", other) for other in held if other != role]
            if role not in held:
                needed.append(("iam:AttachPolicy", role))
            # Every change is checked before the first is made: a refused
            # demotion must not leave the extra role it would have added.
            self._require_all(iam, principal_id, scope, needed)
            self._keep_an_org_admin(iam, principal_id, scope, role in INHERITING_ROLES)
            iam.attach_policy(_POLICY_OF[role], principal_id, scope)
            for other in held:
                if other != role:
                    iam.detach_policy(_POLICY_OF[other], principal_id, scope)
            self.mirror_org_wide(iam, principal_id, scope, role)

        await self._run(work, as_api=by is None, user=by)
        await self._audit(changes)
        await self._notify(scope)

    async def seed_capabilities(
        self, entries: Sequence[tuple[str, str | None, str]]
    ) -> tuple[int, list[str]]:
        """Put people in capability groups as the system (the configuration's
        declarations; #1589): ``(user id, org id, capability)``, the group made if
        missing (``capabilities.ensure_capability``; "Models · all" is the
        platform's, ``org id`` unused). Returns how many joined, and what was
        skipped: an unknown capability, or "Workflow runners" of an organization
        with no "<O> access" to bound it (recorded before #1585)."""
        from naas_abi.apps.nexus.apps.api.app.services.iam.capabilities import (
            NAMES,
            ensure_capability,
        )

        bounds: dict[str, str | None] = {}
        for _user, org_id, key in entries:
            if key == "workflow_runners" and org_id and org_id not in bounds:
                record = await CONTAINER_DEFAULTS.record_of(org_container(org_id))
                bounds[org_id] = record.access_policy_id if record is not None else None

        def work(iam: Any) -> tuple[int, list[str]]:
            joined, skipped = 0, []
            for user_id, org_id, key in dict.fromkeys(entries):
                if key not in NAMES:
                    skipped.append(f"{key}: not a capability group")
                    continue
                if key == "workflow_runners" and not (org_id and bounds.get(org_id)):
                    skipped.append(f"{key} of {org_id}: no organization access to bound it")
                    continue
                group = ensure_capability(
                    iam, org_id or "", key, org_access=bounds.get(org_id or "")
                )
                principal_id = self._principal_id(iam, user_id)
                if principal_id in iam.list_group_members(group.group_id):
                    continue
                iam.add_group_member(group.group_id, principal_id)
                joined += 1
            return joined, skipped

        return await self._run(work)

    async def seed(self, entries: list[tuple[str, str, str]], *, replace: bool) -> tuple[int, int]:
        """Grant ``(user id, role, scope)`` entries as the system: the config's
        declarations (``replace``: the role named wins) or the migration of old
        membership rows (kept where IAM already holds a role). In a grouped
        container, as ``grant`` maps it. Returns ``(granted, kept)``."""
        records = {
            scope: await CONTAINER_DEFAULTS.grouped_record(scope)
            for scope in dict.fromkeys(scope for _u, _r, scope in entries)
        }

        def work(iam: Any) -> tuple[int, int]:
            granted = kept = 0
            for user_id, role, scope in entries:
                if role not in _RANK:
                    raise ValueError(f"Unknown role {role!r}")
                principal_id = self._principal_id(iam, user_id)
                record = records.get(scope)
                if record is not None:
                    held_now = _Reading(iam).roles_of(principal_id).get(scope, [])
                    if held_now and not replace:
                        kept += 1
                        continue
                    plan = self._plan(iam, principal_id, role, scope, record)
                    if self._apply_plan(iam, plan):
                        granted += 1
                    else:
                        kept += 1
                    continue
                held = self._held(iam, principal_id, scope)
                if (held and not replace) or held == [role]:
                    kept += 1
                    self.mirror_org_wide(iam, principal_id, scope, best(held))
                    continue
                iam.attach_policy(_POLICY_OF[role], principal_id, scope)
                for other in held:
                    if other != role:
                        iam.detach_policy(_POLICY_OF[other], principal_id, scope)
                self.mirror_org_wide(iam, principal_id, scope, role)
                granted += 1
            return granted, kept

        result = await self._run(work)
        for scope in dict.fromkeys(scope for _user, _role, scope in entries):
            await self._notify(scope)
        return result

    async def revoke(self, user_id: str, scope: str, *, by: Any = None) -> bool:
        """Drop every role the user holds at ``scope`` (in a grouped container: leave
        its membership and admins groups; the level stays, it is the person's). True
        when there was one. ``LastOrgAdminError`` for an organization's last admin."""

        vouched = await self._vouched(user_id)
        record = await CONTAINER_DEFAULTS.grouped_record(scope)

        changes: list[GroupChange] = []

        def work(iam: Any) -> bool:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return False
            if record is not None:
                plan = self._plan(iam, principal_id, None, scope, record)
                self._require_plan(iam, plan, scope)
                self._keep_an_org_admin(iam, principal_id, scope, False)
                return self._apply_plan(iam, plan, by=by, changes=changes, container=scope)
            held = self._held(iam, principal_id, scope)
            self._require_all(iam, principal_id, scope, [("iam:DetachPolicy", r) for r in held])
            if held:
                self._keep_an_org_admin(iam, principal_id, scope, False)
            for role in held:
                iam.detach_policy(_POLICY_OF[role], principal_id, scope)
            self.mirror_org_wide(iam, principal_id, scope, None)
            return bool(held)

        revoked = await self._run(work, as_api=by is None, user=by)
        await self._audit(changes)
        await self._notify(scope)
        return revoked

    # -- containers -----------------------------------------------------------------

    async def register_workspace(self, org_id: str | None, workspace_id: str) -> str:
        """Register a workspace with IAM as a container, in its organization's (both
        registered here) or at the platform for one in none; returns its name."""

        def work(iam: Any) -> str:
            parent = PLATFORM
            if org_id:
                parent = iam.register_container(SERVICE, ORGANIZATION, org_id).name
            return iam.register_container(SERVICE, WORKSPACE, workspace_id, parent=parent).name

        container = await self._run(work)
        self._authz.forget_workspace(workspace_id)
        return container

    async def register_org(self, org_id: str) -> str:
        """Register an organization with IAM as a container; returns its name."""
        return await self._run(
            lambda iam: iam.register_container(SERVICE, ORGANIZATION, org_id).name
        )

    async def containers_in(self, org_id: str) -> list[str]:
        """The names of the containers IAM registers inside an organization (its
        workspaces, and any a module put there)."""
        container = org_container(org_id)

        def work(iam: Any) -> list[str]:
            return sorted(c.name for c in iam.list_containers() if c.parent == container)

        return await self._run(work)

    async def drop_scope(self, org_id: str | None, workspace_id: str | None) -> None:
        """Forget a deleted workspace (or, with no workspace, organization): IAM
        deletes its container, with what it owns, every attachment at it and
        below it, and every container below it."""
        if workspace_id:
            scope = workspace_container(org_id, workspace_id)
            await self._run(lambda iam: iam.delete_container(SERVICE, WORKSPACE, workspace_id))
            self._authz.forget_workspace(workspace_id)
            await self._notify(scope, dropped=True)
            return
        if org_id:
            await self._run(lambda iam: iam.delete_container(SERVICE, ORGANIZATION, org_id))
            self._authz.forget_workspaces()  # its workspaces went with it


MEMBERSHIPS = Memberships()

__all__ = [
    "MEMBERSHIPS",
    "LastOrgAdminError",
    "ROLE_NAMES",
    "DirectoryEntry",
    "Member",
    "MembershipDenied",
    "Memberships",
    "best",
    "role_of_policy",
    "roles",
]
