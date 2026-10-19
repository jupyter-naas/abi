"""Token exchange (RFC §9.4): narrow, engine-signed tokens, each with its own
audience, derived from an identity that was already verified."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from naas_abi_core.engine import nats_auth
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_auth import (
    AGENT_AUDIENCE,
    API_KEY_AUDIENCE,
    APP_AUDIENCE,
    CODING_AUDIENCE,
    PREVIEW_AUDIENCE,
    SESSION_AUDIENCE,
    InvalidServiceTokenError,
)
from naas_abi_core.engine.nats_identity import token_context
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_ACCESS_TOKEN,
    TOKEN_TYPE_API_KEY,
    TOKEN_TYPE_ID_TOKEN,
    TOKEN_TYPE_JWT,
    TOKEN_TYPE_SESSION,
    IAMConflictError,
    KeyRefusedError,
    PermissionDeniedError,
    TokenExchange,
)
from naas_abi_core.services.iam.tests.iam_harness import graph, statement

QUERY = "triple_store:Query"
INSERT = "triple_store:Insert"
MODULE = "abi:-:-:discovery:module/acme/people"
ALL_DELEGATED = nats_auth.DELEGATED_AUDIENCES


def _verify(iam, token, *audiences):
    return iam.verifier(audiences or (AGENT_AUDIENCE,)).verify(token)


def _exchange(iam, **fields):
    """As ``api``: the only account that exchanges for any audience."""
    with as_service_account("api"):
        return iam.exchange_token(TokenExchange(**fields))


def _vouched(iam, user_id, audience, **fields):
    return _exchange(
        iam,
        subject_token=user_id,
        subject_token_type=TOKEN_TYPE_SESSION,
        audience=audience,
        **fields,
    )


@pytest.fixture
def bob(h):
    record = h.user("bob")
    h.grant(record.id, statement("Allow", [QUERY], [graph("*")]))
    return record


@pytest.fixture
def people(h):
    """The module account of acme/people, allowed to insert and query."""
    account = h.service_account("module/acme/people")
    h.grant(account.id, statement("Allow", [QUERY, INSERT], [graph("*")]))
    return account


# -- who may exchange, and from what --------------------------------------------------


def test_api_vouches_for_a_session_user_and_gets_an_agent_token_acting_as_itself(
    h, iam, bob
):
    issued = _vouched(iam, bob.id, AGENT_AUDIENCE)
    claims = _verify(iam, issued.token)
    assert claims.subject == bob.id and claims.kind == "user"
    assert claims.audience == AGENT_AUDIENCE
    assert claims.actor == iam.store.find_service_account("api").id
    assert 0 < claims.lifetime <= 600
    assert claims.since == claims.issued_at


def test_the_exchange_needs_the_requesters_own_iam_action(h, iam, bob, people):
    # A module holds no iam:ExchangeToken; acting for bob changes nothing.
    with h.as_(people), pytest.raises(PermissionDeniedError):
        iam.exchange_token(
            TokenExchange(
                subject_token=bob.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=AGENT_AUDIENCE,
            )
        )
    # A user does not either, not even for their own session.
    with h.as_(bob), pytest.raises(PermissionDeniedError):
        iam.exchange_token(
            TokenExchange(
                subject_token=bob.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=AGENT_AUDIENCE,
            )
        )
    # api acting on behalf of bob is still api: the user's side does not decide.
    with h.as_(actor="api", on_behalf_of=bob):
        assert iam.exchange_token(
            TokenExchange(
                subject_token=bob.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=AGENT_AUDIENCE,
            )
        ).token


def test_only_a_first_party_vouches_for_a_session_user(h, iam, bob):
    # A grant of iam:ExchangeToken alone does not make a module a Nexus.
    module = h.service_account("module/acme/rogue")
    h.grant(module.id, statement("Allow", ["iam:ExchangeToken"], ["*"]))
    with h.as_(module), pytest.raises(PermissionDeniedError, match="first-party"):
        iam.exchange_token(
            TokenExchange(
                subject_token=bob.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=AGENT_AUDIENCE,
            )
        )


def test_a_suspended_or_deleted_user_gets_nothing(h, iam, bob):
    h.admin("suspend_principal", bob.id)
    with pytest.raises(KeyRefusedError):
        _vouched(iam, bob.id, AGENT_AUDIENCE)
    h.admin("resume_principal", bob.id)
    assert _vouched(iam, bob.id, AGENT_AUDIENCE).token


@pytest.mark.parametrize(
    "audience", ["abi:nats", "abi:host:abc", "abi:delegated:other", "abi:anything", ""]
)
def test_only_the_session_and_delegated_audiences_are_issued(h, iam, bob, audience):
    with pytest.raises(ValueError):
        _vouched(iam, bob.id, audience)


def test_a_session_user_may_be_one_iam_has_no_record_of(h, iam):
    # Nexus's own users are not in IAM until their login moves (#67).
    claims = _verify(iam, _vouched(iam, "nexus-user-1", AGENT_AUDIENCE).token)
    assert claims.subject == "nexus-user-1"


def test_a_vouched_user_is_named_one_plain_id(h, iam):
    for bad in ("", " bob", "bob\n", "x" * 300):
        with pytest.raises(ValueError):
            _vouched(iam, bad, AGENT_AUDIENCE)


# -- engine tokens: only toward a narrower audience --------------------------------------


def _session_token(h, iam, user):
    """What an IdP login yields: an abi:session token (issued as Nexus would)."""
    return _vouched(iam, user.id, SESSION_AUDIENCE).token


def test_a_session_exchanges_to_every_delegated_audience_but_never_back(h, iam, bob):
    session = _session_token(h, iam, bob)
    for audience in (APP_AUDIENCE, PREVIEW_AUDIENCE, CODING_AUDIENCE, API_KEY_AUDIENCE):
        issued = _exchange(
            iam,
            subject_token=session,
            subject_token_type=TOKEN_TYPE_JWT,
            audience=audience,
        )
        claims = _verify(iam, issued.token, audience)
        assert claims.subject == bob.id and claims.actor is None
    with pytest.raises(PermissionDeniedError, match="session"):
        _exchange(
            iam,
            subject_token=session,
            subject_token_type=TOKEN_TYPE_JWT,
            audience=SESSION_AUDIENCE,
        )


def test_a_delegated_token_never_becomes_another_delegated_audience(h, iam, bob):
    app = _exchange(
        iam,
        subject_token=_session_token(h, iam, bob),
        subject_token_type=TOKEN_TYPE_JWT,
        audience=APP_AUDIENCE,
    ).token
    for audience in (SESSION_AUDIENCE, *ALL_DELEGATED):
        with pytest.raises(PermissionDeniedError):
            _exchange(
                iam,
                subject_token=app,
                subject_token_type=TOKEN_TYPE_JWT,
                audience=audience,
            )


def test_a_service_token_is_not_a_subject(h, iam, bob):
    own = iam.issue_service_token("api").token
    with pytest.raises(InvalidServiceTokenError):
        _exchange(
            iam,
            subject_token=own,
            subject_token_type=TOKEN_TYPE_JWT,
            audience=APP_AUDIENCE,
        )
    with pytest.raises(InvalidServiceTokenError):
        _exchange(
            iam,
            subject_token="nonsense",
            subject_token_type=TOKEN_TYPE_JWT,
            audience=APP_AUDIENCE,
        )


def test_an_unknown_subject_token_type_is_refused(h, iam, bob):
    with pytest.raises(ValueError, match="subject_token_type"):
        _exchange(
            iam,
            subject_token=bob.id,
            subject_token_type="urn:made:up",
            audience=APP_AUDIENCE,
        )


# -- the actor of an agent token -------------------------------------------------------------


def test_a_resource_names_the_module_that_acts_for_the_user(h, iam, bob, people):
    issued = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)
    claims = _verify(iam, issued.token)
    assert claims.actor == people.id and claims.subject == bob.id
    assert claims.resource == MODULE
    # The same resource, spelled as one of its agents, names the same module.
    agent = "abi:-:-:discovery:agent/acme/people/summarize"
    assert (
        _verify(iam, _vouched(iam, bob.id, AGENT_AUDIENCE, resource=agent).token).actor
        == people.id
    )


def test_a_resource_that_is_no_module_or_has_no_account_is_refused(h, iam, bob, people):
    for resource in (
        "abi:-:-:triple_store:graph/x",
        "abi:-:-:discovery:module/acme/ghost",
        "not a name",
    ):
        with pytest.raises((ValueError, KeyRefusedError)):
            _vouched(iam, bob.id, AGENT_AUDIENCE, resource=resource)
    h.admin("suspend_principal", people.id)
    with pytest.raises(KeyRefusedError):
        _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)


def test_the_context_of_an_agent_token_is_the_module_for_the_user(h, iam, bob, people):
    issued = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)
    context = token_context(_verify(iam, issued.token))
    assert context.principal.id == people.id
    assert context.principal.kind == "service_account"
    assert context.on_behalf_of is not None and context.on_behalf_of.id == bob.id
    assert context.audience == AGENT_AUDIENCE
    # Both sides must allow: the module may Insert but bob may not.
    assert iam.authorizer.check(context, QUERY, graph("g")).allowed
    assert not iam.authorizer.check(context, INSERT, graph("g")).allowed


def test_the_module_renews_its_own_delegation_and_nobody_else_does(h, iam, bob, people):
    first = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)
    other = h.service_account("module/acme/other")

    def renew(requester):
        with h.as_(requester):
            return iam.exchange_token(
                TokenExchange(
                    subject_token=first.token,
                    subject_token_type=TOKEN_TYPE_JWT,
                    audience=AGENT_AUDIENCE,
                )
            )

    renewed = _verify(iam, renew(people).token)
    original = _verify(iam, first.token)
    assert renewed.subject == bob.id and renewed.actor == people.id
    assert renewed.since == original.since  # the chain keeps its start
    assert renewed.token_id != original.token_id
    with pytest.raises(PermissionDeniedError):
        renew(other)
    with pytest.raises(PermissionDeniedError):
        renew(bob)


def test_renewals_stop_after_eight_hours(h, iam, bob, people):
    first = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)
    start = _verify(iam, first.token).issued_at
    later = datetime.fromtimestamp(start, UTC) + timedelta(hours=8, seconds=5)
    iam.tokens._clock = lambda: later
    with h.as_(people), pytest.raises(PermissionDeniedError, match="renew"):
        iam.exchange_token(
            TokenExchange(
                subject_token=first.token,
                subject_token_type=TOKEN_TYPE_JWT,
                audience=AGENT_AUDIENCE,
            )
        )


def test_a_renewal_never_outlives_the_cap(h, iam, bob, people):
    first = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE)
    start = _verify(iam, first.token).issued_at
    near = datetime.fromtimestamp(start, UTC) + timedelta(hours=7, minutes=58)
    iam.tokens._clock = lambda: near
    with h.as_(people):
        renewed = iam.exchange_token(
            TokenExchange(
                subject_token=first.token,
                subject_token_type=TOKEN_TYPE_JWT,
                audience=AGENT_AUDIENCE,
            )
        )
    cap = start + nats_auth.MAX_DELEGATION_SECONDS
    assert renewed.expires_at <= cap


# -- scope: an exchange only narrows --------------------------------------------------------


READ_ONE = ({"effect": "Allow", "actions": [QUERY], "resources": [graph("one")]},)


def test_a_requested_scope_narrows_the_token(h, iam, bob):
    issued = _vouched(iam, bob.id, AGENT_AUDIENCE, scope=READ_ONE)
    claims = _verify(iam, issued.token)
    assert claims.scope == READ_ONE
    context = token_context(claims)
    # The actor (api) and bob allow it; the token allows graph one only.
    assert iam.authorizer.check(context, QUERY, graph("one")).allowed
    assert not iam.authorizer.check(context, QUERY, graph("two")).allowed


@pytest.mark.parametrize(
    "scope",
    [
        ({"effect": "Deny", "actions": ["*"], "resources": ["*"]},),
        ({"effect": "Allow", "actions": "triple_store:Query", "resources": ["*"]},),
        ({"effect": "Allow", "actions": [QUERY]},),
        ("Allow",),
        tuple(
            {"effect": "Allow", "actions": [QUERY], "resources": ["*"]}
            for _ in range(40)
        ),
    ],
)
def test_a_malformed_scope_is_refused(h, iam, bob, scope):
    with pytest.raises(ValueError, match="scope"):
        _vouched(iam, bob.id, AGENT_AUDIENCE, scope=scope)


def test_a_token_that_is_already_narrowed_is_not_narrowed_again(h, iam, bob):
    session = _vouched(iam, bob.id, SESSION_AUDIENCE, scope=READ_ONE).token
    inherited = _exchange(
        iam,
        subject_token=session,
        subject_token_type=TOKEN_TYPE_JWT,
        audience=APP_AUDIENCE,
    )
    assert _verify(iam, inherited.token, APP_AUDIENCE).scope == READ_ONE
    with pytest.raises(ValueError, match="scope"):
        _exchange(
            iam,
            subject_token=session,
            subject_token_type=TOKEN_TYPE_JWT,
            audience=APP_AUDIENCE,
            scope=({"effect": "Allow", "actions": ["*"], "resources": ["*"]},),
        )


def test_groups_in_a_token_are_only_groups(h, iam, bob):
    """A user's or an account's id in the groups claim must not lend its policies
    (the #57 review): only ids of active groups count."""
    admin = h.user("admin")
    h.grant(admin.id, statement("Allow", [INSERT], [graph("*")]))
    sales = h.group("sales")
    h.grant(sales.id, statement("Allow", ["triple_store:ListGraphs"], ["*"]))
    issued = _vouched(
        iam, bob.id, AGENT_AUDIENCE, groups=(admin.id, sales.id, "grp_unknown")
    )
    claims = _verify(iam, issued.token)
    assert set(claims.groups) == {sales.id}
    # Even a token that was forged with them is read as groups only.
    from dataclasses import replace

    from naas_abi_core.engine.call_context import Principal

    forged = Principal(id=bob.id, kind="user", groups=frozenset({admin.id, sales.id}))
    context = replace(token_context(claims), on_behalf_of=forged)
    assert not iam.authorizer.check(context, INSERT, graph("g")).allowed
    # A group that is gone grants nothing, whatever the token says.
    allowed = iam.authorizer.check(
        token_context(claims), "triple_store:ListGraphs", graph("g")
    ).allowed
    assert allowed
    h.admin("delete_group", sales.id)
    assert not iam.authorizer.check(
        token_context(claims), "triple_store:ListGraphs", graph("g")
    ).allowed


# -- identity-provider tokens ---------------------------------------------------------------


class _Idp:
    def __init__(self, principal_id, groups=()):
        self.principal_id, self.groups, self.seen = principal_id, groups, []

    def authenticate_token(self, token, token_type):
        self.seen.append((token, token_type))
        if token != "good":
            raise InvalidServiceTokenError("not a token of a provider")
        return self.principal_id, tuple(self.groups)


def test_an_idp_token_buys_a_session_token_and_nothing_else(h, iam, bob):
    sales = h.group("sales")
    iam.identity_authenticator = idp = _Idp(bob.id, (sales.id,))
    for token_type in (TOKEN_TYPE_ID_TOKEN, TOKEN_TYPE_ACCESS_TOKEN):
        issued = _exchange(
            iam,
            subject_token="good",
            subject_token_type=token_type,
            audience=SESSION_AUDIENCE,
        )
        claims = _verify(iam, issued.token, SESSION_AUDIENCE)
        assert claims.subject == bob.id and claims.kind == "user"
        assert claims.groups == (sales.id,)
        assert claims.actor is None
    assert [t for _, t in idp.seen] == [TOKEN_TYPE_ID_TOKEN, TOKEN_TYPE_ACCESS_TOKEN]
    for audience in ALL_DELEGATED:
        with pytest.raises(PermissionDeniedError):
            _exchange(
                iam,
                subject_token="good",
                subject_token_type=TOKEN_TYPE_ID_TOKEN,
                audience=audience,
            )
    with pytest.raises(InvalidServiceTokenError):
        _exchange(
            iam,
            subject_token="bad",
            subject_token_type=TOKEN_TYPE_ID_TOKEN,
            audience=SESSION_AUDIENCE,
        )


def test_idp_tokens_need_a_configured_identity_service(h, iam, bob):
    with pytest.raises(ValueError, match="identity"):
        _exchange(
            iam,
            subject_token="good",
            subject_token_type=TOKEN_TYPE_ID_TOKEN,
            audience=SESSION_AUDIENCE,
        )


def test_a_suspended_idp_user_gets_no_session(h, iam, bob):
    iam.identity_authenticator = _Idp(bob.id)
    h.admin("suspend_principal", bob.id)
    with pytest.raises(KeyRefusedError):
        _exchange(
            iam,
            subject_token="good",
            subject_token_type=TOKEN_TYPE_ID_TOKEN,
            audience=SESSION_AUDIENCE,
        )


# -- personal keys, coding keys and link grants -------------------------------------------------


def _key(h, user, **fields):
    with h.as_(actor="api", on_behalf_of=user):
        return h.iam.create_key(user.id, **fields)


def _by_key(iam, value, audience=None, **fields):
    return _exchange(
        iam,
        subject_token=value,
        subject_token_type=TOKEN_TYPE_API_KEY,
        audience=audience or API_KEY_AUDIENCE,
        **fields,
    )


def test_a_personal_key_is_shown_once_hashed_and_buys_an_api_key_token(h, iam, bob):
    created = _key(h, bob, description="ci")
    assert created.value.startswith(f"abi_pk_{created.record.key_id}_")
    assert created.record.kind == "personal"
    assert created.record.audience == API_KEY_AUDIENCE
    # Personal keys expire: one year at most, by default exactly that.
    assert created.record.expires_at is not None
    life = created.record.expires_at - created.record.created_at
    assert timedelta(days=364) < life <= timedelta(days=366)
    stored = iam.store.get_key(created.record.key_id)
    assert created.value.split("_", 3)[3] not in repr(stored)

    claims = _verify(iam, _by_key(iam, created.value).token, API_KEY_AUDIENCE)
    assert claims.subject == bob.id and claims.kind == "user" and claims.actor is None
    assert iam.store.get_key(created.record.key_id).last_used_at is not None


def test_a_personal_key_cannot_outlive_a_year(h, iam, bob):
    too_long = datetime.now(UTC) + timedelta(days=400)
    with pytest.raises(ValueError, match="year"):
        _key(h, bob, expires_at=too_long)
    fine = _key(h, bob, expires_at=datetime.now(UTC) + timedelta(days=30))
    assert fine.record.expires_at is not None


def test_a_key_scope_narrows_every_token_it_buys(h, iam, bob):
    created = _key(h, bob, scope=READ_ONE)
    claims = _verify(iam, _by_key(iam, created.value).token, API_KEY_AUDIENCE)
    assert claims.scope == READ_ONE
    with pytest.raises(ValueError, match="scope"):
        _by_key(iam, created.value, scope=READ_ONE)  # no widening, no re-narrowing


def test_a_personal_key_reaches_only_its_own_audience(h, iam, bob):
    created = _key(h, bob)
    for audience in (SESSION_AUDIENCE, AGENT_AUDIENCE, APP_AUDIENCE, CODING_AUDIENCE):
        with pytest.raises((PermissionDeniedError, KeyRefusedError)):
            _by_key(iam, created.value, audience)


def test_a_coding_key_is_bound_to_its_environment_and_reaches_coding_only(h, iam, bob):
    created = _key(h, bob, audience=CODING_AUDIENCE, resource="env-1", scope=READ_ONE)
    assert created.record.kind == "personal"
    issued = _by_key(iam, created.value, CODING_AUDIENCE)
    claims = _verify(iam, issued.token, CODING_AUDIENCE)
    assert claims.subject == bob.id and claims.resource == "env-1"
    assert claims.scope == READ_ONE
    with pytest.raises((PermissionDeniedError, KeyRefusedError)):
        _by_key(iam, created.value, API_KEY_AUDIENCE)


def test_keys_for_other_purposes_are_not_the_personal_keys_of_a_user(h, iam, bob):
    _key(h, bob, audience=CODING_AUDIENCE, resource="env-1")
    plain = [
        k
        for k in h.admin("list_keys", bob.id)
        if k.kind == "personal" and k.audience == API_KEY_AUDIENCE
    ]
    assert plain == []
    # Coding and grant keys do not count against the five personal ones.
    for _ in range(5):
        _key(h, bob)
    for index in range(8):
        _key(h, bob, audience=CODING_AUDIENCE, resource=f"env-{index + 2}")
    with pytest.raises(IAMConflictError):
        _key(h, bob)


def test_a_link_grant_opens_one_audience_for_hours_and_is_revocable(h, iam, bob):
    expires = datetime.now(UTC) + timedelta(hours=1)
    grant = _key(
        h,
        bob,
        kind="grant",
        audience=APP_AUDIENCE,
        resource="abi:-:-:discovery:app/acme/people/crm",
        scope=(
            {"effect": "Allow", "actions": ["discovery:OpenApp"], "resources": ["*"]},
        ),
        expires_at=expires,
    )
    assert grant.value.startswith("abi_gk_")
    claims = _verify(iam, _by_key(iam, grant.value, APP_AUDIENCE).token, APP_AUDIENCE)
    assert claims.subject == bob.id and claims.audience == APP_AUDIENCE
    assert claims.resource == "abi:-:-:discovery:app/acme/people/crm"
    with pytest.raises((PermissionDeniedError, KeyRefusedError)):
        _by_key(iam, grant.value, API_KEY_AUDIENCE)
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_key(bob.id, grant.record.key_id)
    with pytest.raises(KeyRefusedError):
        _by_key(iam, grant.value, APP_AUDIENCE)


def test_a_grant_lasts_at_most_eight_hours(h, iam, bob):
    with pytest.raises(ValueError, match="8 hours"):
        _key(
            h,
            bob,
            kind="grant",
            audience=APP_AUDIENCE,
            expires_at=datetime.now(UTC) + timedelta(hours=9),
        )
    with pytest.raises(ValueError, match="expir"):
        _key(h, bob, kind="grant", audience=APP_AUDIENCE)  # a grant always expires
    with pytest.raises(ValueError, match="audience"):
        _key(
            h,
            bob,
            kind="grant",
            audience=API_KEY_AUDIENCE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_key_audiences_and_kinds_are_checked_at_creation(h, iam, bob):
    for audience in (SESSION_AUDIENCE, AGENT_AUDIENCE, "abi:nats", "abi:other"):
        with pytest.raises(ValueError, match="audience"):
            _key(h, bob, audience=audience)
    with pytest.raises(ValueError, match="kind"):
        _key(h, bob, kind="service")
    with pytest.raises(ValueError, match="resource"):
        _key(h, bob, audience=CODING_AUDIENCE)  # a coding key names its environment


def test_users_manage_only_their_own_keys(h, iam, bob):
    alice = h.user("alice")
    created = _key(h, bob)
    with h.as_(actor="api", on_behalf_of=alice):
        with pytest.raises((PermissionDeniedError, LookupError)):
            iam.revoke_key(bob.id, created.record.key_id)
        with pytest.raises((PermissionDeniedError, LookupError)):
            iam.create_key(bob.id)
        assert iam.list_keys(bob.id) == []
    with h.as_(actor="api", on_behalf_of=bob):
        assert [k.key_id for k in iam.list_keys(bob.id)] == [created.record.key_id]


def test_revoked_expired_and_suspended_owner_stop_a_personal_key(h, iam, bob):
    revoked = _key(h, bob)
    assert _by_key(iam, revoked.value).token
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_key(bob.id, revoked.record.key_id)
    with pytest.raises(KeyRefusedError):
        _by_key(iam, revoked.value)

    live = _key(h, bob)
    h.admin("suspend_principal", bob.id)
    with pytest.raises(KeyRefusedError):
        _by_key(iam, live.value)
    h.admin("resume_principal", bob.id)
    assert _by_key(iam, live.value).token


def test_a_service_key_is_not_exchanged_here_and_a_personal_key_not_there(h, iam, bob):
    account = h.service_account("module/acme/people")
    service = h.admin("create_key", account.id).value
    with pytest.raises(KeyRefusedError):
        _by_key(iam, service)
    personal = _key(h, bob).value
    with pytest.raises(KeyRefusedError):
        iam.exchange_key(personal)
    with pytest.raises(KeyRefusedError):
        iam.authenticate_key(personal)


@pytest.mark.parametrize(
    "mangle",
    [
        lambda v: v[:-1] + ("A" if v[-1] != "A" else "B"),
        lambda v: "abi_pk_aaaaaaaaaaaaaaaa_" + v.split("_", 3)[3],
        lambda v: v.replace("abi_pk_", "abi_gk_"),
        lambda v: "not-a-key",
    ],
)
def test_a_bad_personal_key_is_refused_with_one_message(h, iam, bob, mangle):
    value = _key(h, bob).value
    with pytest.raises(KeyRefusedError, match="^invalid key$"):
        _by_key(iam, mangle(value))


# -- revoking all of a user's tokens ------------------------------------------------------------


def _delegated_for(iam, user):
    return _vouched(iam, user.id, AGENT_AUDIENCE).token


def test_revoking_tokens_cuts_off_what_was_issued_before(h, iam, bob):
    token = _delegated_for(iam, bob)
    assert _verify(iam, token)
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    with pytest.raises(InvalidServiceTokenError, match="revoked"):
        _verify(iam, token)
    # The kernel's own verifier is the same one.
    with pytest.raises(InvalidServiceTokenError, match="revoked"):
        iam.verifier().verify(token)


def test_tokens_issued_after_the_revocation_work(h, iam, bob):
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    later = datetime.now(UTC) + timedelta(seconds=3)
    iam.tokens._clock = lambda: later
    assert _verify(iam, _delegated_for(iam, bob))


def test_revoked_tokens_do_not_renew(h, iam, bob, people):
    first = _vouched(iam, bob.id, AGENT_AUDIENCE, resource=MODULE).token
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    with h.as_(people), pytest.raises(InvalidServiceTokenError):
        iam.exchange_token(
            TokenExchange(
                subject_token=first,
                subject_token_type=TOKEN_TYPE_JWT,
                audience=AGENT_AUDIENCE,
            )
        )


def test_revoking_tokens_also_ends_links_and_coding_keys_but_not_api_keys(h, iam, bob):
    api_key = _key(h, bob)
    coding = _key(h, bob, audience=CODING_AUDIENCE, resource="env-1")
    grant = _key(
        h,
        bob,
        kind="grant",
        audience=APP_AUDIENCE,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    assert _by_key(iam, api_key.value).token
    for gone, audience in ((coding, CODING_AUDIENCE), (grant, APP_AUDIENCE)):
        with pytest.raises(KeyRefusedError):
            _by_key(iam, gone.value, audience)


def test_revoking_tokens_with_keys_ends_the_api_keys_too(h, iam, bob):
    api_key = _key(h, bob)
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id, include_keys=True)
    with pytest.raises(KeyRefusedError):
        _by_key(iam, api_key.value)


def test_a_user_revokes_their_own_tokens_and_nobody_elses(h, iam, bob):
    alice = h.user("alice")
    with (
        h.as_(actor="api", on_behalf_of=alice),
        pytest.raises((PermissionDeniedError, LookupError)),
    ):
        iam.revoke_tokens(bob.id)


def test_suspending_a_user_cuts_off_their_delegated_tokens_at_the_kernel(h, iam, bob):
    token = _delegated_for(iam, bob)
    context = token_context(_verify(iam, token))
    assert iam.authorizer.check(context, QUERY, graph("g")).allowed
    h.admin("suspend_principal", bob.id)
    decision = iam.authorizer.check(context, QUERY, graph("g"))
    assert not decision.allowed and decision.reason == "suspended"


def test_a_floor_cuts_off_a_token_in_the_authorizer_too(h, iam, bob):
    """A token that was verified before the revocation, and is still held by a
    long call, stops being honoured at the next check."""
    token = _delegated_for(iam, bob)
    claims = _verify(iam, token)
    context = token_context(claims)
    assert iam.authorizer.check(context, QUERY, graph("g")).allowed
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    decision = iam.authorizer.check(context, QUERY, graph("g"))
    assert not decision.allowed and decision.reason == "suspended"


def test_the_clock_of_the_floor_is_the_issue_time(h, iam, bob):
    token = _delegated_for(iam, bob)
    claims = _verify(iam, token)
    with h.as_(actor="api", on_behalf_of=bob):
        iam.revoke_tokens(bob.id)
    assert iam.token_revoked(claims)
    # Tokens of others are untouched.
    other = _verify(iam, _delegated_for(iam, h.user("alice")))
    assert not iam.token_revoked(other)
    time.sleep(0)
