"""Levels as groups (#1585): where someone works is a membership group, what they do
there is their level, bounded by what the workspace offers.

A real IAM (``NexusIam``) with an organization and a workspace whose defaults are
made as Nexus makes them (``container_defaults``), and every membership given through
``MEMBERSHIPS`` (the role-based API mapped onto the groups). Nothing is mocked."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import widen_offer
from naas_abi.apps.nexus.apps.api.app.services.iam.levels import (
    LEVELS,
    MEMBER_ACCESS,
    VIEWER_ACCESS,
    VIEWER_FEATURES,
    WORKSPACE_ADMIN_ACCESS,
    level_document,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    ADMINS,
    MEMBERSHIP,
    MEMBERSHIPS,
    LastOrgAdminError,
    MembershipDenied,
    Seat,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_below,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.engine import (
    EngineAccessGateway,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes, roles

ORG = org_container("org-1")
PEOPLE = ("viewer", "member", "wadmin", "oadmin", "stranger", "bob")
OFFER = Offer.of(
    agents=[("people", "a")],
    apps=[("people", "app1")],
    workflows=[("people", "wf")],
    features=["chat", "apps", "datasets"],
)


class SimpleUser:
    def __init__(self, user_id: str) -> None:
        self.id = user_id
        self.name = user_id.title()


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        org = nexus.grouped_org("org-1", "Acme")
        with as_service_account("api"):
            # The platform admin widened the organization's offer (wf2 beyond W's).
            widen_offer(
                nexus.iam,
                org.access_policy_id,
                OFFER.merged(Offer.of(workflows=[("people", "wf2")])),
            )
        workspace = nexus.grouped_workspace("org-1", "ws-1", "Alpha", offer=OFFER)
        nexus.grouped_workspace("org-1", "ws-2", "Beta", offer=OFFER)
        for person in PEOPLE:
            nexus.user(person)
        nexus.platform_admin("root")
        nexus.W = workspace.container  # type: ignore[attr-defined]
        nexus.record = workspace  # type: ignore[attr-defined]
        yield nexus


async def _team(world) -> None:
    await MEMBERSHIPS.grant("oadmin", "admin", ORG)
    await MEMBERSHIPS.grant("member", "member", world.W)
    await MEMBERSHIPS.grant("viewer", "viewer", world.W)
    await MEMBERSHIPS.grant("wadmin", "admin", world.W)


def _can(world, user: str, action: str, resource: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return world.iam.authorize(action, resource).allowed


def _scope(world, kind: str, name: str) -> str:
    return module_scopes.scope_resource(kind, "people", name, container=world.W)


def _members(world, group_id: str) -> set[str]:
    with as_service_account("api"):
        return {world.iam.get_principal(p).subject for p in world.iam.list_group_members(group_id)}


# -- the generic level policies ----------------------------------------------------------


def test_the_level_policies_are_generic_and_written_once(world):
    """Features and module scopes by type, never an instance: what W offers is its
    bound's to say. One policy each, the platform's."""
    member = level_document(MEMBER_ACCESS).to_dict()
    resources = [r for s in member["statements"] for r in s["resources"]]
    assert "${scope}/module:agent/*" in resources and "${scope}/module:app/*" in resources
    assert "${scope}/nexus:feature/chat" in resources
    assert not any("workflow" in r for r in resources)
    viewer = [
        r for s in level_document(VIEWER_ACCESS).to_dict()["statements"] for r in s["resources"]
    ]
    assert sorted(r.rsplit("/", 1)[1] for r in viewer if "feature" in r) == ["apps", "datasets"]
    assert "${scope}/module:agent/*" not in viewer
    admin = [
        r
        for s in level_document(WORKSPACE_ADMIN_ACCESS).to_dict()["statements"]
        for r in s["resources"]
    ]
    assert "${scope}/module:workflow/*" in admin and "${scope}/module:pipeline/*" in admin
    levels = LEVELS.get(world.iam)
    with as_service_account("api"):
        named = [p.name for p in world.iam.list_policies(limit=500).items]
    for name in (VIEWER_ACCESS, MEMBER_ACCESS, WORKSPACE_ADMIN_ACCESS):
        assert named.count(name) == 1
    assert LEVELS.get(world.iam) == levels


# -- what a workspace's lists show ------------------------------------------------------


@pytest.mark.asyncio
async def test_the_lists_of_a_workspace_show_what_it_offers_and_nothing_beyond(world):
    """An org admin uses the organization's offer in each of its workspaces ("<O>
    access" below O: wf2 runs in ws-1, which does not offer it), and the platform
    admin everything. What a workspace's lists show (``filter_scopes``: agents,
    apps, workflows, the chat's agents) is within its offer, for everyone. An item
    with no module scope is another check's. Widening the offer shows the item."""
    await _team(world)
    assert _can(world, "oadmin", "module:RunWorkflow", _scope(world, "workflow", "wf2"))
    wf, wf2 = ModuleScope("workflow", "people", "wf"), ModuleScope("workflow", "people", "wf2")
    a, b = ModuleScope("agent", "people", "a"), ModuleScope("agent", "people", "b")
    items: list[ModuleScope | str] = [wf, wf2, a, b, "built in the workspace"]

    async def listed(user: str) -> list[ModuleScope | str]:
        return await world.authz.filter_scopes(
            items,
            user=SimpleUser(user),
            workspace="ws-1",
            scope_of=lambda item: item if isinstance(item, ModuleScope) else None,
        )

    assert await listed("oadmin") == [wf, a, "built in the workspace"]
    assert await listed("root") == [wf, a, "built in the workspace"]
    assert await listed("wadmin") == [wf, a, "built in the workspace"]
    assert await listed("member") == [a, "built in the workspace"]
    with as_service_account("api"):
        widen_offer(
            world.iam, world.record.access_policy_id, Offer.of(workflows=[("people", "wf2")])
        )
    assert await listed("oadmin") == [wf, wf2, a, "built in the workspace"]


def test_a_deployment_sets_the_features_of_each_level():
    """``feature_flags.level_features`` caps what a Viewer and a Member use (within
    each workspace's offer); unset, the defaults. A change rewrites the level
    policy in place at the next start: one policy each, never a second."""
    from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig

    def features(nexus, name):
        with as_service_account("api"):
            found = [p for p in nexus.iam.list_policies(limit=500).items if p.name == name]
        assert len(found) == 1, name
        return sorted(
            r.rsplit("/", 1)[1]
            for s in found[0].document.to_dict()["statements"]
            for r in s["resources"]
            if "/nexus:feature/" in r
        )

    nexus = NexusIam(
        FeatureFlagsConfig(level_features={"viewer": ["apps"], "member": ["apps", "chat"]}),
        features_with_roles=False,
    )
    with nexus.installed():
        LEVELS.get(nexus.iam)
        assert features(nexus, VIEWER_ACCESS) == ["apps"]
        assert features(nexus, MEMBER_ACCESS) == ["apps", "chat"]
        nexus.flags.level_features = {"member": ["apps", "chat", "graph"]}
        LEVELS.forget()
        LEVELS.get(nexus.iam)
        assert features(nexus, MEMBER_ACCESS) == ["apps", "chat", "graph"]
        # Unset for the Viewer: the default.
        assert features(nexus, VIEWER_ACCESS) == sorted(VIEWER_FEATURES)


# -- the matrix by level, inside IAM -----------------------------------------------------


@pytest.mark.asyncio
async def test_each_level_uses_what_it_gives_within_what_the_workspace_offers(world):
    await _team(world)
    W = world.W
    agent_a, agent_b = _scope(world, "agent", "a"), _scope(world, "agent", "b")
    app = _scope(world, "app", "app1")
    wf, wf2 = _scope(world, "workflow", "wf"), _scope(world, "workflow", "wf2")
    chat, files = f"{W}/nexus:feature/chat", f"{W}/nexus:feature/files"
    model = "abi:model_registry:model/acme-large"
    rows = {
        #            agent a, agent b, app,  wf,    wf2,   chat,  files, embed, chat model, update W
        "viewer": (False, False, True, False, False, False, False, True, False, False),
        "member": (True, False, True, False, False, True, False, True, False, False),
        "wadmin": (True, False, True, True, False, True, False, True, True, True),
        "oadmin": (True, False, True, True, True, True, False, True, True, True),
        "root": (True, True, True, True, True, True, True, True, True, True),
        "stranger": (False,) * 10,
    }
    for person, wanted in rows.items():
        seen = (
            _can(world, person, "module:UseAgent", agent_a),
            _can(world, person, "module:UseAgent", agent_b),
            _can(world, person, "module:OpenApp", app),
            _can(world, person, "module:RunWorkflow", wf),
            _can(world, person, "module:RunWorkflow", wf2),
            _can(world, person, "nexus:UseFeature", chat),
            _can(world, person, "nexus:UseFeature", files),
            _can(world, person, "model_registry:Embed", model),
            _can(world, person, "model_registry:Chat", model),
            _can(world, person, "nexus:UpdateWorkspace", W),
        )
        assert seen == wanted, person


@pytest.mark.asyncio
async def test_nothing_is_attached_to_a_person(world):
    await _team(world)
    with as_service_account("api"):
        for person in ("viewer", "member", "wadmin", "oadmin"):
            held = world.iam.list_attachments(principal_id=world.principal(person))
            assert [(a.policy_id, a.scope) for a in held] == [], person


@pytest.mark.asyncio
async def test_the_role_based_api_maps_onto_the_groups(world):
    """viewer or member -> the level plus "<W> workspace"; admin -> Member plus
    "<W> admins" plus "<W> workspace"; at the organization, "<O> admins" or "<O>
    people"."""
    await _team(world)
    levels = LEVELS.get(world.iam)
    record = world.record
    assert _members(world, record.members_group_id) == {"viewer", "member", "wadmin"}
    assert _members(world, record.admins_group_id) == {"wadmin"}
    assert _members(world, levels.members) == {"member", "wadmin"}
    assert _members(world, levels.viewers) == {"viewer"}
    assert _members(world, levels.workspace_admins) == {"wadmin", "oadmin"}
    assert await MEMBERSHIPS.roles_of("oadmin") == {ORG: "admin", org_below("org-1"): "admin"}
    # A demotion leaves "<W> admins", keeps the workspace and the level.
    await MEMBERSHIPS.grant("wadmin", "member", world.W)
    assert _members(world, record.admins_group_id) == set()
    assert _members(world, levels.workspace_admins) == {"oadmin"}
    assert await MEMBERSHIPS.role_at("wadmin", world.W) == "member"
    # Owner is no longer assigned: an admin is made.
    await MEMBERSHIPS.grant("bob", "owner", world.W)
    assert await MEMBERSHIPS.role_at("bob", world.W) == "admin"
    # Leaving the workspace keeps the level, which reaches nothing there any more.
    assert await MEMBERSHIPS.revoke("member", world.W)
    assert await MEMBERSHIPS.role_at("member", world.W) is None
    assert await MEMBERSHIPS.level_of("member") == "member"


@pytest.mark.asyncio
async def test_a_level_is_one_choice_for_every_workspace(world):
    await _team(world)
    beta = org_container("org-1") + "/nexus:workspace/ws-2"
    await MEMBERSHIPS.grant("member", "member", beta)
    assert await MEMBERSHIPS.role_at("member", beta) == "member"
    # Made a viewer in W, by W's admin: a viewer in Beta too.
    await MEMBERSHIPS.grant("member", "viewer", world.W, by=SimpleUser("wadmin"))
    assert await MEMBERSHIPS.role_at("member", beta) == "viewer"
    assert await MEMBERSHIPS.level_of("member") == "viewer"


@pytest.mark.asyncio
async def test_the_admin_of_a_workspace_manages_it_and_nobody_else_does(world):
    await _team(world)
    wadmin, member = SimpleUser("wadmin"), SimpleUser("member")
    await MEMBERSHIPS.grant("bob", "member", world.W, by=wadmin)
    assert await MEMBERSHIPS.role_at("bob", world.W) == "member"
    with pytest.raises(MembershipDenied):
        await MEMBERSHIPS.grant("stranger", "member", world.W, by=member)
    beta = org_container("org-1") + "/nexus:workspace/ws-2"
    with pytest.raises(MembershipDenied):
        await MEMBERSHIPS.grant("stranger", "member", beta, by=wadmin)
    # An org admin manages every workspace of the organization.
    await MEMBERSHIPS.grant("stranger", "admin", beta, by=SimpleUser("oadmin"))
    assert await MEMBERSHIPS.role_at("stranger", beta) == "admin"


@pytest.mark.asyncio
async def test_the_last_org_admin_stays(world):
    await _team(world)
    oadmin = SimpleUser("oadmin")
    with pytest.raises(LastOrgAdminError):
        await MEMBERSHIPS.grant("oadmin", "member", ORG, by=oadmin)
    with pytest.raises(LastOrgAdminError):
        await MEMBERSHIPS.revoke("oadmin", ORG, by=oadmin)
    with pytest.raises(LastOrgAdminError):
        await MEMBERSHIPS.check("oadmin", None, ORG, by=oadmin)
    await MEMBERSHIPS.grant("bob", "admin", ORG, by=oadmin)
    assert await MEMBERSHIPS.revoke("oadmin", ORG, by=SimpleUser("bob"))
    assert await MEMBERSHIPS.role_at("oadmin", ORG) is None
    # The people of the organization: "<O> people", at the organization's own level.
    await MEMBERSHIPS.grant("viewer", "viewer", ORG, by=SimpleUser("bob"))
    assert await MEMBERSHIPS.role_at("viewer", ORG) == "viewer"


@pytest.mark.asyncio
async def test_the_member_lists_show_workspace_and_level(world):
    await _team(world)
    members = {m.user_id: (m.role, m.level) for m in await MEMBERSHIPS.members(world.W)}
    assert members == {
        "viewer": ("viewer", "viewer"),
        "member": ("member", "member"),
        "wadmin": ("admin", "member"),
    }
    directory = {e.user_id: e for e in await MEMBERSHIPS.org_directory("org-1")}
    assert directory["member"].workspace_ids == ("ws-1",)
    assert directory["member"].level == "member"
    assert directory["oadmin"].role == "admin" and directory["oadmin"].org_wide


@pytest.mark.asyncio
async def test_the_member_list_of_one_scope_reads_that_scope_alone(world, monkeypatch):
    """One workspace's members are read from its people, not from every person's
    memberships across the deployment, and are what the full pass finds there: at
    each workspace, at the organization and below it."""
    await _team(world)
    other = workspace_container("org-1", "ws-2")
    for n in range(3):
        world.user(f"other{n}")
        await MEMBERSHIPS.grant(f"other{n}", "member" if n else "admin", other)
    with as_service_account("api"):
        full = MEMBERSHIPS.members_by_scope(world.iam)
    read: list[str] = []
    real = world.iam.list_memberships
    monkeypatch.setattr(world.iam, "list_memberships", lambda p: read.append(p) or real(p))
    for scope in (world.W, other, ORG, org_below("org-1")):
        listed = await MEMBERSHIPS.members(scope)
        assert [(m.user_id, m.role, m.level) for m in listed] == [
            (m.user_id, m.role, m.level) for m in full.get(scope, [])
        ], scope
    assert {m.user_id for m in await MEMBERSHIPS.members(world.W)} == {"viewer", "member", "wadmin"}
    assert not read


@pytest.mark.asyncio
async def test_the_people_gateway_joins_and_leaves_the_groups(world):
    """The people service's ``AccessGateway`` (#1589): seats in the groups, checked
    as the inviting person, and the level."""
    await _team(world)
    gateway = EngineAccessGateway(lambda: world.iam)
    seats = [Seat(world.W, MEMBERSHIP), Seat(world.W, ADMINS)]
    await gateway.check("bob", seats, level="member", by="oadmin", organization_id="org-1")
    for seat in seats:
        assert await gateway.join("bob", seat, by="oadmin", level="member")
    await gateway.set_level("bob", "member", by="oadmin")
    record, levels = world.record, LEVELS.get(world.iam)
    assert "bob" in _members(world, record.admins_group_id)
    assert "bob" in _members(world, record.members_group_id)
    assert "bob" in _members(world, levels.members)
    assert (await gateway.roles_of("bob")) == {world.W: "admin"}
    assert await gateway.held("bob", seats) == set(seats)
    for seat in reversed(seats):
        assert await gateway.leave("bob", seat, by="oadmin")
    assert "bob" not in _members(world, record.members_group_id)


@pytest.mark.asyncio
async def test_platform_admins_are_a_group(world):
    await MEMBERSHIPS.set_platform_admin("bob", True)
    assert "bob" in _members(world, LEVELS.get(world.iam).platform_admins)
    assert {"bob", "root"} <= await MEMBERSHIPS.platform_admins()
    assert _can(
        world, "bob", "nexus:DeletePlatformOrganization", "abi:nexus:organization_record/org-1"
    )
    await MEMBERSHIPS.set_platform_admin("bob", False)
    assert "bob" not in await MEMBERSHIPS.platform_admins()
    with as_service_account("api"):
        assert not world.iam.list_attachments(
            principal_id=world.principal("bob"), policy_id=roles.PLATFORM_ADMIN
        )


@pytest.mark.asyncio
async def test_a_member_chats_with_the_member_set_and_a_viewer_does_not(world):
    """The level groups hold the model sets (S3's ``level_model_policy_ids``),
    unscoped: a Member chats with the deployment's member set, a Viewer only embeds."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import model_sets

    with as_service_account("api"):
        model_sets.ensure_model_policies(world.iam, ["acme-large"], [])
    await _team(world)
    chosen, other = "abi:model_registry:model/acme-large", "abi:model_registry:model/other"
    assert _can(world, "member", "model_registry:Chat", chosen)
    assert not _can(world, "member", "model_registry:Chat", other)
    assert not _can(world, "viewer", "model_registry:Chat", chosen)
    assert _can(world, "viewer", "model_registry:Embed", other)
    assert _can(world, "wadmin", "model_registry:Chat", other)
