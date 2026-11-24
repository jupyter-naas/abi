"""Users › Role: what a change of a member's roles at a workspace does (``plan_role_change``)."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.workspaces.roles import (
    KEEP,
    RoleChangeRefused,
    RoleGroups,
    plan_role_change,
)

GROUPS = RoleGroups(
    own="grp_w", admins="grp_wa", members="grp_m", viewers="grp_v", elsewhere=frozenset({"grp_oa"})
)


def plan(current, wanted, policies=None, wanted_policies=(), otherwise=False):
    return plan_role_change(
        current_groups=set(current),
        current_policies=dict(policies or {}),
        wanted_groups=set(wanted),
        wanted_policies=set(wanted_policies),
        groups=GROUPS,
        reaches_otherwise=otherwise,
    )


def test_nothing_asked_changes_nothing():
    change = plan({"grp_w", "grp_m"}, {"grp_w", "grp_m"})
    assert (
        change.level,
        change.admin,
        change.join,
        change.leave,
        change.attach,
        change.detach,
    ) == (KEEP, None, [], [], [], [])


def test_the_level_admin_groups_and_policies_follow_what_is_asked():
    change = plan(
        {"grp_w", "grp_m", "grp_old"},
        {"grp_w", "grp_wa", "grp_m", "grp_runners"},
        policies={"pol_a": "abi:w"},
        wanted_policies={"pol_b"},
    )
    assert change.level == KEEP and change.admin is True
    assert change.join == ["grp_runners"] and change.leave == ["grp_old"]
    assert change.attach == ["pol_b"] and change.detach == [("pol_a", "abi:w")]
    assert plan({"grp_w", "grp_m"}, {"grp_w", "grp_v"}).level == "viewer"
    assert plan({"grp_w", "grp_wa", "grp_m"}, {"grp_w", "grp_m"}).admin is False


def test_the_workspace_group_and_what_is_managed_elsewhere_never_move_here():
    change = plan({"grp_w", "grp_m", "grp_oa"}, {"grp_m", "grp_x"})
    assert change.join == ["grp_x"] and change.leave == []
    assert plan({"grp_w", "grp_m"}, {"grp_w", "grp_m", "grp_oa"}).join == []


def test_one_level_and_an_admin_is_a_member():
    with pytest.raises(RoleChangeRefused, match="one level"):
        plan({"grp_w", "grp_m"}, {"grp_w", "grp_m", "grp_v"})
    with pytest.raises(RoleChangeRefused, match="Member"):
        plan({"grp_w", "grp_v"}, {"grp_w", "grp_v", "grp_wa"})


def test_someone_left_with_nothing_to_use_is_refused():
    with pytest.raises(RoleChangeRefused, match="use nothing"):
        plan({"grp_w", "grp_m"}, {"grp_w"})
    # A policy, the admins group, or another role (an organization's admin) is enough.
    assert plan({"grp_w", "grp_m"}, {"grp_w"}, wanted_policies={"pol_a"}).level is None
    assert plan({"grp_w", "grp_m"}, {"grp_w"}, otherwise=True).level is None
