"""Levels as groups (#1585): where someone works is a membership group, what they do
there is their level, bounded by what the workspace offers.

A real IAM (``NexusIam``) with an organization and a workspace whose defaults are
made as Nexus makes them (``container_defaults``), and every membership given through
``MEMBERSHIPS`` (the role-based API mapped onto the groups). Nothing is mocked."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    PLATFORM,
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


@pytest.mark.asyncio
async def test_a_workspace_shows_the_features_it_offers_to_everyone(world):
    """What a workspace shows of its features (``user_feature_flags``) is within its offer,
    for everyone: a platform admin and an organization's admin too, whom IAM lets use
    more. Settings stays shown to whoever may administer it, to offer a feature again. A
    change of the offer shows at once."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.user_features import user_feature_flags

    await _team(world)
    keys = ["chat", "files", "settings"]

    async def shown(user: str) -> dict[str, bool]:
        flags = await user_feature_flags(user, [("org-1", "ws-1")], keys)
        assert flags is not None
        return {key: flags["ws-1"][key] for key in keys}

    W = world.W
    assert _can(world, "root", "nexus:UseFeature", f"{W}/nexus:feature/files")  # IAM allows
    assert await shown("root") == {"chat": True, "files": False, "settings": True}
    assert (await shown("oadmin"))["files"] is False
    assert (await shown("member"))["chat"] is True
    with as_service_account("api"):
        widen_offer(world.iam, world.record.access_policy_id, Offer.of(features=["files"]))
    world.authz.forget_offers()  # as an offer's change does
    assert (await shown("root"))["files"] is True


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
async def test_a_role_is_the_groups_and_policies_that_bear_on_the_workspace(world):
    """Workspace settings › Users › Role: each person's groups owned by the platform, the
    workspace's organization or the workspace itself, and the policies attached to them
    there (or everywhere); never another workspace's."""
    await _team(world)
    await MEMBERSHIPS.grant("member", "member", workspace_container("org-1", "ws-2"))
    with as_service_account("api"):
        reports = world.iam.create_policy(
            "Alpha reports",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["nexus:UseFeature"],
                        "resources": ["${scope}/nexus:feature/chat"],
                    }
                ],
            },
        )
        world.iam.attach_policy(reports.id, world.principal("member"), world.W)
        elsewhere = world.iam.create_policy(
            "Beta reports",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["nexus:UseFeature"],
                        "resources": ["${scope}/nexus:feature/chat"],
                    }
                ],
            },
        )
        world.iam.attach_policy(
            elsewhere.id, world.principal("member"), workspace_container("org-1", "ws-2")
        )
        # Kept in step with their groups, never given by hand: not a role.
        shared = world.iam.create_policy(
            "workspace.ws-2.graphs.read",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["triple_store:Query"],
                        "resources": ["abi:triple_store:graph/shared"],
                    }
                ],
            },
        )
        world.iam.attach_policy(shared.id, world.principal("member"))
        world.iam.attach_policy(reports.id, world.principal("member"), ORG)
        copy = world.iam.create_policy(
            "Alpha reports",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["nexus:UseFeature"],
                        "resources": ["${scope}/nexus:feature/chat"],
                    }
                ],
            },
        )
        world.iam.attach_policy(copy.id, world.principal("member"), ORG)
    people = {p: world.principal(p) for p in ("member", "viewer", "wadmin", "oadmin")}
    roles = await MEMBERSHIPS.roles_at(world.W, list(people.values()))
    names = {p: [r.name for r in roles[people[p]]] for p in people}
    # The workspace's group first, then what counts: an admin's group (the organization's
    # before the workspace's), else their level; then policies. Never what is automatic
    # ("<O> people", Workspace admins), nor the level of an admin.
    assert names["member"] == ["Alpha workspace", "Members", "Alpha reports"]
    assert names["viewer"] == ["Alpha workspace", "Viewers"]
    assert names["wadmin"] == ["Alpha workspace", "Alpha admins"]
    assert names["oadmin"] == ["Alpha workspace", "Acme admins"]
    implied = {p: [r.name for r in roles[people[p]] if r.implied] for p in people}
    assert implied["member"] == [] and implied["oadmin"] == ["Alpha workspace"]
    kinds = {r.name: r.kind for r in roles[people["member"]]}
    assert kinds == {"Alpha reports": "policy", "Alpha workspace": "group", "Members": "group"}


@pytest.mark.asyncio
async def test_the_role_groups_of_an_organization_and_of_the_platform(world):
    """An organization's Role is made of its people and admins groups (and its workspaces'
    groups, to place someone in them); the platform's of its admins group; the levels at
    each. A workspace's Role leaves its organization's to Organization › Users."""
    await _team(world)
    org = await MEMBERSHIPS.role_groups(ORG)
    ws = await MEMBERSHIPS.role_groups(world.W)
    platform = await MEMBERSHIPS.role_groups(PLATFORM)
    assert org.own and org.admins and {org.own, org.admins}.isdisjoint({ws.own, ws.admins})
    assert {org.own, org.admins} <= ws.elsewhere
    assert platform.own is None and platform.admins and platform.members == org.members
    member = world.principal("member")
    at_org, _ = await MEMBERSHIPS.held_at(ORG, member)
    at_platform, _ = await MEMBERSHIPS.held_at(PLATFORM, member)
    assert ws.own in at_org and org.members in at_org
    assert ws.own not in at_platform and org.members in at_platform


@pytest.mark.asyncio
async def test_a_member_joined_when_they_entered_the_workspace_s_groups(world):
    """Users › Joined: the earliest a person entered the workspace's own or admins group."""
    before = datetime.now(UTC) - timedelta(seconds=1)
    await _team(world)
    since = {m.user_id: m.since for m in await MEMBERSHIPS.members(world.W)}
    assert set(since) == {"viewer", "member", "wadmin"}
    assert all(at is not None and at >= before for at in since.values()), since


@pytest.mark.asyncio
async def test_a_role_at_the_organization_and_at_the_platform(world):
    """Organization › Users and Platform › Users › Role: the organization's people first
    and its admins for an org admin (no level); at the platform, Platform admins for a
    platform admin (no level), else their level."""
    await _team(world)
    people = {p: world.principal(p) for p in ("member", "oadmin", "root")}
    with as_service_account("api"):  # as the access move leaves a platform admin
        world.iam.add_group_member(LEVELS.get(world.iam).platform_admins, people["root"])
    at_org = await MEMBERSHIPS.roles_at(ORG, list(people.values()))
    names = {p: [r.name for r in at_org[people[p]]] for p in people}
    assert names["oadmin"] == ["Acme people", "Acme admins"]
    assert names["member"][:1] == ["Acme people"] and "Members" in names["member"]
    assert "Alpha workspace" not in names["member"]  # the Workspaces column says it
    at_platform = await MEMBERSHIPS.roles_at(PLATFORM, list(people.values()))
    names = {p: [r.name for r in at_platform[people[p]]] for p in people}
    assert names["root"][:1] == ["Platform admins"] and "Members" not in names["root"]
    assert names["member"] == ["Members"]


@pytest.mark.asyncio
async def test_a_persons_page_names_their_groups_and_policies(world):
    """Users › a person lists their Role by name: groups and policies, an unknown id
    left out."""
    await _team(world)
    levels = LEVELS.get(world.iam)
    names = await MEMBERSHIPS.names_of([levels.members, "grp_gone"], ["builtin.member", "pol_gone"])
    assert names[levels.members] == "Members"
    assert names["builtin.member"]
    assert "grp_gone" not in names and "pol_gone" not in names


@pytest.mark.asyncio
async def test_a_persons_page_shows_what_their_role_shows(world):
    """Users › a person lists the groups their Role shows (Users › Role), each one a
    change here leaves alone said why: the workspace's own group an organization's admin
    reaches through its admins group, the organization's admins group (managed in
    Organization › Users)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.roles import held_roles

    await _team(world)
    groups = await MEMBERSHIPS.role_groups(world.W)
    oadmin = await held_roles(world.W, world.principal("oadmin"), groups)
    shown = {s.name: s.managed for s in oadmin.shown}
    assert list(shown) == ["Alpha workspace", "Acme admins"]
    assert shown == {"Alpha workspace": "admins", "Acme admins": "organization"}
    assert not {s.id for s in oadmin.shown} & set(oadmin.groups)
    wadmin = await held_roles(world.W, world.principal("wadmin"), groups)
    assert [(s.name, s.managed) for s in wadmin.shown] == [
        ("Alpha workspace", None),
        ("Alpha admins", None),
    ]


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


# -- search sources (fix-permissions-offer) ----------------------------------------------


def _source(world, source: str, container: str | None = None) -> str:
    return f"{container or world.W}/nexus:search_source/{source}"


@pytest.mark.asyncio
async def test_a_workspace_offers_its_search_sources_and_its_levels_use_them_there(world):
    """A search source (a feature searched, a web engine) is used where the workspace's
    offer names it, within the organization's, by the levels that search. A source the
    offer leaves out is refused to everyone in W, its admins included; in another
    workspace the first's offer gives nothing."""
    await _team(world)
    w_access = world.record.access_policy_id
    with as_service_account("api"):
        o_access = world.iam.get_policy(w_access).parent_id
        widen_offer(
            world.iam,
            o_access,
            Offer.of(
                features=["search"], search_sources=["chat", "web.wikipedia", "web.duckduckgo"]
            ),
        )
        widen_offer(
            world.iam,
            w_access,
            Offer.of(features=["search"], search_sources=["chat", "web.wikipedia"]),
        )
    use = "nexus:UseSearchSource"
    assert _can(world, "member", use, _source(world, "web.wikipedia"))
    assert _can(world, "member", use, _source(world, "chat"))
    assert _can(world, "wadmin", use, _source(world, "web.wikipedia"))
    for user in ("member", "wadmin"):
        assert not _can(world, user, use, _source(world, "web.duckduckgo"))
    # A Viewer does not search (no search feature at their level, so no source).
    assert not _can(world, "viewer", use, _source(world, "web.wikipedia"))
    # W's offer gives nothing in ws-2, which offers no source.
    ws2 = workspace_container("org-1", "ws-2")
    assert not _can(world, "member", use, _source(world, "web.wikipedia", ws2))
    # A level grants a type, never a source: the bound names which.
    member = level_document(MEMBER_ACCESS).to_dict()
    sources = [r for s in member["statements"] for r in s["resources"] if "search_source" in r]
    assert sources == ["${scope}/nexus:search_source/*"]
    viewer = level_document(VIEWER_ACCESS).to_dict()
    assert not [r for s in viewer["statements"] for r in s["resources"] if "search_source" in r]


@pytest.mark.asyncio
async def test_the_move_writes_the_sources_each_workspace_kept_on(world):
    """``search_sources_offer``: an organization offers every source; a workspace
    every source but those its Settings › Search switched off. Its other sections are
    kept; a second pass changes nothing (a section naming nothing stays so)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import search_sources_offer
    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import offer_of

    await _team(world)
    w_access = world.record.access_policy_id
    with as_service_account("api"):
        o_access = world.iam.get_policy(w_access).parent_id
        before = offer_of(world.iam.get_policy(w_access).document)
        # Search itself is offered (the sources are what it reads).
        widen_offer(world.iam, o_access, Offer.of(features=["search"]))
        widen_offer(world.iam, w_access, Offer.of(features=["search"]))
    policies = {ORG: o_access, world.W: w_access}
    switched_off = {"ws-1": ["web.duckduckgo", "maps"]}
    report = search_sources_offer.apply(world.iam, policies, switched_off)
    assert sorted(report.written) == sorted(policies) and not report.failed
    world.authz.forget_offers()
    use = "nexus:UseSearchSource"
    assert _can(world, "member", use, _source(world, "web.wikipedia"))
    assert not _can(world, "member", use, _source(world, "web.duckduckgo"))
    assert not _can(world, "member", use, _source(world, "maps"))
    with as_service_account("api"):
        after = offer_of(world.iam.get_policy(w_access).document)
    assert after.agents == before.agents and after.apps == before.apps
    assert "web.duckduckgo" not in after.search_sources and "chat" in after.search_sources
    # Once written, a pass leaves it: an admin's later choice is theirs.
    again = search_sources_offer.apply(world.iam, policies, {})
    assert not again.written and sorted(again.kept) == sorted(policies)


@pytest.mark.asyncio
async def test_a_workspace_offers_its_ontologies_and_its_levels_read_them_there(world):
    """An ontology file is read where the workspace's offer names it, within the
    organization's (which allows every file, as its admins could assign any)."""
    await _team(world)
    w_access = world.record.access_policy_id
    with as_service_account("api"):
        o_access = world.iam.get_policy(w_access).parent_id
        org = world.iam.get_policy(o_access)
        doc = org.document.to_dict()
        doc["statements"].append(
            {
                "sid": "Ontologies",
                "effect": "Allow",
                "actions": ["nexus:UseOntology"],
                "resources": ["${scope}/nexus:ontology_file/*"],
            }
        )
        world.iam.update_policy(o_access, expected_revision=org.revision, document=doc)
        widen_offer(world.iam, w_access, Offer.of(ontologies=["bfo:bfo-core.ttl"]))
    use = "nexus:UseOntology"
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    file = nexus_resource("ontology_file", container=world.W, id="bfo:bfo-core.ttl")
    other = nexus_resource("ontology_file", container=world.W, id="acme:Sales.ttl")
    assert _can(world, "member", use, file) and _can(world, "wadmin", use, file)
    assert not _can(world, "member", use, other)
    # A Viewer reads no ontology (no ontology feature at their level).
    assert not _can(world, "viewer", use, file)


@pytest.mark.asyncio
async def test_the_move_writes_each_workspaces_ontologies_and_lets_its_organization_allow_any(
    world,
):
    from naas_abi.apps.nexus.apps.api.app.services.iam import ontologies_offer
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource

    await _team(world)
    w_access = world.record.access_policy_id
    with as_service_account("api"):
        o_access = world.iam.get_policy(w_access).parent_id
    policies = {ORG: o_access, world.W: w_access}
    report = ontologies_offer.apply(world.iam, policies, {"ws-1": ["bfo:bfo-core.ttl"]})
    assert sorted(report.written) == sorted(policies) and not report.failed
    use = "nexus:UseOntology"

    def reads(ref: str) -> bool:
        return _can(
            world, "member", use, nexus_resource("ontology_file", container=world.W, id=ref)
        )

    assert reads("bfo:bfo-core.ttl") and not reads("acme:Sales.ttl")
    # The organization allows any file: its admins may offer another one in W.
    with as_service_account("api"):
        widen_offer(world.iam, w_access, Offer.of(ontologies=["acme:Sales.ttl"]))
    assert reads("acme:Sales.ttl")
    again = ontologies_offer.apply(world.iam, policies, {})
    assert not again.written


@pytest.mark.asyncio
async def test_a_viewer_given_the_chat_feature_is_not_shown_a_chat_they_cannot_use(world):
    """Chatting is writing a conversation, which the Viewer level never does: a policy
    giving a Viewer the chat feature does not show them the chat (every message would
    be refused). A Member is shown it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.user_features import user_feature_flags

    await _team(world)
    world.allow("viewer", ["nexus:UseFeature"], ["${scope}/nexus:feature/chat"], world.W)
    assert _can(world, "viewer", "nexus:UseFeature", f"{world.W}/nexus:feature/chat")

    async def chat(user: str) -> bool:
        flags = await user_feature_flags(SimpleUser(user), [("org-1", "ws-1")], ["chat"])
        assert flags is not None
        return flags["ws-1"]["chat"]

    assert await chat("member") is True
    assert await chat("viewer") is False


@pytest.mark.asyncio
async def test_a_viewer_reads_my_files_unless_the_deployment_says_not(world):
    """My Files is no workspace's to give: every Member writes theirs, and a Viewer
    reads theirs unless ``feature_flags.viewer_my_files`` is off, which writes a Deny
    into "Viewer access" (rewritten at the next start)."""
    await _team(world)

    async def mine(user: str, action: str, of: str = "my_file") -> bool:
        what = {"my_file": f"{action}MyFile", "user_storage": f"{action}UserStorage"}[of]
        if action == "List":
            what = {"my_file": "ListMyFiles", "user_storage": "ListUserStorage"}[of]
        return await world.authz.allowed(what, user=user, id=(user, "notes.md"))

    assert await mine("viewer", "List") and await mine("viewer", "Get")
    assert await mine("viewer", "Get", "user_storage")
    assert not await mine("viewer", "Put")
    assert await mine("member", "Put") and await mine("wadmin", "Put")

    world.flags.viewer_my_files = False
    LEVELS.forget()
    LEVELS.get(world.iam)
    with as_service_account("api"):
        viewer = [p for p in world.iam.list_policies(limit=500).items if p.name == VIEWER_ACCESS]
    assert len(viewer) == 1
    assert not await mine("viewer", "List") and not await mine("viewer", "Get")
    assert not await mine("viewer", "Get", "user_storage")
    assert await mine("member", "Get") and await mine("member", "Put")
    assert await mine("wadmin", "Put")
    assert not any(
        s["effect"] == "Deny" for s in level_document(MEMBER_ACCESS).to_dict()["statements"]
    )


@pytest.mark.asyncio
async def test_a_workspace_offers_its_models_and_the_chatting_levels_use_them_there(world):
    """``UseModel`` is granted by the levels that chat (``${scope}/nexus:model/*``) and
    bounded by W's offer (``OfferModels``): ``*`` every model, else the ones it names.
    A Viewer does not chat: no model."""
    from dataclasses import replace

    from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
        offer_of,
        with_offer,
    )

    await _team(world)
    W = world.W

    def model(name: str) -> str:
        return f"{W}/nexus:model/{name}"

    rows = {"member": True, "wadmin": True, "viewer": False, "stranger": False}
    # The fixture's offer names no model: none is used in W through the level.
    assert not _can(world, "member", "nexus:UseModel", model("qwen-3.8"))
    with as_service_account("api"):
        # W's offer is bounded by its organization's (its parent): it names every model.
        org_access = world.iam.get_policy(world.record.access_policy_id).parent_id
        widen_offer(world.iam, org_access, Offer.of(models=["*"]))
        policy = world.iam.get_policy(world.record.access_policy_id)
        world.iam.update_policy(
            policy.id,
            expected_revision=policy.revision,
            document=with_offer(
                policy.document,
                replace(offer_of(policy.document), models=frozenset({"*"})),
            ),
        )
    for person, wanted in rows.items():
        assert _can(world, person, "nexus:UseModel", model("gpt-x")) == wanted, person
    with as_service_account("api"):
        policy = world.iam.get_policy(world.record.access_policy_id)
        world.iam.update_policy(
            policy.id,
            expected_revision=policy.revision,
            document=with_offer(
                policy.document,
                replace(
                    offer_of(policy.document),
                    models=frozenset({"qwen-3.8"}),
                    default_model="qwen-3.8",
                ),
            ),
        )
    assert _can(world, "member", "nexus:UseModel", model("qwen-3.8"))
    assert not _can(world, "member", "nexus:UseModel", model("gpt-x"))
