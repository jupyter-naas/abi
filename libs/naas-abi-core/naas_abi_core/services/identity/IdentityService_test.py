"""``IdentityService`` behaviours the generic suite leaves to the in-process provider:
what a caller needs for a sign-in, a refresh that sends no ID token, the client
credentials on the wire and how long a provider's documents are cached."""

from __future__ import annotations

import secrets
from urllib.parse import parse_qs, urlsplit

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, statement
from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
    OIDCHttpHttpx,
)
from naas_abi_core.services.identity.IdentityPorts import (
    PrincipalSuspendedError,
    SignInError,
)
from naas_abi_core.services.identity.IdentityService import IdentityService
from naas_abi_core.services.identity.provider_keys import ProviderKeys
from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    CALLER,
    Pkce,
    bootstrapped_iam,
    identity_service,
    provider_of,
    sign_in,
)


@pytest.fixture
def idp():
    with FakeIdP() as provider:
        yield provider


@pytest.fixture
def iam() -> IAMService:
    return bootstrapped_iam()


@pytest.fixture
def service(idp, iam) -> IdentityService:
    return identity_service(idp, iam)


def _email(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3)}@example.com"


def _caller_allowed(iam: IAMService, name: str, *actions: str) -> str:
    """A service account that may do ``actions`` on every provider, and no more."""
    with as_service_account("engine"):
        account = iam.create_service_account(name)
        policy = iam.create_policy(
            f"{name}-identity",
            document(
                statement("Allow", list(actions), ["abi:-:-:identity:provider/*"])
            ),
        )
        iam.attach_policy(policy.id, account.id)
    return name


def _authorization(service: IdentityService, idp: FakeIdP, user) -> tuple[Pkce, str]:
    pkce = Pkce.new()
    with as_service_account(CALLER):
        url = service.authorization_url(
            idp.provider_name,
            redirect_uri=idp.redirect_uri,
            state=pkce.state,
            nonce=pkce.nonce,
            code_challenge=pkce.challenge,
        )
    return pkce, parse_qs(urlsplit(idp.sign_in(url, user)).query)["code"][0]


# -- who may complete a sign-in -------------------------------------------------


def test_a_caller_with_only_sign_in_cannot_create_users(idp, service, iam):
    caller = _caller_allowed(
        iam, "module/acme/relying-party", "identity:SignIn", "identity:GetProvider"
    )
    user = idp.create_user(_email("sia"))
    pkce, code = _authorization(service, idp, user)
    with as_service_account(caller), pytest.raises(PermissionDeniedError):
        service.exchange_code(
            idp.provider_name,
            code=code,
            code_verifier=pkce.verifier,
            redirect_uri=idp.redirect_uri,
            nonce=pkce.nonce,
        )
    # The code was never redeemed, and IAM never saw the user.
    assert iam.store.find_user(idp.issuer, user.subject) is None
    assert idp.token_requests == []


def test_a_caller_with_only_sign_in_cannot_refresh(idp, service, iam):
    signed_in = sign_in(service, idp, idp.create_user(_email("sib")))
    caller = _caller_allowed(
        iam, "module/acme/relying-party", "identity:SignIn", "identity:GetProvider"
    )
    before = len(idp.token_requests)
    with as_service_account(caller), pytest.raises(PermissionDeniedError):
        service.refresh(
            idp.provider_name,
            refresh_token=signed_in.tokens.refresh_token or "",
            principal_id=signed_in.user.principal_id,
        )
    assert len(idp.token_requests) == before


def test_a_caller_with_both_actions_signs_in(idp, service, iam):
    caller = _caller_allowed(
        iam,
        "module/acme/relying-party",
        "identity:SignIn",
        "identity:Authenticate",
        "identity:GetProvider",
    )
    user = idp.create_user(_email("sic"))
    pkce, code = _authorization(service, idp, user)
    with as_service_account(caller):
        signed_in = service.exchange_code(
            idp.provider_name,
            code=code,
            code_verifier=pkce.verifier,
            redirect_uri=idp.redirect_uri,
            nonce=pkce.nonce,
        )
    assert (
        iam.store.find_user(idp.issuer, user.subject).id == signed_in.user.principal_id
    )


# -- a refresh that sends no ID token ----------------------------------------------


def test_a_refresh_without_an_id_token_keeps_the_user(idp, service):
    signed_in = sign_in(service, idp, idp.create_user(_email("rfa")))
    idp.refresh_returns_id_token = False
    with as_service_account(CALLER):
        refreshed = service.refresh(
            idp.provider_name,
            refresh_token=signed_in.tokens.refresh_token or "",
            principal_id=signed_in.user.principal_id,
        )
    assert refreshed.tokens.id_token is None
    assert refreshed.user.principal_id == signed_in.user.principal_id
    assert refreshed.user.subject == signed_in.user.subject
    assert refreshed.tokens.refresh_token  # the provider's new one
    assert refreshed.refresh_at <= signed_in.refresh_at + 600


def test_a_refresh_without_an_id_token_still_refuses_a_suspended_user(
    idp, service, iam
):
    signed_in = sign_in(service, idp, idp.create_user(_email("rfb")))
    idp.refresh_returns_id_token = False
    with as_service_account("engine"):
        iam.suspend_principal(signed_in.user.principal_id)
    with as_service_account(CALLER), pytest.raises(PrincipalSuspendedError):
        service.refresh(
            idp.provider_name,
            refresh_token=signed_in.tokens.refresh_token or "",
            principal_id=signed_in.user.principal_id,
        )


def test_a_refresh_without_an_id_token_refuses_another_providers_user(
    idp, service, iam
):
    signed_in = sign_in(service, idp, idp.create_user(_email("rfc")))
    idp.refresh_returns_id_token = False
    with as_service_account("engine"):
        stranger = iam.ensure_user("https://elsewhere.example", "someone")
    with as_service_account(CALLER), pytest.raises(SignInError) as refused:
        service.refresh(
            idp.provider_name,
            refresh_token=signed_in.tokens.refresh_token or "",
            principal_id=stranger.id,
        )
    assert refused.value.error == "subject_changed"


# -- client credentials -------------------------------------------------------------


def test_client_credentials_are_urlencoded_before_basic_encoding(idp, iam):
    # RFC 6749 §2.3.1: a secret holding "+", "%", ":" or "&" must survive.
    client_id, secret = idp.add_client(idp.redirect_uri, secret="s3+cr%t:with&all ;")
    service = identity_service(
        idp,
        iam,
        providers=[provider_of(idp, client_id=client_id, client_secret=secret)],
    )
    signed_in = sign_in(service, idp, idp.create_user(_email("cra")))
    assert signed_in.tokens.refresh_token
    with as_service_account(CALLER):
        refreshed = service.refresh(
            idp.provider_name,
            refresh_token=signed_in.tokens.refresh_token,
            principal_id=signed_in.user.principal_id,
        )
        assert service.revoke(
            idp.provider_name, refresh_token=refreshed.tokens.refresh_token or ""
        )


# -- caching ----------------------------------------------------------------------


@pytest.mark.parametrize("directive", ["no-store", "no-cache", "max-age=0"])
def test_a_jwks_the_provider_forbids_caching_is_read_again(idp, directive):
    idp.jwks_cache_control = directive
    keys = ProviderKeys(provider_of(idp), OIDCHttpHttpx())
    keys.prefetch()
    reads = idp.jwks_reads
    keys.prefetch()
    assert idp.jwks_reads == reads + 1


def test_a_jwks_without_a_lifetime_gets_the_default_one(idp):
    idp.jwks_cache_control = "public"
    keys = ProviderKeys(provider_of(idp), OIDCHttpHttpx(), jwks_cache_seconds=300.0)
    keys.prefetch()
    reads = idp.jwks_reads
    keys.prefetch()
    assert idp.jwks_reads == reads


def test_a_jwks_is_cached_for_its_max_age(idp):
    keys = ProviderKeys(provider_of(idp), OIDCHttpHttpx())
    keys.prefetch()
    reads = idp.jwks_reads
    keys.prefetch()
    assert idp.jwks_reads == reads
