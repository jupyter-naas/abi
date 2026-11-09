"""The generic identity suite: what any OIDC provider must pass for ABI.

It covers discovery, the JWKS and key rotation, token verification (issuer,
audience, lifetime, signature, nonce), groups, suspension and a full
authorization code + PKCE sign-in with refresh and revocation, all through
``IdentityService`` and real HTTP.

A provider plugs in with an ``IdentityProviderHarness``: subclass
``IdentityProviderContract`` and give it a ``harness`` fixture.

```python
class TestMyIdP(IdentityProviderContract):
    @pytest.fixture(scope="class")
    def harness(self):
        with MyIdPHarness() as idp:
            yield idp
```

It runs against the in-process ``FakeIdP`` on every test run, against Zitadel
(``zitadel_server.py``) when its pinned binaries are available, and against
the built-in IdP.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest

from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.identity.adapters.secondary.OIDCHttpHttpx import (
    OIDCHttpHttpx,
)
from naas_abi_core.services.identity.iam_catalog import CATALOG
from naas_abi_core.services.identity.IdentityPorts import (
    IdentityProvider,
    PrincipalSuspendedError,
    SignIn,
    SignInError,
    TokenRejectedError,
    UnknownProviderError,
)
from naas_abi_core.services.identity.IdentityService import IdentityService

# The caller of the suite's operations: Nexus, the relying party.
CALLER = "api"


@dataclass(frozen=True)
class TestUser:
    """A user the harness created at its provider."""

    __test__ = False  # not a pytest class

    subject: str
    email: str
    login: str
    password: str | None = None


class IdentityProviderHarness(Protocol):
    """A provider under test, and a way to drive its sign-in without a browser."""

    provider_name: str
    issuer: str
    client_id: str
    client_secret: str | None
    redirect_uri: str
    groups_claim: str | None
    scopes: tuple[str, ...]

    def create_user(self, email: str, *, groups: Sequence[str] = ()) -> TestUser:
        """A new user, member of ``groups`` as the groups claim names them."""

    def sign_in(self, authorization_url: str, user: TestUser) -> str:
        """Follow an authorization URL as ``user`` and return the redirect to
        ``redirect_uri`` (with ``code`` and ``state``)."""

    def rotate_signing_key(self) -> None:
        """Publish a new signing key and sign with it from now on."""

    def other_client(self) -> tuple[str, str | None]:
        """Another client of the same issuer, allowed the same redirect URI."""


def provider_of(
    harness: IdentityProviderHarness,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> IdentityProvider:
    return IdentityProvider(
        name=harness.provider_name,
        issuer=harness.issuer,
        client_id=client_id or harness.client_id,
        client_secret=client_secret if client_id else harness.client_secret,
        groups_claim=harness.groups_claim,
        scopes=harness.scopes,
    )


def bootstrapped_iam() -> IAMService:
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with as_service_account("engine"):
        iam.register_catalog(CATALOG)
    return iam


def identity_service(
    harness: IdentityProviderHarness,
    iam: IAMService,
    *,
    providers: Sequence[IdentityProvider] | None = None,
    clock: Callable[[], float] = time.time,
) -> IdentityService:
    return IdentityService(
        list(providers) if providers is not None else [provider_of(harness)],
        iam,
        OIDCHttpHttpx(),
        default_provider=None,
        refetch_seconds=0.0,
        clock=clock,
    )


@dataclass(frozen=True)
class Pkce:
    verifier: str
    challenge: str
    state: str
    nonce: str

    @classmethod
    def new(cls) -> Pkce:
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        return cls(
            verifier, challenge, secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        )


def sign_in(
    service: IdentityService,
    harness: IdentityProviderHarness,
    user: TestUser,
    *,
    provider: str | None = None,
) -> SignIn:
    """A full authorization code + PKCE sign-in, as the relying party runs it."""
    name = provider or harness.provider_name
    pkce = Pkce.new()
    with as_service_account(CALLER):
        url = service.authorization_url(
            name,
            redirect_uri=harness.redirect_uri,
            state=pkce.state,
            nonce=pkce.nonce,
            code_challenge=pkce.challenge,
            login_hint=user.login,
        )
    callback = harness.sign_in(url, user)
    query = parse_qs(urlsplit(callback).query)
    assert query["state"] == [pkce.state]
    with as_service_account(CALLER):
        return service.exchange_code(
            name,
            code=query["code"][0],
            code_verifier=pkce.verifier,
            redirect_uri=harness.redirect_uri,
            nonce=pkce.nonce,
        )


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}@example.com"


class IdentityProviderContract:
    """The suite. Subclasses give it a ``harness`` fixture."""

    @pytest.fixture
    def iam(self) -> IAMService:
        return bootstrapped_iam()

    @pytest.fixture
    def service(self, harness, iam) -> IdentityService:
        return identity_service(harness, iam)

    # -- discovery and keys -----------------------------------------------------

    def test_discovery_names_the_issuer_and_its_endpoints(self, harness, service):
        with as_service_account(CALLER):
            metadata = service.metadata(harness.provider_name)
        assert metadata.issuer == harness.issuer
        assert metadata.authorization_endpoint and metadata.token_endpoint
        assert metadata.jwks_uri
        if metadata.code_challenge_methods:
            assert "S256" in metadata.code_challenge_methods

    def test_the_jwks_publishes_signing_keys(self, harness):
        from naas_abi_core.services.identity.provider_keys import ProviderKeys

        keys = ProviderKeys(provider_of(harness), OIDCHttpHttpx())
        keys.prefetch()
        assert keys.known_key_ids()

    # -- a full sign-in ---------------------------------------------------------

    def test_a_pkce_sign_in_yields_the_user_keyed_by_issuer_and_subject(
        self, harness, service, iam
    ):
        user = harness.create_user(_unique_email("alice"))
        signed_in = sign_in(service, harness, user)
        assert signed_in.user.subject == user.subject
        assert signed_in.user.issuer == harness.issuer
        record = iam.store.find_user(harness.issuer, user.subject)
        assert record is not None and record.id == signed_in.user.principal_id
        assert record.provider == harness.provider_name
        assert record.email == user.email
        # A relying party re-verifies at the provider within ten minutes.
        assert signed_in.refresh_at <= int(time.time()) + 600
        assert signed_in.tokens.refresh_token

    def test_the_same_identity_is_the_same_principal(self, harness, service):
        user = harness.create_user(_unique_email("bob"))
        first = sign_in(service, harness, user)
        second = sign_in(service, harness, user)
        assert first.user.principal_id == second.user.principal_id

    def test_a_refresh_at_the_provider_names_the_same_user(self, harness, service):
        user = harness.create_user(_unique_email("carol"))
        signed_in = sign_in(service, harness, user)
        assert signed_in.tokens.refresh_token
        with as_service_account(CALLER):
            refreshed = service.refresh(
                harness.provider_name,
                refresh_token=signed_in.tokens.refresh_token,
                principal_id=signed_in.user.principal_id,
            )
        assert refreshed.user.principal_id == signed_in.user.principal_id
        assert refreshed.tokens.refresh_token

    def test_a_revoked_refresh_token_no_longer_refreshes(self, harness, service):
        user = harness.create_user(_unique_email("dave"))
        signed_in = sign_in(service, harness, user)
        token = signed_in.tokens.refresh_token
        assert token
        with as_service_account(CALLER):
            if not service.revoke(harness.provider_name, refresh_token=token):
                pytest.skip("the provider offers no revocation")
            with pytest.raises(SignInError):
                service.refresh(
                    harness.provider_name,
                    refresh_token=token,
                    principal_id=signed_in.user.principal_id,
                )

    def test_a_code_needs_its_pkce_verifier(self, harness, service):
        user = harness.create_user(_unique_email("erin"))
        pkce = Pkce.new()
        with as_service_account(CALLER):
            url = service.authorization_url(
                harness.provider_name,
                redirect_uri=harness.redirect_uri,
                state=pkce.state,
                nonce=pkce.nonce,
                code_challenge=pkce.challenge,
            )
        code = parse_qs(urlsplit(harness.sign_in(url, user)).query)["code"][0]
        with as_service_account(CALLER), pytest.raises(SignInError):
            service.exchange_code(
                harness.provider_name,
                code=code,
                code_verifier=Pkce.new().verifier,
                redirect_uri=harness.redirect_uri,
                nonce=pkce.nonce,
            )

    # -- verification -----------------------------------------------------------

    def test_a_token_from_an_unconfigured_issuer_is_refused(
        self, harness, service, iam
    ):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("f")))
        unconfigured = identity_service(harness, iam, providers=[])
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            unconfigured.authenticate(signed_in.tokens.id_token or "")
        assert refused.value.reason == "unknown_issuer"

    def test_a_token_for_another_client_is_refused(self, harness, service, iam):
        client_id, secret = harness.other_client()
        other = identity_service(
            harness,
            iam,
            providers=[provider_of(harness, client_id=client_id, client_secret=secret)],
        )
        signed_in = sign_in(other, harness, harness.create_user(_unique_email("g")))
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            service.authenticate(signed_in.tokens.id_token or "")
        assert refused.value.reason == "wrong_audience"

    def test_an_expired_token_is_refused(self, harness, service, iam):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("h")))
        token = signed_in.tokens.id_token or ""
        later = signed_in.user.token.expires_at + 31
        expired = identity_service(harness, iam, clock=lambda: float(later))
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            expired.verify_token(token)
        assert refused.value.reason == "expired"

    def test_a_token_not_valid_yet_is_refused(self, harness, service, iam):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("i")))
        earlier = signed_in.user.token.issued_at - 120
        early = identity_service(harness, iam, clock=lambda: float(earlier))
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            early.verify_token(signed_in.tokens.id_token or "")
        assert refused.value.reason == "not_yet_valid"

    def test_a_tampered_token_is_refused(self, harness, service):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("j")))
        header, _payload, signature = (signed_in.tokens.id_token or "").split(".")
        claims = jwt.decode(
            signed_in.tokens.id_token or "", options={"verify_signature": False}
        )
        claims["sub"] = "someone-else"
        forged_payload = (
            base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        )
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            service.verify_token(f"{header}.{forged_payload}.{signature}")
        assert refused.value.reason == "invalid_signature"

    def test_a_nonce_must_match(self, harness, service):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("k")))
        with as_service_account(CALLER), pytest.raises(TokenRejectedError) as refused:
            service.verify_token(signed_in.tokens.id_token or "", nonce="another")
        assert refused.value.reason == "nonce_mismatch"

    def test_a_caller_with_no_policy_cannot_authenticate(self, harness, service):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("l")))
        with use_call_context(ANONYMOUS), pytest.raises(UnknownProviderError):
            service.authenticate(signed_in.tokens.id_token or "")

    # -- keys rotate --------------------------------------------------------------

    def test_key_rotation_is_followed(self, harness, service):
        before = sign_in(service, harness, harness.create_user(_unique_email("m")))
        old_kid = jwt.get_unverified_header(before.tokens.id_token or "").get("kid")
        harness.rotate_signing_key()
        after = sign_in(service, harness, harness.create_user(_unique_email("n")))
        new_kid = jwt.get_unverified_header(after.tokens.id_token or "").get("kid")
        assert new_kid != old_kid
        with as_service_account(CALLER):
            # Both verify: the old key stays published while its tokens live.
            assert service.verify_token(after.tokens.id_token or "").subject
            assert service.verify_token(before.tokens.id_token or "").subject

    # -- groups and suspension --------------------------------------------------

    def test_the_groups_claim_maps_to_iam_groups(self, harness, service, iam):
        if not harness.groups_claim:
            pytest.skip("the provider sends no groups claim")
        claim_value = f"readers-{secrets.token_hex(3)}"
        with as_service_account("engine"):
            group = iam.create_group("Data readers")
            iam.map_idp_group(harness.provider_name, claim_value, group.id)
        user = harness.create_user(_unique_email("o"), groups=[claim_value])
        signed_in = sign_in(service, harness, user)
        assert claim_value in signed_in.user.token.groups
        assert signed_in.user.group_ids == (group.id,)

    def test_a_suspended_principal_is_refused(self, harness, service, iam):
        signed_in = sign_in(service, harness, harness.create_user(_unique_email("p")))
        with as_service_account("engine"):
            iam.suspend_principal(signed_in.user.principal_id)
        with as_service_account(CALLER):
            with pytest.raises(PrincipalSuspendedError):
                service.authenticate(signed_in.tokens.id_token or "")
            with pytest.raises(PrincipalSuspendedError):
                service.refresh(
                    harness.provider_name,
                    refresh_token=signed_in.tokens.refresh_token or "",
                    principal_id=signed_in.user.principal_id,
                )
