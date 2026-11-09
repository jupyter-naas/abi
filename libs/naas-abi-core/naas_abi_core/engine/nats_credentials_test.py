"""``issuer_source``: the serving engine's own tokens, and its delegations."""

from __future__ import annotations

import pytest
from naas_abi_core.engine import nats_credentials
from naas_abi_core.engine.call_context import Principal, as_service_account
from naas_abi_core.engine.nats_auth import AGENT_AUDIENCE
from naas_abi_core.engine.nats_identity import token_context
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import KeyRefusedError
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.modules import subject_token


@pytest.fixture
def iam() -> IAMService:
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    return service


def _user(iam, subject="bob") -> Principal:
    with as_service_account("engine"):
        record = iam.ensure_user("https://idp.example", subject)
    return Principal(id=record.id, kind="user")


def test_api_and_engine_delegate_a_user_to_the_kernel(iam):
    bob = _user(iam)
    for name in ("api", "engine"):
        source = nats_credentials.issuer_source(iam, name)
        claims = iam.verifier().verify(source.token_for(bob))
        assert claims.audience == AGENT_AUDIENCE
        assert claims.subject == bob.id
        assert claims.actor == iam.store.find_service_account(name).id
        # And without a user, the source's own token.
        assert iam.verifier().verify(source.token_for(None)).subject == claims.actor


def test_the_groups_of_a_user_travel_as_claims(iam):
    with as_service_account("engine"):
        sales = iam.create_group("sales")
    bob = Principal(
        id=_user(iam).id, kind="user", groups=frozenset({sales.id, "grp_unknown"})
    )
    claims = iam.verifier().verify(
        nats_credentials.issuer_source(iam, "api").token_for(bob)
    )
    assert claims.groups == (sales.id,)


def test_a_call_to_a_module_host_names_the_module_that_acts(iam):
    bob = _user(iam)
    with as_service_account("engine"):
        module = iam.create_service_account("module/acme/people")
    recipient = subject_token(module.id)
    source = nats_credentials.issuer_source(iam, "api")
    token = source.token_for(bob, recipient)
    claims = iam.verifier().verify(token)
    assert claims.actor == module.id and claims.subject == bob.id
    # The kernel accepts it as the module acting for bob: both sides decide.
    context = token_context(claims)
    assert context.principal.id == module.id
    assert context.on_behalf_of is not None and context.on_behalf_of.id == bob.id


def test_a_host_that_is_no_module_gets_no_delegation(iam):
    bob = _user(iam)
    source = nats_credentials.issuer_source(iam, "api")
    refused = (nats_credentials.DelegationError, KeyRefusedError)
    for recipient in ("0" * 26, "not-a-recipient"):
        with pytest.raises(refused):
            source.token_for(bob, recipient)
    engine = iam.store.find_service_account("engine")
    with pytest.raises(refused):
        source.token_for(bob, subject_token(engine.id))  # not a module account


def test_a_suspended_user_is_not_delegated(iam):
    bob = _user(iam)
    with as_service_account("engine"):
        iam.suspend_principal(bob.id)
    with pytest.raises(KeyRefusedError):
        nats_credentials.issuer_source(iam, "api").token_for(bob)


def test_host_audience_sources_do_not_delegate(iam):
    from naas_abi_core.engine.nats_auth import host_audience

    source = nats_credentials.issuer_source(iam, "api", host_audience("HOST"))
    bob = _user(iam)
    # A host token is the account's own, never a user's.
    assert source.token_for(bob) == source.token()


def test_the_scope_of_a_call_travels_in_its_delegation(iam):
    bob = _user(iam)
    scope = (
        {"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},
    )
    source = nats_credentials.issuer_source(iam, "api")
    claims = iam.verifier().verify(source.token_for(bob, None, scope))
    assert claims.scope == scope
    assert iam.verifier().verify(source.token_for(bob)).scope is None


def test_a_client_role_engine_carries_the_users_it_serves(iam, monkeypatch):
    """Its key is exchanged at the serving engine, and so are its delegations:
    without one it would call as ``engine`` alone and drop the user."""
    from naas_abi_core.engine.nats_auth import IssuedToken

    bob = _user(iam)
    own = iam.issue_service_token("engine")
    monkeypatch.setattr(
        nats_credentials,
        "exchange_key",
        lambda *args, **kwargs: IssuedToken(own.token, own.expires_at),
    )
    calls = []

    class ServingEngine:  # the IAM client: only what the delegation calls
        def exchange_token(self, request):
            calls.append(request)
            return iam.exchange_token(request)

    source = nats_credentials.client_engine_source(
        "nats://unused", "abi_sk_aaaaaaaaaaaaaaaa_c2VjcmV0", ServingEngine()
    )
    assert source.token() == own.token
    claims = iam.verifier().verify(source.token_for(bob))
    assert claims.subject == bob.id and claims.audience == AGENT_AUDIENCE
    assert claims.actor_name == "engine"
    assert [c.subject_token for c in calls] == [bob.id]


def test_a_cached_delegation_is_dropped_when_the_users_tokens_are_revoked(iam):
    """The cache holds a delegation for half its life: one made before a
    revocation must not be handed out after it, or every call of a user who
    signed in again would be refused until it expired."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
    )
    from naas_abi_core.engine.call_context import user as as_user

    bob = _user(iam)
    source = nats_credentials.issuer_source(iam, "api")
    first = source.token_for(bob)
    assert source.token_for(bob) == first  # cached
    with use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=as_user(bob.id))
    ):
        iam.revoke_tokens(bob.id)
    second = source.token_for(bob)
    assert second != first
    assert iam.verifier().verify(second).subject == bob.id
    with pytest.raises(Exception, match="revoked"):
        iam.verifier().verify(first)


def test_a_job_calls_over_nats_with_its_own_accounts_token():
    from types import SimpleNamespace

    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.engine.nats_credentials import JobAccountSource

    class Source:
        def __init__(self, name):
            self.identity = name

        def token(self):
            return f"token:{self.identity}"

        def token_for(self, user, recipient=None, scope=None):
            return f"delegation:{self.identity}:{user.id}"

    accounts = {}

    def for_account(name):
        accounts.setdefault(name, Source(name))
        return accounts[name]

    source = JobAccountSource(Source("engine"), for_account)
    assert source.identity == "engine"
    assert source.token() == "token:engine"
    with as_service_account("job/acme.jobs"):
        assert source.token() == "token:job/acme.jobs"
        # A call made for a user is the engine's delegation, whoever asks.
        assert source.token_for(SimpleNamespace(id="u1")) == "delegation:engine:u1"
    with as_service_account("module/default/people"):
        assert source.token() == "token:engine"
