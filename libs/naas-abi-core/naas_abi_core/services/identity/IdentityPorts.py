"""Identity: users from OIDC identity providers (RFC 20261013 §12.1).

The engine is not an identity provider. It trusts the providers configured
under ``identity.providers``, verifies their tokens against each issuer's
discovery document and JWKS, and resolves a verified ``(issuer, sub)`` to an
IAM user principal, created on first sign-in.

It also runs the provider side of an OIDC client's sign-in (authorization code
with PKCE, refresh, revocation) for a relying party such as Nexus: the client
secret stays in the engine, and the relying party only holds the browser's
state, nonce and code verifier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Provisioning = Literal["builtin", "zitadel", "keycloak", "none"]

# Token signing algorithms a provider may use. Never "none", never HMAC: a
# verifier holds no shared secret with an IdP.
ALLOWED_ALGORITHMS: tuple[str, ...] = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)


# =============================================================================
# Records
# =============================================================================


@dataclass(frozen=True)
class IdentityProvider:
    """A configured provider (``identity.providers[]``)."""

    name: str
    issuer: str
    client_id: str
    client_secret: str | None = field(default=None, repr=False)
    groups_claim: str | None = None
    scopes: tuple[str, ...] = ("openid", "email", "profile")
    provisioning: Provisioning = "none"
    display_name: str | None = None

    def public(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            issuer=self.issuer,
            client_id=self.client_id,
            display_name=self.display_name or self.name,
            scopes=self.scopes,
            groups_claim=self.groups_claim,
            provisioning=self.provisioning,
        )


@dataclass(frozen=True)
class ProviderInfo:
    """What anyone may learn about a provider: never its client secret."""

    name: str
    issuer: str
    client_id: str
    display_name: str
    scopes: tuple[str, ...]
    groups_claim: str | None
    provisioning: Provisioning


@dataclass(frozen=True)
class ProviderMetadata:
    """The parts of a provider's discovery document the engine uses."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None = None
    revocation_endpoint: str | None = None
    end_session_endpoint: str | None = None
    signing_algorithms: tuple[str, ...] = ("RS256",)
    code_challenge_methods: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedToken:
    """A token whose signature, issuer, audience and lifetime checked out.

    ``groups`` are the raw values of the provider's groups claim, before IAM
    maps them to group ids.
    """

    provider: str
    issuer: str
    subject: str
    audience: tuple[str, ...]
    issued_at: int
    expires_at: int
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = None
    groups: tuple[str, ...] = ()
    nonce: str | None = None
    session_id: str | None = None
    claims: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """A verified token resolved to its IAM user."""

    principal_id: str
    token: VerifiedToken
    # IAM group ids the token's groups claim maps to (the engine token's grp).
    group_ids: tuple[str, ...] = ()

    @property
    def provider(self) -> str:
        return self.token.provider

    @property
    def issuer(self) -> str:
        return self.token.issuer

    @property
    def subject(self) -> str:
        return self.token.subject


@dataclass(frozen=True)
class TokenSet:
    """What a provider's token endpoint answered."""

    id_token: str | None
    access_token: str | None = field(default=None, repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_in: int | None = None
    token_type: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class SignIn:
    """A completed code exchange or refresh: the user and the provider's tokens.

    The relying party keeps the refresh token server-side; the access token
    and ID token never reach the browser.
    """

    user: AuthenticatedUser
    tokens: TokenSet = field(repr=False)
    # When the relying party must refresh at the latest: the ID token's
    # expiry, never more than ten minutes after it was verified (RFC §12.1).
    refresh_at: int = 0


@dataclass(frozen=True)
class HttpJSON:
    """A JSON body and how long it may be cached (``Cache-Control: max-age``)."""

    body: Mapping[str, Any]
    max_age: float | None = None


# =============================================================================
# Errors
# =============================================================================


class IdentityError(Exception):
    """Base of the identity errors; ``code`` travels on the wire."""

    code = "IDENTITY_ERROR"


class UnknownProviderError(IdentityError):
    code = "NOT_FOUND"


class ProviderUnavailableError(IdentityError):
    """The provider's discovery document, JWKS or token endpoint could not be read."""

    code = "UNAVAILABLE"


class TokenRejectedError(IdentityError):
    """A token that is not accepted. ``reason`` names the check that failed:

    ``malformed``, ``unknown_issuer``, ``unknown_key``, ``invalid_signature``,
    ``wrong_audience``, ``expired``, ``not_yet_valid``, ``nonce_mismatch``,
    ``missing_claim``, ``algorithm``.
    """

    code = "UNAUTHENTICATED"

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or reason)


class SignInError(IdentityError):
    """The provider refused a code exchange or a refresh (``invalid_grant``...)."""

    code = "SIGN_IN_FAILED"

    def __init__(self, error: str, description: str | None = None) -> None:
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}" if description else error)


class PrincipalSuspendedError(IdentityError):
    """The token is valid, but IAM has suspended or deleted its user."""

    code = "SUSPENDED"

    def __init__(self, principal_id: str, status: str) -> None:
        self.principal_id = principal_id
        self.status = status
        super().__init__(f"Principal {principal_id} is {status}")


# =============================================================================
# Ports
# =============================================================================


class OIDCHttpPort(ABC):
    """How the engine talks to providers over HTTP (secondary)."""

    @abstractmethod
    def get_json(self, url: str) -> HttpJSON:
        """GET a JSON document; ``ProviderUnavailableError`` when it cannot."""

    @abstractmethod
    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        basic_auth: tuple[str, str] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        """POST a form; the status and the JSON body (``{}`` when there is none).

        ``ProviderUnavailableError`` when the endpoint cannot be reached.
        """


class IIdentityService(ABC):
    """What callers use: in process, or over NATS (``abi.identity.v1.*``).

    Every operation is authorized with the ``identity`` catalog
    (``iam_catalog.py``) on ``abi:-:-:identity:provider/<name>``.
    """

    @abstractmethod
    def list_providers(self) -> list[ProviderInfo]:
        """The configured providers the caller may see."""

    @abstractmethod
    def get_provider(self, name: str) -> ProviderInfo:
        """One provider, else ``UnknownProviderError``."""

    @property
    @abstractmethod
    def default_provider(self) -> str | None:
        """The provider a login with no routed domain goes to."""

    @abstractmethod
    def verify_token(self, token: str, *, nonce: str | None = None) -> VerifiedToken:
        """Verify an ID token from a configured provider. No IAM side effect."""

    @abstractmethod
    def authenticate(
        self, token: str, *, nonce: str | None = None
    ) -> AuthenticatedUser:
        """Verify an ID token and resolve its user: created on first sign-in,
        its groups claim mapped, refused when suspended."""

    @abstractmethod
    def authorization_url(
        self,
        provider: str,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str,
        login_hint: str | None = None,
        prompt: str | None = None,
    ) -> str:
        """The provider's authorization URL for a code + PKCE (S256) request."""

    @abstractmethod
    def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> SignIn:
        """Redeem an authorization code, then ``authenticate`` its ID token."""

    @abstractmethod
    def refresh(
        self, provider: str, *, refresh_token: str, principal_id: str
    ) -> SignIn:
        """Refresh at the provider and re-authenticate: the same user, still
        active, with its groups as the provider now states them."""

    @abstractmethod
    def revoke(self, provider: str, *, refresh_token: str) -> bool:
        """Revoke a refresh token at the provider, when it offers revocation."""

    @abstractmethod
    def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
        state: str | None = None,
    ) -> str | None:
        """The provider's RP-initiated logout URL, when it offers one."""


def claim_values(value: Any) -> tuple[str, ...]:
    """A groups claim as a tuple of strings.

    Providers send a list of strings (Okta, Keycloak, Entra), one string, or an
    object whose keys are the values (Zitadel's project roles claim).
    """
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Mapping):
        return tuple(sorted(str(k) for k in value if str(k)))
    if isinstance(value, Sequence):
        return tuple(str(v) for v in value if isinstance(v, (str, int)) and str(v))
    return ()
