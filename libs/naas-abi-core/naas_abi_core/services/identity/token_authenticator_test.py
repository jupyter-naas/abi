"""An IdP's token, exchanged for a session through IAM."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_auth import (
    API_KEY_AUDIENCE,
    SESSION_AUDIENCE,
    InvalidServiceTokenError,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_ID_TOKEN,
    KeyRefusedError,
    PermissionDeniedError,
    TokenExchange,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.identity.IdentityPorts import (
    AuthenticatedUser,
    PrincipalSuspendedError,
    TokenRejectedError,
    VerifiedToken,
)
from naas_abi_core.services.identity.token_authenticator import (
    IdentityTokenAuthenticator,
)


class _Identity:
    def __init__(self, iam):
        self.iam, self.calls = iam, []

    def authenticate(self, token, *, nonce=None):
        from naas_abi_core.engine.call_context import current_call_context

        # The IdP-side check runs for the requester alone.
        assert current_call_context().on_behalf_of is None
        self.calls.append(token)
        if token == "rejected":
            raise TokenRejectedError("bad_signature", "no")
        if token == "suspended":
            raise PrincipalSuspendedError("usr_x", "suspended")
        with as_service_account("engine"):
            record = self.iam.ensure_user("https://idp.example", token)
            group = self.iam.create_group("sales")
        verified = VerifiedToken(
            provider="acme",
            issuer="https://idp.example",
            subject=token,
            audience=("client",),
            issued_at=0,
            expires_at=1,
        )
        return AuthenticatedUser(
            principal_id=record.id, token=verified, group_ids=(group.id,)
        )


@pytest.fixture
def iam():
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    service.identity_authenticator = IdentityTokenAuthenticator(_Identity(service))
    return service


def exchange(iam, token, audience=SESSION_AUDIENCE, requester="api"):
    with as_service_account(requester):
        return iam.exchange_token(TokenExchange(token, TOKEN_TYPE_ID_TOKEN, audience))


def test_an_idp_token_becomes_a_session_of_its_iam_user_with_its_groups(iam):
    issued = exchange(iam, "ada")
    claims = iam.verifier((SESSION_AUDIENCE,)).verify(issued.token)
    assert claims.kind == "user" and claims.audience == SESSION_AUDIENCE
    record = iam.store.find_user("https://idp.example", "ada")
    assert claims.subject == record.id
    assert len(claims.groups) == 1


def test_a_token_no_provider_vouches_for_is_refused(iam):
    with pytest.raises(InvalidServiceTokenError):
        exchange(iam, "rejected")


def test_a_suspended_user_gets_no_session_and_no_reason(iam):
    with pytest.raises(KeyRefusedError, match="^invalid key$"):
        exchange(iam, "suspended")


def test_only_the_session_audience_is_for_an_idp_token(iam):
    with pytest.raises(PermissionDeniedError):
        exchange(iam, "ada", API_KEY_AUDIENCE)


def test_the_requester_needs_the_exchange_action(iam):
    with as_service_account("engine"):
        account = iam.create_service_account("module/acme/people")
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        use_call_context,
    )

    with use_call_context(
        CallContext(principal=Principal(account.id, "service_account", account.name))
    ), pytest.raises(PermissionDeniedError):
        iam.exchange_token(
            TokenExchange("ada", TOKEN_TYPE_ID_TOKEN, SESSION_AUDIENCE)
        )
    assert iam.identity_authenticator._identity.calls == []  # never reached the IdP
