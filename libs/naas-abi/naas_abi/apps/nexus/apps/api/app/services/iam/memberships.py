"""Memberships are IAM's role attachments (RFC §7, §13): the only record of who
holds which role in an organization or a workspace.

A role is ``builtin.<role>`` attached to the user's principal at the scope of
the organization (``abi:<org>:-``) or the workspace (``abi:<org>:<workspace>``).
A Nexus user the built-in login created holds IAM's user of issuer
``urn:abi:nexus`` (subject: its Nexus id); a user of an identity provider is its
principal id (``usr_…``) itself.

Reads run as ``api`` for no user, after the route authorized its caller with the
Nexus action (``ListWorkspaceMembers``). Changes run as ``api`` on behalf of the
caller, so IAM checks them too: an admin cannot grant or take away ``owner``
(bug c), however the API is called. Seeding and the owner of a new org or
workspace are granted as ``api`` for no user.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_scope,
    workspace_scope,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER, attachment_resource
from naas_abi_core.services.iam.names import scope_fields
from starlette.concurrency import run_in_threadpool

_T = TypeVar("_T")
_PRINCIPAL_ID = re.compile(r"^usr_[0-9a-z]{26}$")

ROLE_NAMES = ("owner", "admin", "member", "viewer")
# Organization owners and admins reach every workspace of their organization
# (ADR 20261014_nexus-platform-managed-users): the org role is also held
# organization-wide (``abi:<org>:*``), which IAM reaches into every workspace.
# Members and viewers of an organization inherit nothing.
INHERITING_ROLES = ("owner", "admin")
_RANK = {name: len(ROLE_NAMES) - index for index, name in enumerate(ROLE_NAMES)}
_POLICY_OF = {name: f"builtin.{name}" for name in ROLE_NAMES}


class MembershipDenied(PermissionError):
    """IAM refused a change of roles to the caller."""


@dataclass(frozen=True)
class Member:
    user_id: str
    role: str
    principal_id: str
    since: datetime | None = None


def wide_scope(scope: str) -> str | None:
    """The organization-wide scope (``abi:<org>:*``) of an organization's own scope
    (``abi:<org>:-``); None for any other scope."""
    org, workspace = scope_fields(scope)
    return f"abi:{org}:*" if workspace == "-" and org != "-" else None


def role_of_policy(policy_id: str) -> str | None:
    name = policy_id.removeprefix("builtin.")
    return name if policy_id.startswith("builtin.") and name in _RANK else None


def best(role_names: list[str]) -> str | None:
    return max(role_names, key=_RANK.__getitem__, default=None)


RolesListener = Callable[[str, bool], Awaitable[None]]


class UnknownUserError(ValueError):
    """The id names no user Nexus (or IAM) knows, or not a user at all."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"{user_id} is not a known user")
        self.user_id = user_id


class Memberships:
    def __init__(self, authz: Authz = AUTHZ) -> None:
        self._authz = authz
        self._listeners: list[RolesListener] = []
        # Whether a (legacy) Nexus user id is a user Nexus has; set where the
        # users live (the application's startup). None: every id is vouched for.
        self.known_user: Callable[[str], Awaitable[bool]] | None = None

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
        org, workspace = scope_fields(scope)
        if workspace in ("-", "*") or org == "-":
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

    async def members(self, scope: str) -> list[Member]:
        """Who holds a role at ``scope``, each with the highest they hold."""

        def work(iam: Any) -> list[Member]:
            held: dict[str, list[str]] = {}
            since: dict[str, datetime] = {}
            for role, policy in _POLICY_OF.items():
                for attachment in iam.list_attachments(policy_id=policy):
                    if attachment.scope == scope:
                        held.setdefault(attachment.principal_id, []).append(role)
                        if attachment.created_at is not None:
                            since[attachment.principal_id] = min(
                                attachment.created_at,
                                since.get(attachment.principal_id, attachment.created_at),
                            )
            found = []
            for principal_id, names in held.items():
                try:
                    user_id = self._user_id(iam, principal_id)
                except (IAMNotFoundError, ResourceNotFoundError):
                    continue
                found.append(
                    Member(user_id, best(names) or "viewer", principal_id, since.get(principal_id))
                )
            return sorted(found, key=lambda m: (-_RANK[m.role], m.user_id))

        return await self._run(work)

    async def platform_admins(self) -> set[str]:
        """The users who hold ``builtin.platform_admin``, by the id Nexus names them."""

        def work(iam: Any) -> set[str]:
            found: set[str] = set()
            for attachment in iam.list_attachments(policy_id=roles.PLATFORM_ADMIN):
                try:
                    found.add(self._user_id(iam, attachment.principal_id))
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
            if on:
                iam.attach_policy(roles.PLATFORM_ADMIN, principal_id)
            else:
                iam.detach_policy(roles.PLATFORM_ADMIN, principal_id)

        await self._run(work, as_api=by is None, user=by)

    async def role_at(self, user_id: str, scope: str) -> str | None:
        """The highest role the user holds directly at ``scope``."""
        return (await self.roles_of(user_id)).get(scope)

    async def inherited_role(self, user_id: str, org_id: str) -> str | None:
        """The role the user holds in every workspace of ``org_id`` through their
        organization role (an owner or admin of the organization), if any."""
        return (await self.roles_of(user_id)).get(f"abi:{org_id}:*")

    async def org_wide_orgs_of(self, user_id: str) -> list[str]:
        """The orgs whose every workspace the user reaches (they hold a role
        organization-wide there: an org owner or admin)."""
        found = []
        for scope in await self.roles_of(user_id):
            org, workspace = scope_fields(scope)
            if workspace == "*" and org != "-":
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
            held: dict[str, list[str]] = {}
            for attachment in iam.list_attachments(principal_id=principal_id):
                role = role_of_policy(attachment.policy_id)
                if role is not None and attachment.scope is not None:
                    held.setdefault(attachment.scope, []).append(role)
            return {scope: best(names) or "viewer" for scope, names in held.items()}

        return await self._run(work)

    async def workspaces_of(self, user_id: str) -> list[tuple[str, str]]:
        """``(org, workspace)`` of every workspace the user holds a role in directly."""
        found = []
        for scope in await self.roles_of(user_id):
            org, workspace = scope_fields(scope)
            if workspace not in ("-", "*") and org != "-":
                found.append((org, workspace))
        return sorted(found)

    async def scopes_of(self, user_id: str, *, level: str) -> dict[str, str]:
        """The user's roles at ``level``: ``"org"`` (``abi:<org>:-``) or
        ``"workspace"`` (``abi:<org>:<ws>``), keyed by the org or workspace id."""
        found: dict[str, str] = {}
        for scope, role in (await self.roles_of(user_id)).items():
            org, workspace = scope_fields(scope)
            if level == "org" and workspace == "-" and org != "-":
                found[org] = role
            elif level == "workspace" and workspace not in ("-", "*") and org != "-":
                found[workspace] = role
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
        """Hold the organization-wide role an organization ``role`` (``None``: no
        role) carries, and no other. Made as ``api`` for no user: IAM keeps
        organization-wide attachments from an org admin, so the change that
        asked for ``role`` was authorized at the organization's own scope first."""
        wide = wide_scope(scope)
        if wide is None:
            return
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

    async def check(
        self, user_id: str, role: str | None, scope: str, *, by: Any = None
    ) -> None:
        """Raise ``MembershipDenied`` unless ``by`` may give the user ``role`` at
        ``scope`` (``None``: take their roles away), changing nothing. Callers
        with rules of their own (an owner must remain) ask this first, so the
        caller's lack of rights is what they hear about."""

        vouched = await self._vouched(user_id)

        def work(iam: Any) -> None:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return  # no such user: nothing is held, nothing to refuse
            held = self._held(iam, principal_id, scope)
            needed = [("iam:DetachPolicy", other) for other in held if other != role]
            if role is not None and role not in held:
                needed.append(("iam:AttachPolicy", role))
            self._require_all(iam, principal_id, scope, needed)

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

        ``by``: the user making the change, whose rights IAM checks; ``None`` for
        the system (seeding, the owner of what was just created).
        """
        if role not in _RANK:
            raise ValueError(f"Unknown role {role!r}")

        if not await self._vouched(user_id):
            raise UnknownUserError(user_id)

        def work(iam: Any) -> None:
            principal_id = self._principal_id(iam, user_id)
            held = self._held(iam, principal_id, scope)
            needed = [("iam:DetachPolicy", other) for other in held if other != role]
            if role not in held:
                needed.append(("iam:AttachPolicy", role))
            # Every change is checked before the first is made: a refused
            # demotion must not leave the extra role it would have added.
            self._require_all(iam, principal_id, scope, needed)
            iam.attach_policy(_POLICY_OF[role], principal_id, scope)
            for other in held:
                if other != role:
                    iam.detach_policy(_POLICY_OF[other], principal_id, scope)
            self.mirror_org_wide(iam, principal_id, scope, role)

        await self._run(work, as_api=by is None, user=by)
        await self._notify(scope)

    async def seed(self, entries: list[tuple[str, str, str]], *, replace: bool) -> tuple[int, int]:
        """Grant ``(user id, role, scope)`` entries as the system: the config's
        declarations (``replace``: the role named wins) or the migration of old
        membership rows (kept where IAM already holds a role). Returns
        ``(granted, kept)``."""

        def work(iam: Any) -> tuple[int, int]:
            granted = kept = 0
            for user_id, role, scope in entries:
                if role not in _RANK:
                    raise ValueError(f"Unknown role {role!r}")
                principal_id = self._principal_id(iam, user_id)
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
        """Drop every role the user holds at ``scope``. True when there was one."""

        vouched = await self._vouched(user_id)

        def work(iam: Any) -> bool:
            principal_id = self._find_principal(iam, user_id, vouched=vouched)
            if principal_id is None:
                return False
            held = self._held(iam, principal_id, scope)
            self._require_all(iam, principal_id, scope, [("iam:DetachPolicy", r) for r in held])
            for role in held:
                iam.detach_policy(_POLICY_OF[role], principal_id, scope)
            self.mirror_org_wide(iam, principal_id, scope, None)
            return bool(held)

        revoked = await self._run(work, as_api=by is None, user=by)
        await self._notify(scope)
        return revoked

    # -- scopes -------------------------------------------------------------------

    async def register_workspace(self, org_id: str | None, workspace_id: str) -> str:
        """Tell IAM a workspace exists in its org (``iam:PutScope``); returns its scope."""
        scope = workspace_scope(org_id, workspace_id)
        org, _ = scope_fields(scope)

        def work(iam: Any) -> None:
            iam.put_scope(org)
            iam.put_scope(org, workspace_id)

        await self._run(work)
        self._authz.forget_workspace(workspace_id)
        return scope

    async def drop_scope(self, org_id: str | None, workspace_id: str | None) -> None:
        """Forget a deleted workspace (or, with no workspace, organization): its
        role and feature attachments, then its scope."""
        scope = workspace_scope(org_id, workspace_id) if workspace_id else org_scope(org_id or "")
        org, _ = scope_fields(scope)

        def work(iam: Any) -> None:
            held_policies = [
                *_POLICY_OF.values(),
                *(roles.feature_policy_id(key) for key in iam.feature_policy_keys()),
            ]
            scopes = {scope, wide_scope(scope)} - {None}
            for policy_id in held_policies:
                for attachment in iam.list_attachments(policy_id=policy_id):
                    if attachment.scope in scopes:
                        iam.detach_policy(policy_id, attachment.principal_id, attachment.scope)
            iam.delete_scope(org, workspace_id or "-")

        await self._run(work)
        if workspace_id:
            self._authz.forget_workspace(workspace_id)
            await self._notify(scope, dropped=True)

    async def register_org(self, org_id: str) -> str:
        await self._run(lambda iam: iam.put_scope(org_id))
        return org_scope(org_id)


MEMBERSHIPS = Memberships()

__all__ = [
    "MEMBERSHIPS",
    "ROLE_NAMES",
    "Member",
    "MembershipDenied",
    "Memberships",
    "best",
    "role_of_policy",
    "roles",
]
