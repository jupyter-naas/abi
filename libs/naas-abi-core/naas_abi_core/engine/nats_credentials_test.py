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
