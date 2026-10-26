"""Pending grants and IdP group bindings: who may make them, and
what they reach."""

from __future__ import annotations

import pytest

from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
)
from naas_abi_core.services.iam.tests.iam_harness import graph

W1 = "abi:acme:ws1"
W2 = "abi:acme:ws2"
BOB = "bob@example.com"


@pytest.fixture
def ada(h):
    """A workspace admin of ws1."""
    record = h.user("ada", email="ada@example.com", provider="builtin")
    h.attach(roles.ADMIN, record.id, W1)
    return record


def sign_in(h, subject="bob", *, email=BOB, verified=True, provider="builtin"):
    return h.user(subject, provider=provider, email=email, email_verified=verified)


def held(h, record) -> set[tuple[str, str | None]]:
    return {
        (a.policy_id, a.scope)
        for a in h.iam.store.list_attachments(principal_id=record.id)
    }


# -- who may invite ---------------------------------------------------------------


def test_the_platform_admin_invites_to_any_scope(h):
    grant = h.admin(
        "create_pending_grant", "builtin", "Bob@Example.com", roles.MEMBER, W1
    )
    assert (grant.provider, grant.email, grant.scope) == ("builtin", BOB, W1)
    assert grant.policy_id == roles.MEMBER and grant.created_by == "engine"
    # The same invitation again is the same grant.
    assert h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1) == grant
    other = h.admin("create_pending_grant", "builtin", BOB, roles.VIEWER, W2)
    assert h.admin("list_pending_grants") == sorted([grant, other], key=lambda g: g.id)
    assert (
        h.admin("list_pending_grants", email="BOB@example.com", provider="acme") == []
    )


def test_a_workspace_admin_invites_to_their_workspace_only(h, ada):
    with h.as_(ada):
        grant = h.iam.create_pending_grant("builtin", BOB, roles.MEMBER, W1)
        assert grant.created_by == ada.id
        assert h.iam.create_pending_grant("builtin", BOB, roles.ADMIN, W1)
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.create_pending_grant("builtin", BOB, roles.MEMBER, W2)
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.create_pending_grant("builtin", BOB, roles.MEMBER, "abi:acme:*")
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.create_pending_grant("builtin", BOB, roles.MEMBER)
        # Never an owner: an admin cannot make one, invited or not.
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.create_pending_grant("builtin", BOB, roles.OWNER, W1)
        # Nor a policy that reaches past the workspace.
        with pytest.raises((PermissionDeniedError, IAMNotFoundError, ValueError)):
            h.iam.create_pending_grant("builtin", BOB, roles.PLATFORM_ADMIN)


def test_a_member_and_a_stranger_invite_nobody(h, ada):
    carol = h.user("carol")
    h.attach(roles.MEMBER, carol.id, W1)
    dave = h.user("dave")
    for who in (carol, dave):
        with h.as_(who), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.create_pending_grant("builtin", BOB, roles.VIEWER, W1)


def test_what_an_invitation_names_is_checked(h):
    for provider, email in (
        ("Not A Provider", BOB),
        ("builtin", "nope"),
        ("builtin", ""),
    ):
        with pytest.raises(ValueError):
            h.admin("create_pending_grant", provider, email, roles.MEMBER, W1)
    with pytest.raises(ValueError):  # a policy using ${scope} needs a scope
        h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER)
    with pytest.raises(IAMNotFoundError):
        h.admin("create_pending_grant", "builtin", BOB, "pol_missing", W1)


def test_listing_and_revoking_follow_the_attach_rights(h, ada):
    mine = h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    elsewhere = h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W2)
    with h.as_(ada):
        assert h.iam.list_pending_grants() == [mine]
    # Another workspace's grant is neither listed nor revocable by ada.
    assert elsewhere in h.admin("list_pending_grants")
    with h.as_(ada), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.revoke_pending_grant(elsewhere.id)
    with h.as_(ada):
        assert h.iam.revoke_pending_grant(mine.id) is True
        assert h.iam.revoke_pending_grant(mine.id) is False
    assert h.admin("list_pending_grants") == [elsewhere]


# -- claiming ------------------------------------------------------------------------


def test_the_first_sign_in_with_the_verified_email_claims_the_grants(h):
    h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    h.admin("create_pending_grant", "builtin", BOB, roles.VIEWER, W2)
    bob = sign_in(h)
    claimed = h.admin("claim_pending_grants", bob.id)
    assert {(a.policy_id, a.scope) for a in claimed} == {
        (roles.MEMBER, W1),
        (roles.VIEWER, W2),
    }
    assert {(roles.MEMBER, W1), (roles.VIEWER, W2)} <= held(h, bob)
    # The platform companion follows the roles, as for an attached one.
    assert (roles.PLATFORM_MEMBER, None) in held(h, bob)
    assert h.admin("list_pending_grants") == []
    # Once: the second sign-in claims nothing.
    assert h.admin("claim_pending_grants", bob.id) == []
    assert h.allowed("triple_store:Insert", graph("g", "acme", "ws1"), bob)
    assert not h.allowed("triple_store:Insert", graph("g", "acme", "ws2"), bob)


def test_an_unverified_email_claims_nothing(h):
    grant = h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    mallory = sign_in(h, "mallory", verified=False)
    assert h.admin("claim_pending_grants", mallory.id) == []
    assert h.admin("list_pending_grants") == [grant]
    assert held(h, mallory) == set()


def test_another_provider_claims_nothing(h):
    grant = h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    other = sign_in(h, "bob", provider="acme")
    assert h.admin("claim_pending_grants", other.id) == []
    assert h.admin("list_pending_grants") == [grant]
    # The same address on the invited provider is the invited person.
    assert h.admin("claim_pending_grants", sign_in(h, "bob2").id)


def test_a_user_without_provider_or_email_claims_nothing(h):
    h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    legacy = h.user("legacy")
    no_provider = h.user("nop", email=BOB, email_verified=True)
    assert h.admin("claim_pending_grants", legacy.id) == []
    assert h.admin("claim_pending_grants", no_provider.id) == []


def test_a_suspended_user_claims_nothing_and_the_email_is_matched_in_lower_case(h):
    h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    bob = sign_in(h, email="BOB@Example.com")
    h.admin("suspend_principal", bob.id)
    assert h.admin("claim_pending_grants", bob.id) == []
    h.admin("resume_principal", bob.id)
    assert len(h.admin("claim_pending_grants", bob.id)) == 1


def test_claiming_is_an_action_of_its_own(h, ada):
    bob = sign_in(h)
    h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    # A workspace admin invites; it cannot make anyone claim.
    with h.as_(ada), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.claim_pending_grants(bob.id)
    with h.as_(bob), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.claim_pending_grants(bob.id)
    assert len(h.admin("list_pending_grants")) == 1


def test_a_policy_an_invitee_holds_cannot_be_deleted(h):
    policy = h.admin(
        "create_policy",
        "reads",
        {
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["triple_store:Query"],
                    "resources": ["${scope}:triple_store:graph/*"],
                }
            ],
        },
    )
    grant = h.admin("create_pending_grant", "builtin", BOB, policy.id, W1)
    from naas_abi_core.services.iam.IAMPorts import IAMConflictError

    with pytest.raises(IAMConflictError):
        h.admin("delete_policy", policy.id)
    h.admin("revoke_pending_grant", grant.id)
    h.admin("delete_policy", policy.id)


# -- IdP group bindings ------------------------------------------------------------------


def test_a_bound_idp_group_holds_the_role_where_it_is_bound(h, ada):
    with h.as_(ada):
        binding = h.iam.bind_idp_group("acme", "Data readers", roles.VIEWER, W1)
        assert h.iam.bind_idp_group("acme", "Data readers", roles.VIEWER, W1) == binding
    assert (binding.provider, binding.claim_value, binding.scope) == (
        "acme",
        "Data readers",
        W1,
    )
    # The claim maps to the group that carries the attachment.
    assert h.iam.resolve_idp_groups("acme", ["Data readers"]) == [binding.group_id]
    assert h.iam.resolve_idp_groups("other", ["Data readers"]) == []
    group = h.iam.store.get_principal(binding.group_id)
    assert group.kind == "group" and group.org == "acme"
    # A member of the IdP group (its sign-in carries the mapped group) reads
    # there and nowhere else.
    reader = h.user("reader")
    groups = frozenset({binding.group_id})
    assert h.allowed(
        "triple_store:Query", graph("g", "acme", "ws1"), reader, groups=groups
    )
    assert not h.allowed(
        "triple_store:Insert", graph("g", "acme", "ws1"), reader, groups=groups
    )
    assert not h.allowed(
        "triple_store:Query", graph("g", "acme", "ws2"), reader, groups=groups
    )


def test_binding_the_same_group_twice_reuses_its_group(h, ada):
    first = h.admin("bind_idp_group", "acme", "eng", roles.VIEWER, W1)
    second = h.admin("bind_idp_group", "acme", "eng", roles.MEMBER, W2)
    assert first.group_id == second.group_id
    assert {(b.policy_id, b.scope) for b in h.admin("list_idp_bindings")} == {
        (roles.VIEWER, W1),
        (roles.MEMBER, W2),
    }
    assert h.admin("list_idp_bindings", provider="other") == []
    assert [b.scope for b in h.admin("list_idp_bindings", policy_id=roles.MEMBER)] == [
        W2
    ]
    with h.as_(ada):  # only the bindings of the workspace ada administers
        assert [b.scope for b in h.iam.list_idp_bindings()] == [W1]


def test_binding_needs_the_right_to_attach_there(h, ada):
    carol = h.user("carol")
    with h.as_(ada):
        for scope, policy in ((W2, roles.VIEWER), (W1, roles.OWNER)):
            with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
                h.iam.bind_idp_group("acme", "eng", policy, scope)
    with h.as_(carol), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.bind_idp_group("acme", "eng", roles.VIEWER, W1)
    # A refused binding leaves nothing behind.
    assert h.iam.resolve_idp_groups("acme", ["eng"]) == []
    assert h.admin("list_idp_bindings") == []


def test_unbinding_removes_the_role_it_gave(h, ada):
    binding = h.admin("bind_idp_group", "acme", "eng", roles.VIEWER, W1)
    h.admin("bind_idp_group", "acme", "eng", roles.MEMBER, W2)
    with h.as_(ada):
        assert h.iam.unbind_idp_group("acme", "eng", roles.VIEWER, W1) is True
        assert h.iam.unbind_idp_group("acme", "eng", roles.VIEWER, W1) is False
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            h.iam.unbind_idp_group("acme", "eng", roles.MEMBER, W2)
    assert [(b.policy_id, b.scope) for b in h.admin("list_idp_bindings")] == [
        (roles.MEMBER, W2)
    ]
    reader = h.user("reader")
    assert not h.allowed(
        "triple_store:Query",
        graph("g", "acme", "ws1"),
        reader,
        groups=frozenset({binding.group_id}),
    )


def test_unbinding_never_touches_a_hand_made_group_that_maps_the_same_claim(h, ada):
    # A group an administrator made and mapped to the same claim, with a role at ws1.
    analysts = h.group("analysts")
    h.admin("map_idp_group", "acme", "eng", analysts.id)
    h.attach(roles.VIEWER, analysts.id, W1)
    binding = h.admin("bind_idp_group", "acme", "eng", roles.VIEWER, W1)
    assert binding.group_id != analysts.id
    with h.as_(ada):
        assert h.iam.unbind_idp_group("acme", "eng", roles.VIEWER, W1) is True
        assert h.iam.unbind_idp_group("acme", "eng", roles.VIEWER, W1) is False
    held = {
        (a.policy_id, a.scope)
        for a in h.iam.store.list_attachments(principal_id=analysts.id)
    }
    assert (roles.VIEWER, W1) in held
    # Nor does it list as a binding.
    assert h.admin("list_idp_bindings") == []


def test_listing_bindings_skips_hand_made_groups(h):
    analysts = h.group("analysts")
    h.admin("map_idp_group", "acme", "eng", analysts.id)
    h.attach(roles.VIEWER, analysts.id, W1)
    assert h.admin("list_idp_bindings") == []
    binding = h.admin("bind_idp_group", "acme", "eng", roles.MEMBER, W2)
    assert [b.group_id for b in h.admin("list_idp_bindings")] == [binding.group_id]


def test_a_sign_in_costs_nothing_when_nobody_was_invited(h, monkeypatch):
    bob = sign_in(h)
    calls = []
    original = h.iam.store.list_pending_grants
    monkeypatch.setattr(
        h.iam.store,
        "list_pending_grants",
        lambda **kw: calls.append(kw) or original(**kw),
    )
    assert h.admin("claim_pending_grants", bob.id) == []
    assert h.admin("claim_pending_grants", bob.id) == []
    assert calls == [{}]  # the index was read once, and rebuilt only on a change
    h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)
    assert len(h.admin("claim_pending_grants", bob.id)) == 1


def test_a_grant_is_revoked_by_id_without_listing_every_grant(h, monkeypatch):
    grant = h.admin("create_pending_grant", "builtin", BOB, roles.MEMBER, W1)

    def forbidden(**_):
        raise AssertionError("every grant was loaded")

    monkeypatch.setattr(h.iam.store, "list_pending_grants", forbidden)
    assert h.admin("revoke_pending_grant", grant.id) is True
    assert h.admin("revoke_pending_grant", grant.id) is False
