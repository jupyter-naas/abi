"""Membership groups and the ``${my workspaces}`` attachment scope, in process
(AGENTS.md, "Groups" and "Attachments and scope").

A group marked as a membership group of a container makes its members members of
that container. A policy attached at ``${my workspaces}`` (``MY_CONTAINERS_SCOPE``)
applies at each container its holder is a member of, ``${scope}`` filled there, and
nowhere else: a level group ("Members", holding the member role there) plus a
membership group of W is the member role attached at W.
"""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionCatalog
from naas_abi_core.services.iam.iam_catalog import CATALOG as IAM_CATALOG
from naas_abi_core.services.iam.IAMPorts import (
    GrantNotHeldError,
    IAMNotFoundError,
    Membership,
    PermissionDeniedError,
    PrincipalRecord,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.names import (
    MY_CONTAINERS_SCOPE,
    PLATFORM,
    IdKind,
    resource_name,
    validate_scope,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    ACTIVITY_LOG,
    NEXUS,
    TRIPLE_STORE,
    IAMHarness,
    graph,
    org,
    statement,
    workspace,
)

W = workspace("ws-1")
W2 = workspace("ws-2")
OTHER_ORG_WS = workspace("ws-9", "org-2")
LEVELS = (roles.VIEWER, roles.MEMBER, roles.ADMIN)


def _register_world(h: IAMHarness) -> None:
    h.register("ws-1")
    h.register("ws-2")
    h.register("ws-9", "org-2")


def _membership_group(h: IAMHarness, container: str, name: str | None = None):
    """ "<W> workspace": a membership group of ``container``, owned by it."""
    with as_service_account("engine"):
        return h.iam.create_group(
            name or f"{container} workspace", scope=container, membership_of=container
        )


def _level_group(h: IAMHarness, role: str, *, level: bool = True, scope=None):
    """A level group holding ``role`` at ``${my workspaces}``."""
    with as_service_account("engine"):
        group = h.iam.create_group(f"{role} level", scope=scope, level=level)
        h.iam.attach_policy(role, group.id, MY_CONTAINERS_SCOPE)
    return group


def _join(h: IAMHarness, group_id: str, member_id: str) -> None:
    h.admin("add_group_member", group_id, member_id)


def _leave(h: IAMHarness, group_id: str, member_id: str) -> None:
    h.admin("remove_group_member", group_id, member_id)


def _ensure_belongs(h: IAMHarness, user_id: str) -> None:
    """A person of the organisation: a group owned in it takes only its users."""
    h.grant(
        user_id,
        statement("Allow", ["nexus:GetOrganization"], ["${scope}"]),
        scope=org(),
    )


# -- the scope ------------------------------------------------------------------------


def test_the_scope_is_a_literal_validated_as_a_scope():
    assert MY_CONTAINERS_SCOPE == "${my workspaces}"
    assert validate_scope(MY_CONTAINERS_SCOPE) == MY_CONTAINERS_SCOPE


# -- equivalence: level group + membership group == the role attached at W ------------


def _catalog_actions() -> list[tuple[str, str]]:
    found = []
    for catalog in (IAM_CATALOG, TRIPLE_STORE, ACTIVITY_LOG, NEXUS):
        for spec in catalog.actions:
            found.append((catalog.service, spec.name))
    return found


_ACTIONS = _catalog_actions()
_CATALOGS: dict[str, ActionCatalog] = {
    c.service: c for c in (IAM_CATALOG, TRIPLE_STORE, ACTIVITY_LOG, NEXUS)
}


def _resources(catalog: ActionCatalog, action: str, principal_id: str) -> list[str]:
    """Names the action may be decided on: in W, in another workspace of the
    organisation, in another organisation's workspace, and at the platform; the
    containers themselves for a container type. A personal type is named with
    the principal's own id."""
    spec = catalog.action(action)
    assert spec is not None
    found: list[str] = []
    for type_name in spec.resource_types:
        declared = catalog.resource_type(type_name)
        assert declared is not None
        if declared.container:
            ids = {"organization": "org-1", "workspace": "ws-1"}
            found += [W, W2, org()] if type_name in ids else []
            found += [
                resource_name(catalog.service, type_name, "new-one", container=c)
                for c in (W, org(), PLATFORM)
            ]
            continue
        kind: IdKind
        if declared.id == "singleton":
            parts: str | list[str] = "-"
            kind = "singleton"
        elif declared.personal:
            parts = [principal_id, "x"] if declared.id == "path" else principal_id
            kind = declared.id
        elif declared.id == "path":
            parts = ["a", "b"]
            kind = "path"
        else:
            parts = "item-1"
            kind = "opaque"
        for container in (W, W2, OTHER_ORG_WS, PLATFORM):
            found.append(
                resource_name(
                    catalog.service, type_name, parts, kind=kind, container=container
                )
            )
    return found


@pytest.fixture(scope="module")
def worlds() -> dict[str, tuple[IAMHarness, PrincipalRecord, PrincipalRecord]]:
    """Per level: the same world, with Alice holding the role attached at W and
    Bob in the level group and W's membership group."""
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
        IAMStoreMemory,
    )

    built: dict[str, tuple[IAMHarness, PrincipalRecord, PrincipalRecord]] = {}
    for role in LEVELS:
        service = IAMService(IAMStoreMemory())
        service.bootstrap()
        for catalog in (TRIPLE_STORE, ACTIVITY_LOG, NEXUS):
            service._register_catalog(catalog)
        h = IAMHarness(service)
        _register_world(h)
        alice = h.user("alice")
        bob = h.user("bob")
        h.attach(role, alice.id, W)
        _ensure_belongs(h, bob.id)
        # Alice holds the same org-level grant, so both differ only in how the role reaches W.
        _ensure_belongs(h, alice.id)
        level = _level_group(h, role)
        members_of_w = _membership_group(h, W)
        _join(h, level.id, bob.id)
        _join(h, members_of_w.id, bob.id)
        built[role] = (h, alice, bob)
    return built


@pytest.mark.parametrize("role", LEVELS)
@pytest.mark.parametrize(
    "service,action", _ACTIONS, ids=[f"{s}:{a}" for s, a in _ACTIONS]
)
def test_a_level_group_and_a_membership_group_equal_the_role_at_w(
    worlds, role, service, action
):
    h, alice, bob = worlds[role]
    catalog = _CATALOGS[service]
    qualified = catalog.qualified(action)
    for direct, through_groups in zip(
        _resources(catalog, action, alice.id), _resources(catalog, action, bob.id)
    ):
        assert h.allowed(qualified, direct, alice) == h.allowed(
            qualified, through_groups, bob
        ), (qualified, direct, through_groups)


def test_the_role_reaches_w_and_nothing_else(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    assert h.allowed("triple_store:Insert", graph("g"), bob)
    assert not h.allowed("triple_store:Insert", graph("g", workspace="ws-2"), bob)
    assert not h.allowed("triple_store:Insert", graph("g", "org-1", "-"), bob)


# -- freshness -----------------------------------------------------------------------


def test_join_and_leave_take_effect_at_the_next_decision(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    level = _level_group(h, roles.MEMBER)
    members_of_w = _membership_group(h, W)
    insert = ("triple_store:Insert", graph("g"))
    _join(h, level.id, bob.id)
    assert not h.allowed(*insert, bob)
    _join(h, members_of_w.id, bob.id)
    assert h.allowed(*insert, bob)
    _leave(h, members_of_w.id, bob.id)
    assert not h.allowed(*insert, bob)
    _join(h, members_of_w.id, bob.id)
    _leave(h, level.id, bob.id)
    assert not h.allowed(*insert, bob)


def test_a_changed_marker_takes_effect_at_the_next_decision(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    team = h.admin("create_group", "team", scope=org())
    _join(h, team.id, bob.id)
    assert not h.allowed("triple_store:Insert", graph("g"), bob)
    h.admin("mark_group", team.id, membership_of=W)
    assert h.allowed("triple_store:Insert", graph("g"), bob)
    h.admin("mark_group", team.id, membership_of=W2)
    assert not h.allowed("triple_store:Insert", graph("g"), bob)
    assert h.allowed("triple_store:Insert", graph("g", workspace="ws-2"), bob)
    h.admin("mark_group", team.id, membership_of=None)
    assert not h.allowed("triple_store:Insert", graph("g", workspace="ws-2"), bob)


def test_every_change_is_heard_by_the_change_listeners(h):
    """The connection warden listens to these (ADR kick_connections_on_iam_change)."""
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    heard: list[int] = []
    h.iam.add_change_listener(heard.append)
    level = _level_group(h, roles.MEMBER)
    members_of_w = _membership_group(h, W)
    before = len(heard)
    _join(h, members_of_w.id, bob.id)
    _join(h, level.id, bob.id)
    h.admin("mark_group", members_of_w.id, membership_of=None)
    _leave(h, level.id, bob.id)
    assert len(heard) == before + 4


def test_a_service_accounts_broker_grants_follow_its_memberships(h):
    _register_world(h)
    account = h.service_account("ci/nightly")
    with as_service_account("engine"):
        members_of_w = h.iam.create_group("w (platform)", membership_of=W)
        level = h.iam.create_group("members", level=True)
        h.iam.attach_policy(roles.MEMBER, level.id, MY_CONTAINERS_SCOPE)
    _join(h, level.id, account.id)
    without = h.iam.broker_grants(account.id)
    _join(h, members_of_w.id, account.id)
    assert h.iam.broker_grants(account.id) != without


# -- what still refuses ----------------------------------------------------------------


def test_a_deny_in_the_ceiling_still_wins(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    members_of_w = _membership_group(h, W)
    with as_service_account("engine"):
        ceiling = h.iam.create_policy(
            "W access",
            {
                "version": "2026-10-13",
                "statements": [
                    statement(
                        "Deny",
                        ["triple_store:Insert"],
                        ["${scope}/triple_store:graph/secret"],
                    )
                ],
            },
            scope=W,
        )
        h.iam.attach_policy(ceiling.id, members_of_w.id, W)
    _join(h, members_of_w.id, bob.id)
    assert h.allowed("triple_store:Insert", graph("open"), bob)
    assert not h.allowed("triple_store:Insert", graph("secret"), bob)
    explained = h.admin(
        "explain", "triple_store:Insert", graph("secret"), principal_id=bob.id
    )
    assert explained.reason == "explicit_deny"
    assert explained.statement is not None
    assert explained.statement.policy_id == ceiling.id


def test_a_level_group_with_no_membership_grants_nothing(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.ADMIN).id, bob.id)
    subject = h.iam.subject(h.context(bob), "actor")
    assert subject is not None
    reached = {s.policy_id for s in subject.statements}
    # builtin.self and the organisation-level grant of the test, nothing else: not
    # the role, not its platform companion.
    assert roles.ADMIN not in reached
    assert roles.PLATFORM_MEMBER not in reached
    assert not h.allowed("triple_store:Query", graph("g"), bob)


def test_a_group_owned_by_an_organisation_reaches_only_within_it(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    h.grant(
        bob.id,
        statement("Allow", ["nexus:GetOrganization"], ["${scope}"]),
        scope=org("org-2"),
    )
    level = _level_group(h, roles.MEMBER, level=False, scope=org())
    _join(h, level.id, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    _join(h, _membership_group(h, OTHER_ORG_WS).id, bob.id)
    assert h.allowed("triple_store:Insert", graph("g"), bob)
    assert not h.allowed("triple_store:Insert", graph("g", "org-2", "ws-9"), bob)


# -- explain ---------------------------------------------------------------------------


def test_explain_names_the_level_group_and_the_membership_group(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    level = _level_group(h, roles.MEMBER)
    members_of_w = _membership_group(h, W)
    _join(h, level.id, bob.id)
    _join(h, members_of_w.id, bob.id)
    explained = h.admin(
        "explain", "triple_store:Insert", graph("g"), principal_id=bob.id
    )
    assert explained.allowed
    deciding = explained.statement
    assert deciding is not None
    assert deciding.policy_id == roles.MEMBER
    assert deciding.via_group == level.id
    assert deciding.membership_group == members_of_w.id
    assert deciding.scope == W


# -- grant only what you hold ------------------------------------------------------------


def _admin_of(h: IAMHarness, container: str, subject: str):
    admin = h.user(subject)
    h.attach(roles.ADMIN, admin.id, container)
    return admin


def test_a_workspace_admin_of_one_of_the_persons_workspaces_changes_their_level(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    # The level grants more than the writer holds: owner, at every workspace of Bob.
    level = _level_group(h, roles.OWNER)
    audited = []
    h.iam.add_audit_listener(audited.append)
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin):
        h.iam.add_group_member(level.id, bob.id)
    assert bob.id in h.iam.store.list_group_members(level.id)
    with h.as_(w_admin):
        assert h.iam.remove_group_member(level.id, bob.id) is True
    assert [(e.action, e.group_id, e.member_id, e.by) for e in audited] == [
        ("iam:AddGroupMember", level.id, bob.id, w_admin.id),
        ("iam:RemoveGroupMember", level.id, bob.id, w_admin.id),
    ]
    assert audited[0].containers == (W,)


def test_an_org_admin_and_the_platform_admin_change_a_persons_level(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    level = _level_group(h, roles.OWNER)
    org_admin = h.user("org-admin")
    h.attach(roles.ADMIN, org_admin.id, org() + "/*")
    platform_admin = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, platform_admin.id)
    for writer in (org_admin, platform_admin):
        with h.as_(writer):
            h.iam.add_group_member(level.id, bob.id)
            assert h.iam.remove_group_member(level.id, bob.id) is True


def test_a_plain_member_and_an_admin_elsewhere_do_not(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    level = _level_group(h, roles.MEMBER)
    member = h.user("member")
    h.attach(roles.MEMBER, member.id, W)
    other_admin = _admin_of(h, W2, "w2-admin")
    audited = []
    h.iam.add_audit_listener(audited.append)
    for writer in (member, other_admin):
        with h.as_(writer), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.add_group_member(level.id, bob.id)
    assert audited == []
    assert bob.id not in h.iam.store.list_group_members(level.id)


def test_the_exception_is_only_for_groups_marked_as_level_groups(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    unmarked = _level_group(h, roles.MEMBER, level=False)
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.add_group_member(unmarked.id, bob.id)


def test_joining_a_membership_group_is_checked_against_what_the_level_gives_there(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.OWNER, level=False).id, bob.id)
    members_of_w = _membership_group(h, W)
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin), pytest.raises(GrantNotHeldError) as refused:
        h.iam.add_group_member(members_of_w.id, bob.id)
    assert refused.value.scope == W
    # A member's level is held by the workspace's admin: Bob as a member joins.
    carol = h.user("carol")
    _ensure_belongs(h, carol.id)
    _join(h, _level_group(h, roles.MEMBER).id, carol.id)
    with h.as_(w_admin):
        h.iam.add_group_member(members_of_w.id, carol.id)


def test_attaching_at_the_scope_is_checked_at_each_container_the_target_reaches(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _membership_group(h, W).id, bob.id)
    _join(h, _membership_group(h, W2).id, bob.id)
    writer = h.user("writer")
    h.grant(
        writer.id,
        statement("Allow", ["iam:AttachPolicy"], ["abi:iam:attachment/*"]),
    )
    h.attach(roles.OWNER, writer.id, W)
    with h.as_(writer), pytest.raises(GrantNotHeldError) as refused:
        h.iam.attach_policy(roles.MEMBER, bob.id, MY_CONTAINERS_SCOPE)
    assert refused.value.scope == W2
    h.attach(roles.OWNER, writer.id, W2)
    with h.as_(writer):
        h.iam.attach_policy(roles.MEMBER, bob.id, MY_CONTAINERS_SCOPE)
    assert h.allowed("triple_store:Insert", graph("g", workspace="ws-2"), bob)


def test_only_a_platform_grant_attaches_at_the_scope(h):
    _register_world(h)
    bob = h.user("bob")
    org_admin = h.user("org-admin")
    h.attach(roles.OWNER, org_admin.id, org() + "/*")
    with h.as_(org_admin), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.attach_policy(roles.MEMBER, bob.id, MY_CONTAINERS_SCOPE)


def test_the_scope_is_for_attachments_only(h):
    _register_world(h)
    group = h.group("level")
    with as_service_account("engine"):
        with pytest.raises(ValueError):
            h.iam.create_pending_grant(
                "builtin", "bob@example.com", roles.MEMBER, MY_CONTAINERS_SCOPE
            )
        with pytest.raises(ValueError):
            h.iam.bind_idp_group("acme", "Sales", roles.MEMBER, MY_CONTAINERS_SCOPE)
        h.iam.attach_policy(roles.MEMBER, group.id, MY_CONTAINERS_SCOPE)


# -- markers ---------------------------------------------------------------------------


def test_a_membership_group_is_of_a_registered_container_within_its_owner(h):
    _register_world(h)
    with as_service_account("engine"):
        with pytest.raises(ValueError):
            h.iam.create_group("x", scope=W, membership_of=W2)
        with pytest.raises(ValueError):
            h.iam.create_group("x", membership_of=workspace("ws-unknown"))
        made = h.iam.create_group("org people", scope=org(), membership_of=org())
    assert made.membership_of == org()
    assert made.level_group is False


def test_marking_a_level_group_is_the_platforms(h):
    _register_world(h)
    org_admin = h.user("org-admin")
    h.attach(roles.OWNER, org_admin.id, org() + "/*")
    with h.as_(org_admin):
        group = h.iam.create_group("o members", scope=org())
        with pytest.raises(PermissionDeniedError):
            h.iam.mark_group(group.id, level=True)
        with pytest.raises(PermissionDeniedError):
            h.iam.create_group("o viewers", scope=org(), level=True)
        # Its own membership marker is the org's admins'.
        marked = h.iam.mark_group(group.id, membership_of=W)
    assert marked.membership_of == W
    assert h.admin("mark_group", group.id, membership_of=W, level=True).level_group


def test_marking_a_group_with_members_is_checked_at_its_new_container(h):
    _register_world(h)
    bob = h.user("bob")
    _ensure_belongs(h, bob.id)
    _join(h, _level_group(h, roles.OWNER, level=False).id, bob.id)
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin):
        team = h.iam.create_group("team", scope=W)
    _join(h, team.id, bob.id)
    with h.as_(w_admin), pytest.raises(GrantNotHeldError):
        h.iam.mark_group(team.id, membership_of=W)


def test_deleting_a_container_drops_the_markers_naming_it(h):
    _register_world(h)
    with as_service_account("engine"):
        platform_group = h.iam.create_group("w2 people", membership_of=W2)
    with as_service_account("api"):
        h.iam.delete_container("nexus", "workspace", "ws-2")
    assert h.iam.store.get_principal(platform_group.id).membership_of is None


# -- listing ---------------------------------------------------------------------------


def test_a_principals_memberships_and_a_containers_members(h):
    _register_world(h)
    bob = h.user("bob")
    carol = h.user("carol")
    for person in (bob, carol):
        _ensure_belongs(h, person.id)
    members_of_w = _membership_group(h, W)
    members_of_w2 = _membership_group(h, W2)
    _join(h, members_of_w.id, bob.id)
    _join(h, members_of_w2.id, bob.id)
    _join(h, members_of_w.id, carol.id)
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    with as_service_account("engine"):
        assert sorted(h.iam.list_memberships(bob.id), key=lambda m: m.container) == [
            Membership(members_of_w.id, W),
            Membership(members_of_w2.id, W2),
        ]
        assert h.iam.list_container_members(W) == sorted([bob.id, carol.id])
        assert h.iam.list_container_members(W2) == [bob.id]
    # What the caller may read only: an admin of W2 sees W2's membership.
    w2_admin = _admin_of(h, W2, "w2-admin")
    with h.as_(w2_admin):
        assert h.iam.list_memberships(bob.id) == [Membership(members_of_w2.id, W2)]
        assert h.iam.list_container_members(W) == []


def test_a_member_of_a_container_belongs_to_its_organisation(h):
    """A person whose only tie to the organisation is a membership group joins
    the organisation's other groups."""
    _register_world(h)
    dave = h.user("dave")
    with as_service_account("engine"):
        members_of_w = h.iam.create_group("w (platform)", membership_of=W)
        h.iam.add_group_member(members_of_w.id, dave.id)
        team = h.iam.create_group("team", scope=org())
        h.iam.add_group_member(team.id, dave.id)
    assert dave.id in h.iam.store.list_group_members(team.id)


# -- the policy builder ----------------------------------------------------------------


def test_grantable_offers_the_scope(h):
    _register_world(h)
    platform_admin = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, platform_admin.id)
    org_admin = h.user("org-admin")
    h.attach(roles.ADMIN, org_admin.id, org() + "/*")

    def offered(record) -> dict[str, tuple[str, ...]]:
        with h.as_(record):
            found = h.iam.grantable(MY_CONTAINERS_SCOPE)
        return {a.action: a.resources for c in found for a in c.actions}

    everything = offered(platform_admin)
    assert everything["triple_store:Query"] == ("${scope}/triple_store:graph/*",)
    assert "${scope}" in everything["nexus:UpdateWorkspace"]
    # An admin of one organisation holds nothing at every container.
    assert "triple_store:Query" not in offered(org_admin)
