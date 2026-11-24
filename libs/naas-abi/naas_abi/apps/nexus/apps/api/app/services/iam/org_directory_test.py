"""The organization's directory: everyone with a role in the organization or in
one of its workspaces, derived from IAM's attachments (nothing stored)."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS


@pytest.fixture
def world(nexus_iam):
    """org-1 with ws-1 and ws-2; org-2 with ws-9; a personal workspace in none."""
    org = nexus_iam.org("org-1")
    ws1 = nexus_iam.workspace("org-1", "ws-1")
    ws2 = nexus_iam.workspace("org-1", "ws-2")
    other = nexus_iam.workspace("org-2", "ws-9")
    solo = nexus_iam.workspace(None, "ws-solo")
    nexus_iam.grant("ada", "owner", org)
    nexus_iam.grant("ben", "member", org)
    nexus_iam.grant("ben", "viewer", ws1)
    nexus_iam.grant("cleo", "member", ws1)
    nexus_iam.grant("cleo", "admin", ws2)
    nexus_iam.grant("dan", "viewer", ws2)
    nexus_iam.grant("eve", "admin", other)
    nexus_iam.grant("eve", "owner", solo)
    return nexus_iam


@pytest.mark.asyncio
async def test_the_directory_holds_org_members_and_workspace_only_people(world) -> None:
    entries = {e.user_id: e for e in await MEMBERSHIPS.org_directory("org-1")}

    assert set(entries) == {"ada", "ben", "cleo", "dan"}
    assert (entries["ada"].role, entries["ada"].source, entries["ada"].org_wide) == (
        "owner",
        "organization",
        True,
    )
    assert (entries["ben"].role, entries["ben"].source) == ("member", "organization")
    assert entries["ben"].workspace_ids == ("ws-1",)
    assert (entries["cleo"].role, entries["cleo"].source) == (None, "workspace")
    assert entries["cleo"].workspace_ids == ("ws-1", "ws-2")
    assert (entries["dan"].role, entries["dan"].source, entries["dan"].org_wide) == (
        None,
        "workspace",
        False,
    )
    assert entries["cleo"].principal_id == world.principal("cleo")


@pytest.mark.asyncio
async def test_other_organizations_and_orgless_workspaces_stay_out(world) -> None:
    assert {e.user_id for e in await MEMBERSHIPS.org_directory("org-2")} == {"eve"}
    assert await MEMBERSHIPS.org_directory("org-unknown") == []


@pytest.mark.asyncio
async def test_org_members_come_first_by_rank_then_workspace_only_people(world) -> None:
    order = [e.user_id for e in await MEMBERSHIPS.org_directory("org-1")]

    assert order == ["ada", "ben", "cleo", "dan"]


@pytest.mark.asyncio
async def test_every_directory_is_read_in_one_pass(world, monkeypatch) -> None:
    calls = []
    original = MEMBERSHIPS.members_by_scope

    def counting(iam, scope=None, **kwargs):
        calls.append(scope)
        return original(iam, scope, **kwargs)

    monkeypatch.setattr(MEMBERSHIPS, "members_by_scope", counting)

    found = await MEMBERSHIPS.org_directories()

    assert calls == [None]
    assert {org: {e.user_id for e in entries} for org, entries in found.items()} == {
        "org-1": {"ada", "ben", "cleo", "dan"},
        "org-2": {"eve"},
    }


@pytest.mark.asyncio
async def test_one_directory_resolves_only_the_organizations_people(world, monkeypatch) -> None:
    """Naming a principal costs an IAM read: one org's directory names its own
    people, never the platform's."""
    named = []
    original = MEMBERSHIPS._user_id

    def counting(iam, principal_id):
        named.append(principal_id)
        return original(iam, principal_id)

    monkeypatch.setattr(MEMBERSHIPS, "_user_id", counting)

    assert {e.user_id for e in await MEMBERSHIPS.org_directory("org-2")} == {"eve"}
    assert set(named) == {world.principal("eve")}


# -- read from the groups (#1589) ----------------------------------------------------------


@pytest.fixture
def grouped():
    """org-g with ws-a and ws-b, whose people are groups (#1585), set by hand: the
    directory reads the groups themselves, whatever the people hold beside."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
    from naas_abi_core.engine.call_context import as_service_account

    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        org = nexus.grouped_org("org-g", "Acme")
        ws_a = nexus.grouped_workspace("org-g", "ws-a", "Alpha")
        ws_b = nexus.grouped_workspace("org-g", "ws-b", "Beta")
        with as_service_account("api"):
            for user, groups in {
                "ada": [org.members_group_id, org.admins_group_id],
                "ben": [org.members_group_id],
                "cleo": [ws_a.members_group_id, ws_b.members_group_id, ws_b.admins_group_id],
                # In a workspace's group and no level group: still in the directory.
                "dan": [ws_a.members_group_id],
            }.items():
                principal = nexus.principal(user)
                for group in groups:
                    nexus.iam.add_group_member(group, principal)
        yield nexus


@pytest.mark.asyncio
async def test_the_directory_is_read_from_the_organizations_groups(grouped) -> None:
    entries = {e.user_id: e for e in await MEMBERSHIPS.org_directory("org-g")}

    assert set(entries) == {"ada", "ben", "cleo", "dan"}
    assert (entries["ada"].role, entries["ada"].source, entries["ada"].org_wide) == (
        "admin",
        "organization",
        True,
    )
    # "<O> people": the organization's own people, Viewer access there.
    assert (entries["ben"].role, entries["ben"].source) == ("viewer", "organization")
    assert (entries["cleo"].role, entries["cleo"].workspace_ids) == (None, ("ws-a", "ws-b"))
    assert (entries["dan"].source, entries["dan"].workspace_ids) == ("workspace", ("ws-a",))
    members_b = {
        m.user_id: m.role for m in await MEMBERSHIPS.members(grouped.workspace("org-g", "ws-b"))
    }
    assert members_b == {"cleo": "admin"}
