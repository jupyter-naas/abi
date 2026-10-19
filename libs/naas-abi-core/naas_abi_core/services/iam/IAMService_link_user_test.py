"""Linking an identity provider's identity to a user that already exists (#67):
the built-in login's users keep their principal, roles, groups and data when they
first sign in through the built-in identity provider."""

from __future__ import annotations

import pytest

from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.tests.iam_harness import graph

ISSUER = "https://idp.example"
W1 = "abi:acme:ws1"


@pytest.fixture
def legacy(h):
    """A user of the built-in login: IAM's user of the Nexus issuer, a member of ws1."""
    record = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "user-0123456789ab")
    h.attach(roles.MEMBER, record.id, W1)
    return record


def sign_in(h, subject="s1", **profile):
    profile = {"provider": "builtin", "email": "bob@example.com", "email_verified": True} | profile
    return h.user(subject, **profile)


def link(h, record, subject="s1", **profile):
    profile = {"provider": "builtin", "email": "bob@example.com", "email_verified": True} | profile
    return h.admin("link_user", record.id, ISSUER, subject, **profile)


def held(h, record) -> set[tuple[str, str | None]]:
    return {
        (a.policy_id, a.scope) for a in h.iam.store.list_attachments(principal_id=record.id)
    }


def test_the_identity_resolves_to_the_existing_user_and_its_roles(h, legacy):
    linked = link(h, legacy)
    assert linked.id == legacy.id
    again = sign_in(h)
    assert again.id == legacy.id
    assert (again.provider, again.email, again.email_verified) == (
        "builtin",
        "bob@example.com",
        True,
    )
    assert (roles.MEMBER, W1) in held(h, legacy)
    # Nexus still names the user by its own id.
    assert h.iam.resolve_user("user-0123456789ab").id == legacy.id


def test_a_sign_in_that_already_made_its_own_user_is_merged_into_the_existing_one(h, legacy):
    made = sign_in(h)
    assert made.id != legacy.id
    h.attach(roles.VIEWER, made.id, "abi:acme:ws2")
    h.attach(roles.MEMBER, made.id, W1)  # the same role the legacy user holds
    team = h.group("team")
    with_group = team.id
    h.admin("add_group_member", with_group, made.id)

    linked = link(h, legacy)

    assert linked.id == legacy.id
    assert sign_in(h).id == legacy.id
    assert held(h, legacy) >= {(roles.MEMBER, W1), (roles.VIEWER, "abi:acme:ws2")}
    assert with_group in h.iam.store.groups_of(legacy.id)
    retired = h.iam.store.get_principal(made.id)
    assert retired.status == "deleted"
    assert held(h, retired) == set()
    assert h.iam.store.groups_of(made.id) == []


def test_the_user_made_by_the_sign_in_is_refused_when_it_holds_keys(h, legacy):
    made = sign_in(h)
    h.admin("create_key", made.id, description="a script")
    with pytest.raises(IAMConflictError):
        link(h, legacy)
    # Nothing moved: the identity still resolves to the user that holds the key.
    assert sign_in(h).id == made.id
    assert h.iam.store.get_principal(made.id).status == "active"


def test_only_a_user_of_the_built_in_login_is_linked(h):
    other = h.user("someone-else")
    with pytest.raises(IAMConflictError):
        link(h, other, subject="s1")
    account = h.service_account("ci/nightly")
    with pytest.raises(IAMConflictError):
        link(h, account, subject="s1")
    with pytest.raises(IAMNotFoundError):
        h.admin("link_user", "usr_00000000000000000000000000", ISSUER, "s1")


def test_an_identity_belonging_to_another_linked_user_is_refused(h, legacy):
    other = h.admin("ensure_user", LEGACY_NEXUS_ISSUER, "user-ffffffffffff")
    link(h, other, subject="s1")
    with pytest.raises(IAMConflictError):
        link(h, legacy, subject="s1")
    assert sign_in(h).id == other.id


def test_linking_twice_is_the_same_link(h, legacy):
    assert link(h, legacy).id == link(h, legacy).id == legacy.id


def test_a_user_is_linked_through_another_identity_only_once_per_issuer_subject(h, legacy):
    link(h, legacy, subject="s1")
    # A second identity at the same provider (another subject) is another link,
    # for the same user: nothing forbids it, and neither is lost.
    link(h, legacy, subject="s2")
    assert sign_in(h, "s1").id == sign_in(h, "s2").id == legacy.id


def test_linking_is_an_administrators_call(h, legacy):
    ada = h.user("ada", email="ada@example.com", provider="builtin")
    h.attach(roles.ADMIN, ada.id, W1)
    with h.as_(ada), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.link_user(legacy.id, ISSUER, "s1")
    assert h.iam.store.find_user(ISSUER, "s1") is None


def test_a_suspended_user_stays_suspended_through_the_link(h, legacy):
    h.admin("suspend_principal", legacy.id)
    with pytest.raises(IAMConflictError):
        link(h, legacy)


def test_the_link_gives_the_user_what_its_roles_reach(h, legacy):
    from naas_abi_core.engine.call_context import CallContext, Principal, use_call_context

    link(h, legacy)
    h.first_party_may("triple_store")
    ctx = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id=sign_in(h).id, kind="user"),
    )
    with use_call_context(ctx):
        assert h.iam.authorize("triple_store:Query", graph("a", "acme", "ws1")).allowed
