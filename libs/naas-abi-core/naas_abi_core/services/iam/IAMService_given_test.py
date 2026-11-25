"""Given statements: what a container's offer gives outside it, in process (ADR
``20261125_offer_gives_outside_resources``; AGENTS.md, "Bounds").

In the policy a membership group of W holds at W (W's bound), an Allow whose
resources are all absolute (no ``${...}``) is a grant to every member of W,
through any of W's membership groups, while they are members. Each of its
actions counts only within the level the person holds at W. Writing one is
held-checked unscoped, and nobody gives on what was only given to them.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import GrantNotHeldError, PrincipalRecord
from naas_abi_core.services.iam.names import MY_CONTAINERS_SCOPE, PLATFORM
from naas_abi_core.services.iam.policy import PolicyDocument, PolicyValidationError
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    document,
    graph,
    org,
    statement,
    workspace,
)

W = workspace("ws-1")
W2 = workspace("ws-2")

LIST = "triple_store:ListGraphs"
READ = "triple_store:Query"
WRITE = "triple_store:Insert"
ADMIN = "triple_store:DropGraph"
ALL = [LIST, READ, WRITE, ADMIN]

# A platform graph, and a graph of another workspace of the organisation.
SHARED = PLATFORM + "triple_store:graph/shared"
OTHER = graph("other", workspace="ws-2")
OWN = "${scope}/triple_store:graph/*"


def _register_world(h: IAMHarness) -> None:
    h.register("ws-1")
    h.register("ws-2")


def _ensure_belongs(h: IAMHarness, user_id: str) -> None:
    h.grant(
        user_id,
        statement("Allow", ["nexus:GetOrganization"], ["${scope}"]),
        scope=org(),
    )


def _membership_group(h: IAMHarness, container: str, name: str | None = None):
    with as_service_account("engine"):
        return h.iam.create_group(
            name or f"{container} workspace", scope=container, membership_of=container
        )


def _level_group(h: IAMHarness, role: str) -> PrincipalRecord:
    with as_service_account("engine"):
        group = h.iam.create_group(f"{role} level", level=True)
        h.iam.attach_policy(role, group.id, MY_CONTAINERS_SCOPE)
    return group


def _join(h: IAMHarness, group_id: str, member_id: str) -> None:
    h.admin("add_group_member", group_id, member_id)


def _leave(h: IAMHarness, group_id: str, member_id: str) -> None:
    h.admin("remove_group_member", group_id, member_id)


def _access(*given: dict, offer: list[str] | None = None, sid: str = "Offer"):
    """ "<W> access": the offer (Insert on W's graphs) and ``given`` statements."""
    return document(
        statement("Allow", [WRITE], offer or [OWN], sid=sid),
        *given,
    )


def _bound(h: IAMHarness, container: str, doc: dict, *, parent: str | None = None):
    """``container``'s membership group holding ``doc`` at it, written by the
    engine (a first-party account acting for no user)."""
    members = _membership_group(h, container)
    with as_service_account("engine"):
        access = h.iam.create_policy(
            f"{container} access", doc, scope=container, parent=parent
        )
        h.iam.attach_policy(access.id, members.id, container)
    return members, access


def _person(h: IAMHarness, name: str) -> PrincipalRecord:
    person = h.user(name)
    _ensure_belongs(h, person.id)
    return person


def _given_world(h: IAMHarness, *resources: str, actions: list[str] | None = None):
    _register_world(h)
    members, access = _bound(
        h,
        W,
        _access(
            statement("Allow", actions or ALL, list(resources or [SHARED]), "Given")
        ),
    )
    return members, access


def _may(h: IAMHarness, person: PrincipalRecord, resource: str = SHARED) -> set[str]:
    return {a for a in ALL if h.allowed(a, resource, person)}


def _update(h: IAMHarness, policy_id: str, doc: dict, writer=None):
    current = h.iam.store.get_policy(policy_id)
    if writer is None:
        with as_service_account("engine"):
            return h.iam.update_policy(
                policy_id, expected_revision=current.revision, document=doc
            )
    with h.as_(writer):
        return h.iam.update_policy(
            policy_id, expected_revision=current.revision, document=doc
        )


def _platform_admin(h: IAMHarness) -> PrincipalRecord:
    root = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    return root


def _admin_of(h: IAMHarness, container: str, name: str) -> PrincipalRecord:
    admin = h.user(name)
    h.attach(roles.ADMIN, admin.id, container)
    return admin


# -- who receives it, and how much ---------------------------------------------------


def test_a_member_gets_the_given_grant_within_the_member_level(h):
    members, _access_policy = _given_world(h)
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    assert _may(h, bob) == set()
    _join(h, members.id, bob.id)
    assert _may(h, bob) == {LIST, READ, WRITE}


def test_a_viewer_gets_only_the_read_and_list_actions(h):
    members, _access_policy = _given_world(h, actions=["triple_store:*"])
    vera = _person(h, "vera")
    _join(h, _level_group(h, roles.VIEWER).id, vera.id)
    _join(h, members.id, vera.id)
    assert _may(h, vera) == {LIST, READ}


def test_a_workspace_admin_gets_the_admin_actions_too(h):
    members, _access_policy = _given_world(h)
    ada = _person(h, "ada")
    h.attach(roles.ADMIN, ada.id, W)
    assert _may(h, ada) == set()
    _join(h, members.id, ada.id)
    assert _may(h, ada) == set(ALL)


def test_an_org_admin_below_the_organisation_gets_the_admin_level(h):
    members, _access_policy = _given_world(h)
    olga = _person(h, "olga")
    h.attach(roles.ADMIN, olga.id, org() + "/*")
    _join(h, members.id, olga.id)
    assert _may(h, olga) == set(ALL)


def test_a_member_without_a_level_gets_nothing(h):
    members, _access_policy = _given_world(h)
    bob = _person(h, "bob")
    _join(h, members.id, bob.id)
    assert _may(h, bob) == set()


def test_a_member_of_the_admins_group_alone_gets_the_grant(h):
    _given_world(h)
    admins = _membership_group(h, W, "W admins")
    h.attach(roles.ADMIN, admins.id, MY_CONTAINERS_SCOPE)
    ada = _person(h, "ada")
    _join(h, admins.id, ada.id)
    assert _may(h, ada) == set(ALL)


def test_a_non_member_and_a_member_of_another_workspace_get_nothing(h):
    _members, _access_policy = _given_world(h)
    level = _level_group(h, roles.MEMBER)
    outsider = _person(h, "outsider")
    _join(h, level.id, outsider.id)
    assert _may(h, outsider) == set()
    w2_member = _person(h, "w2")
    _join(h, level.id, w2_member.id)
    _join(h, _membership_group(h, W2).id, w2_member.id)
    assert _may(h, w2_member) == set()
    assert h.allowed(WRITE, graph("x", workspace="ws-2"), w2_member)


def test_leaving_the_workspace_ends_the_grant_at_once(h):
    members, _access_policy = _given_world(h)
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert h.allowed(WRITE, SHARED, bob)
    _leave(h, members.id, bob.id)
    assert not h.allowed(WRITE, SHARED, bob)


def test_the_offer_still_bounds_the_level_and_grants_nothing_itself(h):
    members, _access_policy = _given_world(h)
    bob = _person(h, "bob")
    _join(h, members.id, bob.id)
    # In W's membership group only: the offer is a bound, it grants nothing.
    assert not h.allowed(WRITE, graph("a"), bob)


def test_the_given_grant_is_not_bounded_by_the_parent_chain(h):
    _register_world(h)
    with as_service_account("engine"):
        org_access = h.iam.create_policy(
            "O access", document(statement("Allow", [WRITE], [OWN]))
        )
    root = _platform_admin(h)
    members = _membership_group(h, W)
    with h.as_(root):
        access = h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ, WRITE], [SHARED], "Given")),
            scope=W,
            parent=org_access.id,
        )
        h.iam.attach_policy(access.id, members.id, W)
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert _may(h, bob) == {READ, WRITE}


def test_an_uncatalogued_action_grants_nothing(h):
    members, access = _given_world(h)
    stored = h.iam.store.get_policy(access.id)
    ghost = replace(
        stored,
        document=PolicyDocument.from_dict(
            _access(statement("Allow", ["ghost:Haunt", READ], [SHARED], "Given"))
        ),
    )
    h.iam.store.update_policy(ghost, stored.revision)
    h.iam.invalidate()
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert not h.allowed("ghost:Haunt", SHARED, bob)
    assert h.allowed(READ, SHARED, bob)


def test_explain_names_the_bound_policy_and_its_group(h):
    members, access = _given_world(h)
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    explained = h.admin("explain", WRITE, SHARED, principal_id=bob.id)
    assert explained.allowed
    deciding = explained.statement
    assert deciding is not None
    assert deciding.policy_id == access.id
    assert deciding.sid == "Given"
    assert deciding.via_group == members.id
    assert deciding.membership_group == members.id
    assert deciding.scope == W
    assert deciding.given is True
    assert deciding.bounded_by == ()


# -- writing ------------------------------------------------------------------------


def test_a_workspace_admin_cannot_give_a_platform_resource(h):
    _register_world(h)
    _members, access = _bound(h, W, _access())
    w_admin = _admin_of(h, W, "w-admin")
    before = h.iam.store.get_policy(access.id)
    with pytest.raises(GrantNotHeldError) as refused:
        _update(
            h,
            access.id,
            _access(statement("Allow", [READ], [SHARED], "Given")),
            w_admin,
        )
    assert refused.value.scope is None
    assert h.iam.store.get_policy(access.id) == before


def test_the_platform_admin_gives_a_platform_resource(h):
    _register_world(h)
    members, access = _bound(h, W, _access())
    root = _platform_admin(h)
    _update(h, access.id, _access(statement("Allow", [READ], [SHARED], "Given")), root)
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert h.allowed(READ, SHARED, bob)


def test_an_org_admin_gives_what_they_hold_in_their_organisation(h):
    _register_world(h)
    members, access = _bound(h, W, _access())
    org_admin = h.user("org-admin")
    h.attach(roles.ADMIN, org_admin.id, org())
    h.attach(roles.ADMIN, org_admin.id, org() + "/*")
    _update(
        h,
        access.id,
        _access(statement("Allow", [READ, WRITE], [OTHER], "Given")),
        org_admin,
    )
    with pytest.raises(GrantNotHeldError):
        _update(
            h,
            access.id,
            _access(statement("Allow", [READ], [OTHER, SHARED], "Given")),
            org_admin,
        )
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert h.allowed(WRITE, OTHER, bob)


def test_a_workspace_admin_narrows_and_edits_around_a_given_statement(h):
    members, access = _given_world(h, SHARED, OTHER)
    w_admin = _admin_of(h, W, "w-admin")
    # Another section changes, the given statement stays as it is.
    _update(
        h,
        access.id,
        _access(
            statement("Allow", ALL, [SHARED, OTHER], "Given"),
            offer=["${scope}/triple_store:graph/a"],
        ),
        w_admin,
    )
    # Narrowed: one resource and one action fewer.
    _update(
        h,
        access.id,
        _access(statement("Allow", [LIST, READ, WRITE], [SHARED], "Given")),
        w_admin,
    )
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    _join(h, members.id, bob.id)
    assert h.allowed(WRITE, SHARED, bob)
    assert not h.allowed(READ, OTHER, bob)
    # Taken away.
    _update(h, access.id, _access(), w_admin)
    assert not h.allowed(READ, SHARED, bob)


def test_what_was_given_is_not_given_again(h):
    members, _access_policy = _given_world(h)
    _w2_members, w2_access = _bound(h, W2, _access())
    w_admin = _admin_of(h, W, "w-admin")
    h.attach(roles.ADMIN, w_admin.id, W2)
    _ensure_belongs(h, w_admin.id)
    _join(h, members.id, w_admin.id)
    assert h.allowed(WRITE, SHARED, w_admin)
    with pytest.raises(GrantNotHeldError):
        _update(
            h,
            w2_access.id,
            _access(statement("Allow", [WRITE], [SHARED], "Given")),
            w_admin,
        )


def test_creating_an_offer_with_a_given_statement_is_held_checked(h):
    _register_world(h)
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin), pytest.raises(GrantNotHeldError):
        h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ], [SHARED], "Given")),
            scope=W,
        )
    root = _platform_admin(h)
    with h.as_(root):
        h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ], [SHARED], "Given")),
            scope=W,
        )


def test_attaching_as_a_bound_is_held_checked(h):
    _register_world(h)
    members = _membership_group(h, W)
    with as_service_account("engine"):
        access = h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ], [SHARED], "Given")),
            scope=W,
        )
    w_admin = _admin_of(h, W, "w-admin")
    with h.as_(w_admin), pytest.raises(GrantNotHeldError):
        h.iam.attach_policy(access.id, members.id, W)
    root = _platform_admin(h)
    with h.as_(root):
        h.iam.attach_policy(access.id, members.id, W)


def test_attaching_a_policy_with_a_given_statement_elsewhere_is_refused(h):
    _register_world(h)
    with as_service_account("engine"):
        access = h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ], [SHARED], "Given")),
            scope=W,
        )
        team = h.iam.create_group("team", scope=W)
    root = _platform_admin(h)
    bob = _person(h, "bob")
    with h.as_(root):
        for principal in (team.id, bob.id):
            with pytest.raises(ValueError):
                h.iam.attach_policy(access.id, principal, W)


def test_a_given_statement_is_refused_in_an_offer_attached_elsewhere(h):
    _register_world(h)
    with as_service_account("engine"):
        access = h.iam.create_policy("W access", _access(), scope=W)
        team = h.iam.create_group("team", scope=W)
        h.iam.attach_policy(access.id, team.id, W)
    with pytest.raises(ValueError):
        _update(h, access.id, _access(statement("Allow", [READ], [SHARED], "Given")))


def test_an_allow_mixing_scope_and_absolute_names_is_refused(h):
    _register_world(h)
    with as_service_account("engine"), pytest.raises(PolicyValidationError):
        h.iam.create_policy(
            "W access",
            document(statement("Allow", [READ], [OWN, SHARED])),
            scope=W,
        )


def test_a_deny_outside_the_scope_is_still_refused(h):
    _register_world(h)
    with as_service_account("engine"), pytest.raises(PolicyValidationError):
        h.iam.create_policy(
            "W access",
            _access(statement("Deny", [READ], [SHARED])),
            scope=W,
        )


def test_an_offer_with_given_statements_is_still_listed_as_attachable(h):
    _register_world(h)
    members = _membership_group(h, W)
    with as_service_account("engine"):
        access = h.iam.create_policy(
            "W access",
            _access(statement("Allow", [READ], [SHARED], "Given")),
            scope=W,
        )
    root = _platform_admin(h)
    bob = _person(h, "bob")
    with h.as_(root):
        to_members = h.iam.attachable_policies(W, principal_id=members.id)
        to_bob = h.iam.attachable_policies(W, principal_id=bob.id)
    assert access.id in {p.id for p in to_members.items}
    assert access.id not in {p.id for p in to_bob.items}


def test_joining_the_workspace_is_not_checked_against_given_statements(h):
    members, _access_policy = _given_world(h)
    w_admin = _admin_of(h, W, "w-admin")
    bob = _person(h, "bob")
    _join(h, _level_group(h, roles.MEMBER).id, bob.id)
    with h.as_(w_admin):
        h.iam.add_group_member(members.id, bob.id)
    assert h.allowed(WRITE, SHARED, bob)
