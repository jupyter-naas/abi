"""What each role may do, decided by IAM through the ``nexus`` catalog."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam import memberships as m
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, AuthzDenied
from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import (
    FEATURE_OF,
    LEVEL_OF,
    NEXUS_CATALOG,
    TYPE_OF,
    TYPES_BY_NAME,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_scope, workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam


@pytest.fixture
def world():
    nexus = NexusIam()
    scope = nexus.workspace("org-1", "ws-1")
    nexus.org("org-1")
    for user, role in (
        ("owner", "owner"),
        ("admin", "admin"),
        ("member", "member"),
        ("viewer", "viewer"),
    ):
        nexus.grant(user, role, scope)
    nexus.user("stranger")
    with nexus.installed():
        yield nexus


def of_feature(feature: str, level: str = "list") -> tuple[str, str | tuple[str, ...]]:
    """An action of ``feature`` at ``level`` and an id that names its resource."""
    action = next(a for a, f in FEATURE_OF.items() if f == feature and LEVEL_OF[a] == level)
    kind = TYPES_BY_NAME[TYPE_OF[action]]
    return action, ("a", "b") if kind.id == "path" else "x"


async def may(action: str, user: str, **target) -> bool:
    return await AUTHZ.allowed(action, user=user, workspace="ws-1", **target)


@pytest.mark.asyncio
async def test_roles_are_cumulative_by_the_level_of_the_action(world) -> None:
    tested = 0
    for action, level in LEVEL_OF.items():
        if action in {"UseFeature", "DeleteWorkspace", "DeleteOrganization"}:
            continue
        spec = NEXUS_CATALOG.action(action)
        kind = next(t for t in NEXUS_CATALOG.resource_types if t.name == spec.resource_types[0])
        if kind.placement == "platform" or action in {
            "CreateOrganization",
            "ListOrganizations",
            "GetOrganization",
            "UpdateOrganization",
            "ListOrganizationCatalog",
            "CreateWorkspace",
            "ListOrganizationMembers",
            "InviteOrganizationMember",
            "UpdateOrganizationMember",
            "RemoveOrganizationMember",
            "ListOrganizationDomains",
            "AddOrganizationDomain",
            "VerifyOrganizationDomain",
            "UpdateOrganizationDomain",
            "RemoveOrganizationDomain",
            "GetBilling",
            "UpdateBilling",
            "GetRoleFeatures",
            "UpdateRoleFeatures",
        }:
            continue  # org- and platform-level: checked below
        resource_id = "x" if kind.id == "opaque" else ("a", "b") if kind.id == "path" else ()
        if kind.personal:
            continue
        no_feature = {"feature": "chat"} if action in FEATURE_OF else {}
        results = {
            user: await AUTHZ.allowed(
                action, user=user, workspace="ws-1", id=resource_id, **no_feature
            )
            for user in ("viewer", "member", "admin", "owner")
        }
        expected = {
            "list": (True, True, True, True),
            "read": (True, True, True, True),
            "write": (False, True, True, True),
            "admin": (False, False, True, True),
        }[level]
        assert tuple(results.values()) == expected, (action, level, results)
        tested += 1
    assert tested > 50


@pytest.mark.asyncio
async def test_a_stranger_sees_nothing_of_the_workspace(world) -> None:
    for action in ("GetWorkspace", "ListWorkspaceMembers"):
        assert not await may(action, "stranger", id="x" if action != "GetWorkspace" else ())
    with pytest.raises(AuthzDenied) as denied:
        await AUTHZ.require("GetWorkspace", user="stranger", workspace="ws-1")
    assert denied.value.status_code == 403
    assert "access to this workspace" in denied.value.detail


@pytest.mark.asyncio
async def test_a_viewer_is_denied_a_write_with_403_and_a_missing_item_with_404(world) -> None:
    with pytest.raises(AuthzDenied) as denied:
        await AUTHZ.require("PutFile", user="viewer", workspace="ws-1", id=("workspace", "a.txt"))
    assert denied.value.status_code == 403
    # Another member's personal conversation is invisible to a viewer: not found.
    with pytest.raises(AuthzDenied) as hidden:
        await AUTHZ.require(
            "GetConversation", user="viewer", workspace="ws-1", id=("member", "c-1")
        )
    assert hidden.value.status_code == 404


@pytest.mark.asyncio
async def test_personal_conversations_belong_to_their_owner(world) -> None:
    assert await may("GetConversation", "member", id=("member", "c-1"))
    assert not await may("GetConversation", "member", id=("admin", "c-1"))
    assert not await may("GetConversation", "owner", id=("member", "c-1"))
    assert await may("ListConversations", "viewer", id=("viewer", "-"))
    assert not await may("ListConversations", "viewer", id=("member", "-"))


@pytest.mark.asyncio
async def test_a_disabled_feature_denies_its_actions_even_to_the_owner() -> None:
    flags = FeatureFlagsConfig(enabled_features=["chat", "files"])
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("owner", "owner", scope)
    nexus.grant("member", "member", scope)
    skills, skill = of_feature("skills")
    agents, agent = of_feature("agents", "write")
    with nexus.installed():
        assert await AUTHZ.allowed(
            "PutFile", user="member", workspace="ws-1", id=("workspace", "a")
        )
        # "skills" is not enabled in the deployment: nobody reaches it.
        assert not await AUTHZ.allowed(skills, user="owner", workspace="ws-1", id=skill)
        with pytest.raises(AuthzDenied) as denied:
            await AUTHZ.require(skills, user="owner", workspace="ws-1", id=skill)
        assert denied.value.status_code == 403
        assert "not available" in denied.value.detail
        assert not await AUTHZ.allowed(agents, user="member", workspace="ws-1", id=agent)


@pytest.mark.asyncio
async def test_role_features_follow_the_deployment_baseline() -> None:
    nexus = NexusIam()
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("member", "member", scope)
    nexus.grant("admin", "admin", scope)
    agents, agent = of_feature("agents", "write")
    with nexus.installed():
        # The default baseline: members have no "agents", admins have.
        assert not await AUTHZ.allowed(agents, user="member", workspace="ws-1", id=agent)
        assert await AUTHZ.allowed(agents, user="admin", workspace="ws-1", id=agent)
        assert await AUTHZ.allowed("ListFiles", user="member", workspace="ws-1", id=("w", "-"))


@pytest.mark.asyncio
async def test_any_of_the_callers_workspaces_may_allow_with_two_filters_in_all() -> None:
    nexus = NexusIam()
    pairs = [("org-1", "ws-1"), ("org-1", "ws-2"), ("org-2", "ws-3")]
    for org, workspace in pairs:
        nexus.workspace(org, workspace)
    nexus.grant("bob", "viewer", workspace_scope("org-1", "ws-1"))
    nexus.grant("bob", "member", workspace_scope("org-1", "ws-2"))
    nexus.grant("cleo", "viewer", workspace_scope("org-1", "ws-1"))
    nexus.grant("cleo", "admin", workspace_scope("org-2", "ws-3"))
    agents, agent = of_feature("agents", "write")
    calls: list[str] = []
    with nexus.installed():
        real = nexus.iam.filter

        def counting(action, resources):
            calls.append(action)
            return real(action, resources)

        nexus.iam.filter = counting  # type: ignore[method-assign]
        # Bob writes files in ws-2 (a member), whatever else he is elsewhere.
        assert await AUTHZ.allowed_in_any(
            "PutFile", user="bob", workspaces=pairs, id=("workspace", "a")
        )
        assert calls == ["nexus:UseFeature", "nexus:PutFile"]
        # Members have no "agents" by the baseline, admins do: only Cleo, in ws-3.
        assert not await AUTHZ.allowed_in_any(
            "PutFile", user="cleo", workspaces=pairs[:1], id=("workspace", "a")
        )
        assert not await AUTHZ.allowed_in_any(agents, user="bob", workspaces=pairs, id=agent)
        assert await AUTHZ.allowed_in_any(agents, user="cleo", workspaces=pairs, id=agent)
        assert not await AUTHZ.allowed_in_any(agents, user="cleo", workspaces=[], id=agent)


@pytest.mark.asyncio
async def test_a_key_scoped_to_reading_cannot_write_whatever_its_user_is(world) -> None:
    """A key of a member that was narrowed to reading files (``abi_scope``) reads
    like the member and writes nothing: the scope travels in the call's context
    and bounds every Nexus decision, whatever role the user holds."""
    from dataclasses import replace

    from naas_abi_core.engine.call_context import use_call_context

    read_files = (
        {
            "effect": "Allow",
            "actions": ["nexus:UseFeature", "nexus:ListFiles", "nexus:GetFile"],
            "resources": ["*"],
        },
    )
    scoped = replace(world.context("member"), scope=read_files)
    put, listed = ("PutFile", ("workspace", "a")), ("ListFiles", ("w", "-"))
    assert await may(put[0], "member", id=put[1])  # a session: no narrowing
    with use_call_context(scoped):
        assert await may(listed[0], "member", id=listed[1])
        assert not await may(put[0], "member", id=put[1])
        with pytest.raises(AuthzDenied) as denied:
            await AUTHZ.require(put[0], user="member", workspace="ws-1", id=put[1])
        assert denied.value.status_code in (403, 404)
    # The same member, no scope again: the narrowing was the key's, not theirs.
    assert await may(put[0], "member", id=put[1])


@pytest.mark.asyncio
async def test_a_workspace_registered_again_in_another_org_is_seen_at_once() -> None:
    nexus = NexusIam()
    nexus.workspace("org-1", "ws-1")
    with nexus.installed():
        assert await AUTHZ.org_of("ws-1") == "org-1"  # now cached
        # Deleted and registered again elsewhere: the cached org must not outlive it.
        await m.MEMBERSHIPS.drop_scope("org-1", "ws-1")
        await m.MEMBERSHIPS.register_workspace("org-2", "ws-1")
        assert await AUTHZ.org_of("ws-1") == "org-2"


@pytest.mark.asyncio
async def test_a_deleted_workspace_is_not_remembered() -> None:
    nexus = NexusIam()
    nexus.workspace("org-1", "ws-1")
    with nexus.installed():
        assert await AUTHZ.org_of("ws-1") == "org-1"
        await m.MEMBERSHIPS.drop_scope("org-1", "ws-1")
        assert await AUTHZ.org_of("ws-1") is None


@pytest.mark.asyncio
async def test_filter_keeps_what_the_caller_may_see(world) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    nexus = world
    other = nexus.workspace("org-1", "ws-2")
    nexus.grant("member", "viewer", other)
    ids = ["ws-1", "ws-2", "ws-3"]
    nexus.workspace("org-2", "ws-3")
    names = {
        i: nexus_resource("workspace", org=o, workspace=i)
        for i, o in zip(ids, ["org-1", "org-1", "org-2"], strict=True)
    }
    seen = await AUTHZ.filter("ListWorkspaces", ids, user="member", resource_of=lambda i: names[i])
    assert seen == ["ws-1", "ws-2"]
    assert (
        await AUTHZ.filter("ListWorkspaces", ids, user="stranger", resource_of=lambda i: names[i])
        == []
    )


@pytest.mark.asyncio
async def test_member_directory_and_billing_are_for_owners_and_admins(world) -> None:
    nexus = world
    nexus.grant("owner", "owner", org_scope("org-1"))
    nexus.grant("admin", "admin", org_scope("org-1"))
    nexus.grant("member", "member", org_scope("org-1"))
    nexus.grant("viewer", "viewer", org_scope("org-1"))
    for action, id_ in (
        ("ListOrganizationMembers", "-"),
        ("ListOrganizationDomains", "-"),
        ("GetBilling", ()),
    ):
        seen = {
            user: await AUTHZ.allowed(action, user=user, org="org-1", id=id_)
            for user in ("owner", "admin", "member", "viewer")
        }
        assert seen == {"owner": True, "admin": True, "member": False, "viewer": False}, action
    assert await AUTHZ.allowed("GetOrganization", user="viewer", org="org-1")
    assert not await AUTHZ.allowed("UpdateOrganization", user="member", org="org-1")


@pytest.mark.asyncio
async def test_only_owners_delete_a_workspace(world) -> None:
    assert await AUTHZ.allowed("DeleteWorkspace", user="owner", workspace="ws-1")
    assert not await AUTHZ.allowed("DeleteWorkspace", user="admin", workspace="ws-1")


# -- memberships: the owner's role is the owner's -----------------------------------------------------------


@pytest.mark.asyncio
async def test_an_admin_cannot_grant_demote_or_remove_an_owner(world) -> None:
    scope = workspace_scope("org-1", "ws-1")
    members = m.MEMBERSHIPS
    # Promoting anyone to owner is the owner's.
    with pytest.raises(m.MembershipDenied):
        await members.grant("member", "owner", scope, by="admin")
    # Demoting or removing the owner is too, and a refused demotion changes nothing.
    with pytest.raises(m.MembershipDenied):
        await members.grant("owner", "member", scope, by="admin")
    with pytest.raises(m.MembershipDenied):
        await members.revoke("owner", scope, by="admin")
    assert await members.role_at("owner", scope) == "owner"
    # An owner can, and an admin can manage the roles below owner.
    await members.grant("member", "admin", scope, by="owner")
    assert await members.role_at("member", scope) == "admin"
    await members.grant("member", "viewer", scope, by="admin")
    assert await members.role_at("member", scope) == "viewer"
    assert await members.revoke("member", scope, by="admin") is True
    assert await members.role_at("member", scope) is None
    await members.grant("admin", "owner", scope, by="owner")
    assert await members.role_at("admin", scope) == "owner"


@pytest.mark.asyncio
async def test_listing_members_reads_the_attachments(world) -> None:
    scope = workspace_scope("org-1", "ws-1")
    found = await m.MEMBERSHIPS.members(scope)
    assert [(x.user_id, x.role) for x in found] == [
        ("owner", "owner"),
        ("admin", "admin"),
        ("member", "member"),
        ("viewer", "viewer"),
    ]
    assert await m.MEMBERSHIPS.scopes_of("member", level="workspace") == {"ws-1": "member"}
