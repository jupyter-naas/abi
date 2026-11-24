"""Users › Role: a change of a member's roles at a workspace, planned.

A member's Role at a workspace is the groups they are in and the policies attached to
them there (``Memberships.roles_at``). Changing it asks for the groups and policies
wanted; ``plan_role_change`` says what that means, or why it cannot be: their level
(Members or Viewers, one choice for every workspace they work in), whether they
administer the workspace, the other groups to join or leave, the policies to attach or
detach. The workspace's own group never moves here (removing someone takes them out),
nor what is managed elsewhere (their organization's people and admins).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

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
