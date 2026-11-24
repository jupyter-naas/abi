"""Users › Role, at a workspace, an organization or the platform: a change of a member's
roles planned, and the routes' shared part.

A member's Role at a workspace is the groups they are in and the policies attached to
them there (``Memberships.roles_at``). Changing it asks for the groups and policies
wanted; ``plan_role_change`` says what that means, or why it cannot be: their level
(Members or Viewers, one choice for every workspace they work in), whether they
administer the workspace, the other groups to join or leave, the policies to attach or
detach. The workspace's own group never moves here (removing someone takes them out),
nor what is managed elsewhere (their organization's people and admins).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from fastapi import HTTPException
from pydantic import BaseModel, Field

KEEP: Final = "keep"


class RoleChangeRefused(ValueError):
    """The roles asked cannot be someone's at the workspace."""


@dataclass(frozen=True)
class RoleGroups:
    """The groups of a workspace's Role: its own group, its admins group, the level
    groups, and those never offered there (``elsewhere``)."""

    own: str | None = None
    admins: str | None = None
    members: str | None = None
    viewers: str | None = None
    elsewhere: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoleChange:
    """``level``: "member", "viewer", None (no level any more) or ``KEEP``. ``admin``:
    True, False, or None (unchanged)."""

    level: str | None = KEEP
    admin: bool | None = None
    join: list[str] = field(default_factory=list)
    leave: list[str] = field(default_factory=list)
    attach: list[str] = field(default_factory=list)
    detach: list[tuple[str, str | None]] = field(default_factory=list)


def plan_role_change(
    *,
    current_groups: set[str],
    current_policies: dict[str, str | None],
    wanted_groups: set[str],
    wanted_policies: set[str],
    groups: RoleGroups,
    reaches_otherwise: bool,
) -> RoleChange:
    """What asking ``wanted_groups`` and ``wanted_policies`` for someone who holds
    ``current_groups`` and ``current_policies`` (policy -> the scope it is attached
    at) changes. ``reaches_otherwise``: another role gives them the workspace (an
    organization's or the platform's admin). ``RoleChangeRefused``: two levels, a
    Viewer who administers, or someone left with nothing to use there."""
    levels = {g for g in (groups.members, groups.viewers) if g}
    if len(wanted_groups & levels) > 1:
        raise RoleChangeRefused("Pick one level: Members or Viewers")
    admin_wanted = bool(groups.admins) and groups.admins in wanted_groups
    if admin_wanted and groups.viewers in wanted_groups:
        raise RoleChangeRefused("A workspace admin is a Member: a Viewer administers nothing")

    def level_in(held: set[str]) -> str | None:
        if groups.members and groups.members in held:
            return "member"
        if groups.viewers and groups.viewers in held:
            return "viewer"
        return None

    level_now, level_wanted = level_in(current_groups), level_in(wanted_groups)
    if not (level_wanted or admin_wanted or wanted_policies or reaches_otherwise):
        raise RoleChangeRefused(
            "They would use nothing in this workspace: keep a level (Members or Viewers), "
            "the admins group or a policy"
        )
    fixed = {g for g in (groups.own, groups.admins) if g} | levels | set(groups.elsewhere)
    admin_now = bool(groups.admins) and groups.admins in current_groups
    return RoleChange(
        level=KEEP if level_wanted == level_now else level_wanted,
        admin=None if admin_wanted == admin_now else admin_wanted,
        join=sorted((wanted_groups - fixed) - current_groups),
        leave=sorted((current_groups - fixed) - wanted_groups),
        attach=sorted(set(wanted_policies) - set(current_policies)),
        detach=sorted(
            ((p, s) for p, s in current_policies.items() if p not in wanted_policies),
            key=lambda item: (item[0], item[1] or ""),
        ),
    )


# -- the routes' part, shared by the levels ------------------------------------------------
# A workspace's, an organization's and the platform's Users each name their container, its
# Role's groups, and how their own seats are changed (a workspace's admins, an organization's
# admins and workspaces, the platform's admins); the rest is here.


class RoleOptionView(BaseModel):
    """A group or a policy a member's Role may hold: ``kind`` "level" (Members, Viewers:
    ``level``), "own" (the container's own group, never removed there), "admins", "group"
    (a capability group, a workspace's group at an organization, one an admin made) or
    "policy"."""

    kind: str
    id: str
    name: str
    level: str | None = None


class RoleOptionsView(BaseModel):
    groups: list[RoleOptionView] = Field(default_factory=list)
    policies: list[RoleOptionView] = Field(default_factory=list)


class MemberRolesInput(BaseModel):
    """The groups and policies wanted for a member (Users › Role)."""

    groups: list[str] = Field(default_factory=list, max_length=500)
    policies: list[str] = Field(default_factory=list, max_length=200)


async def iam_answer(call: Any) -> Any:
    """IAM's answer, or its refusal as the HTTP response it is."""
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
    from naas_abi_core.services.iam.IAMPorts import (
        IAMConflictError,
        IAMNotFoundError,
        PermissionDeniedError,
    )

    try:
        return await call
    except PermissionDeniedError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except IAMConflictError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except AuditUnavailable as exc:
        raise HTTPException(503, detail=f"No change made: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


async def role_groups_of(scope: str) -> RoleGroups:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    found = await MEMBERSHIPS.role_groups(scope)
    return RoleGroups(
        own=found.own,
        admins=found.admins,
        members=found.members,
        viewers=found.viewers,
        elsewhere=found.elsewhere,
    )


async def role_options(
    user: Any,
    scope: str,
    groups: RoleGroups,
    *,
    listed_at: str | None,
    more: Sequence[RoleOptionView] = (),
) -> RoleOptionsView:
    """What a member's Role at ``scope`` may hold, as ``user`` may give it: the levels,
    the container's own and admins groups, ``more`` (an organization's workspaces'
    groups), the other groups ``user`` lists at ``listed_at`` (None: the platform's),
    and the policies ``user`` may attach there. What is managed elsewhere is left out."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.levels import MEMBERS, VIEWERS
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import (
        get_iam_admin_service,
    )

    service = get_iam_admin_service()
    listed = await iam_answer(service.list_groups(user, scope=listed_at))
    items = listed.get("items", [])
    names = {str(g.get("id")): str(g.get("name") or g.get("id")) for g in items}
    options: list[RoleOptionView] = []
    for group_id, name, level in (
        (groups.members, MEMBERS, "member"),
        (groups.viewers, VIEWERS, "viewer"),
    ):
        if group_id:
            options.append(RoleOptionView(kind="level", id=group_id, name=name, level=level))
    for group_id, kind in ((groups.own, "own"), (groups.admins, "admins")):
        if group_id:
            options.append(
                RoleOptionView(kind=kind, id=group_id, name=names.get(group_id, group_id))
            )
    options += list(more)
    taken = {o.id for o in options} | set(groups.elsewhere)
    for item in items:
        group_id = str(item.get("id"))
        if group_id in taken or item.get("level_group"):
            continue
        options.append(RoleOptionView(kind="group", id=group_id, name=names[group_id]))
    attachable = await iam_answer(service.attachable(user, listed_at))
    policies = [
        RoleOptionView(kind="policy", id=str(p["id"]), name=str(p.get("name") or p["id"]))
        for p in attachable.get("items", [])
        if not p.get("managed")
    ]
    return RoleOptionsView(groups=options, policies=sorted(policies, key=lambda p: p.name.lower()))


async def held_roles(scope: str, principal_id: str, groups: RoleGroups) -> MemberRolesInput:
    """What a member holds at ``scope``, as a change of their Role starts from."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    held, policies = await MEMBERSHIPS.held_at(scope, principal_id)
    return MemberRolesInput(groups=sorted(held - groups.elsewhere), policies=sorted(policies))


async def change_roles(
    *,
    user: Any,
    scope: str,
    principal_id: str,
    body: MemberRolesInput,
    groups: RoleGroups,
    reaches_otherwise: bool,
    attach_at: str | None,
    seats: Callable[[RoleChange, set[str]], Awaitable[set[str]]],
) -> RoleChange:
    """Make a member's Role at ``scope`` what ``body`` asks (``plan_role_change``).
    ``seats(change, held)`` changes what the level's own rules guard (their level, the
    admins seat, an organization's workspaces) and returns the groups it took care of;
    the other groups are joined or left, and the policies attached (at ``attach_at``) or
    detached, as ``user`` through the IAM admin service, so IAM decides."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import (
        get_iam_admin_service,
    )

    held, policies = await MEMBERSHIPS.held_at(scope, principal_id)
    try:
        change = plan_role_change(
            current_groups=held,
            current_policies=policies,
            wanted_groups=set(body.groups),
            wanted_policies=set(body.policies),
            groups=groups,
            reaches_otherwise=reaches_otherwise,
        )
    except RoleChangeRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    service = get_iam_admin_service()
    handled = await seats(change, held)
    if change.level is None:
        for level_group in (groups.members, groups.viewers):
            if level_group and level_group in held:
                await iam_answer(service.remove_member(user, level_group, principal_id))
    for group_id in change.join:
        if group_id not in handled:
            await iam_answer(service.add_member(user, group_id, principal_id))
    for group_id in change.leave:
        if group_id not in handled:
            await iam_answer(service.remove_member(user, group_id, principal_id))
    for policy_id in change.attach:
        await iam_answer(service.attach(user, policy_id, principal_id, attach_at))
    for policy_id, at in change.detach:
        await iam_answer(service.detach(user, policy_id, principal_id, at))
    return change
