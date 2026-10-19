"""The identity domain service: configured providers, verified users (RFC §12.1).

Every operation is authorized with the ``identity`` catalog on the provider it
concerns (``abi:-:-:identity:provider/<name>``), for the caller of the current
``CallContext``. Once a caller is allowed ``identity:Authenticate``, the user is
created or refreshed in IAM as the engine: the caller is authorized for the
sign-in, not for IAM administration.

A user is ``(issuer, sub)``, never an email: the same person signing in
through two providers is two principals, and nothing links them.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote_plus, urlencode, urlsplit, urlunsplit

import jwt

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import FilterResult, PrincipalRecord
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.identity.iam_catalog import SERVICE
from naas_abi_core.services.identity.IdentityPorts import (
    AuthenticatedUser,
    IdentityProvider,
    IIdentityService,
    OIDCHttpPort,
    PrincipalSuspendedError,
    ProviderInfo,
    ProviderMetadata,
    SignIn,
    SignInError,
    TokenRejectedError,
    TokenSet,
    UnknownProviderError,
    VerifiedToken,
)
from naas_abi_core.services.identity.provider_keys import ProviderKeys
from naas_abi_core.services.identity.token_verifier import (
    CLOCK_SKEW_SECONDS,
    TokenVerifier,
)

# A relying party re-verifies its user at the provider at least this often
# (RFC §9.2 and §12.1: no access token lives longer than ten minutes).
MAX_SESSION_TOKEN_SECONDS = 600
# Who writes the user a sign-in resolves: the engine, for the caller whose
# sign-in it authorized.
USER_WRITER = "engine"
# RFC 7636 §4.2: BASE64URL(SHA256(verifier)), 43 characters.
_CODE_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_CODE_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


if TYPE_CHECKING:
    from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
        IdPApp,
    )


class IdentityIAM(Protocol):
    """What identity needs of IAM: the owner, in this process."""

    def require(
        self,
        action: str,
        resource: str,
        *,
        not_found: Callable[[], BaseException] | None = None,
    ) -> None: ...

    def ensure_user(
        self,
        issuer: str,
        subject: str,
        *,
        provider: str | None = None,
        email: str | None = None,
        email_verified: bool = False,
        display_name: str | None = None,
    ) -> PrincipalRecord: ...

    def resolve_idp_groups(
        self, provider: str, claim_values: Iterable[str]
    ) -> list[str]: ...

    def get_principal(self, principal_id: str) -> PrincipalRecord: ...

    def filter(self, action: str, resources: Iterable[str]) -> FilterResult: ...


def provider_resource(name: str) -> str:
    return resource_name(SERVICE, "provider", name)


class IdentityService(IIdentityService):
    def __init__(
        self,
        providers: Sequence[IdentityProvider],
        iam: IdentityIAM,
        http: OIDCHttpPort,
        *,
        default_provider: str | None = None,
        clock_skew_seconds: int = CLOCK_SKEW_SECONDS,
        jwks_cache_seconds: float = 300.0,
        discovery_cache_seconds: float = 3600.0,
        refetch_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        names = [p.name for p in providers]
        if len(set(names)) != len(names):
            raise ValueError("Provider names must be unique")
        issuers = [p.issuer for p in providers]
        if len(set(issuers)) != len(issuers):
            raise ValueError("Two providers cannot share an issuer")
        if default_provider is not None and default_provider not in names:
            raise ValueError(
                f"The default provider {default_provider!r} is not configured"
            )
        self._providers = {p.name: p for p in providers}
        self._iam = iam
        self._http = http
        self._default = default_provider
        self._clock = clock
        self._keys = {
            p.name: ProviderKeys(
                p,
                http,
                jwks_cache_seconds=jwks_cache_seconds,
                discovery_cache_seconds=discovery_cache_seconds,
                refetch_seconds=refetch_seconds,
                clock=clock,
            )
            for p in providers
        }
        self._verifier = TokenVerifier(
            list(self._keys.values()),
            clock_skew_seconds=clock_skew_seconds,
            clock=clock,
        )

    # =========================================================================
    # Providers
    # =========================================================================

    @property
    def default_provider(self) -> str | None:
        return self._default

    def list_providers(self) -> list[ProviderInfo]:
        allowed = set(
            self._iam.filter(
                "identity:ListProviders",
                [provider_resource(name) for name in self._providers],
            ).allowed
        )
        return [
            p.public()
            for name, p in self._providers.items()
            if provider_resource(name) in allowed
        ]

    def get_provider(self, name: str) -> ProviderInfo:
        return self._provider("identity:GetProvider", name).public()

    def metadata(self, name: str) -> ProviderMetadata:
        """The provider's discovery document (needs ``identity:GetProvider``)."""
        self._provider("identity:GetProvider", name)
        return self._keys[name].metadata()

    def attach_builtin_idp(self, app: IdPApp | None) -> bool:
        """Where requests to the built-in IdP go (over NATS, see
        ``OIDCHttpBuiltinIdP``); False when no provider is the built-in one."""
        from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
            OIDCHttpBuiltinIdP,
        )

        if not isinstance(self._http, OIDCHttpBuiltinIdP):
            return False
        self._http.attach(app)
        return True

    def warm_up(self) -> dict[str, str]:
        """Read every provider's discovery document and JWKS, for the boot log:
        provider name to an error, for each that could not be read."""
        failures: dict[str, str] = {}
        for name, keys in self._keys.items():
            try:
                keys.prefetch()
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                failures[name] = str(exc)
        return failures

    # =========================================================================
    # Tokens
    # =========================================================================

    def verify_token(self, token: str, *, nonce: str | None = None) -> VerifiedToken:
        self._authorize_token("identity:VerifyToken", token)
        return self._verifier.verify(token, nonce=nonce)

    def authenticate(
        self, token: str, *, nonce: str | None = None
    ) -> AuthenticatedUser:
        self._authorize_token("identity:Authenticate", token)
        return self._authenticate(self._verifier.verify(token, nonce=nonce))

    def _authenticate(self, verified: VerifiedToken) -> AuthenticatedUser:
        """The verified token's IAM user: created on first sign-in, refused
        when suspended or deleted, with its groups claim mapped."""
        with as_service_account(USER_WRITER):
            record = self._iam.ensure_user(
                verified.issuer,
                verified.subject,
                provider=verified.provider,
                email=verified.email,
                email_verified=verified.email_verified,
                display_name=verified.display_name,
            )
            if record.status != "active":
                raise PrincipalSuspendedError(record.id, record.status)
            groups = (
                self._iam.resolve_idp_groups(verified.provider, verified.groups)
                if verified.groups
                else []
            )
        return AuthenticatedUser(
            principal_id=record.id, token=verified, group_ids=tuple(groups)
        )

    def _authorize_token(self, action: str, token: str) -> IdentityProvider:
        """The provider whose issuer the token names, once the caller may
        ``action`` on it. An unconfigured issuer is refused as such."""
        issuer = _unverified_issuer(token)
        keys = self._verifier.provider_keys(issuer) if issuer else None
        if keys is None:
            raise TokenRejectedError(
                "unknown_issuer", f"No provider is configured for issuer {issuer!r}"
            )
        return self._provider(action, keys.provider.name)

    # =========================================================================
    # A relying party's sign-in (authorization code + PKCE)
    # =========================================================================

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
        configured = self._provider("identity:SignIn", provider)
        if not _CODE_CHALLENGE.match(code_challenge):
            raise ValueError("code_challenge must be an S256 challenge (RFC 7636)")
        if not state or not nonce:
            raise ValueError("A sign-in names a state and a nonce")
        metadata = self._keys[provider].metadata()
        if (
            metadata.code_challenge_methods
            and "S256" not in metadata.code_challenge_methods
        ):
            raise SignInError(
                "unsupported_pkce", f"Provider {provider} does not offer PKCE with S256"
            )
        params = {
            "response_type": "code",
            "client_id": configured.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(configured.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if login_hint:
            params["login_hint"] = login_hint
        if prompt:
            params["prompt"] = prompt
        return _with_query(metadata.authorization_endpoint, params)

    def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> SignIn:
        configured = self._signing_in(provider)
        if not _CODE_VERIFIER.match(code_verifier):
            raise ValueError("code_verifier is not an RFC 7636 verifier")
        tokens = self._token_request(
            configured,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        verified = self._verify_issued(configured, tokens, nonce=nonce)
        return self._sign_in(self._authenticate(verified), tokens)

    def refresh(
        self, provider: str, *, refresh_token: str, principal_id: str
    ) -> SignIn:
        configured = self._signing_in(provider)
        tokens = self._token_request(
            configured,
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        if tokens.refresh_token is None:
            # The provider keeps the refresh token it had issued.
            tokens = replace(tokens, refresh_token=refresh_token)
        if not tokens.id_token:
            # OIDC Core §12.2: a refresh response may omit the ID token. The
            # provider accepted the refresh token and the subject cannot change:
            # what is left to check is IAM's side.
            return self._sign_in(
                self._still_signed_in(configured, principal_id), tokens
            )
        # A refreshed ID token names the same user.
        verified = self._verify_issued(configured, tokens, nonce=None)
        user = self._authenticate(verified)
        if user.principal_id != principal_id:
            raise SignInError(
                "subject_changed", "The refreshed token names another user"
            )
        return self._sign_in(user, tokens)

    def _still_signed_in(
        self, provider: IdentityProvider, principal_id: str
    ) -> AuthenticatedUser:
        """The session's user, with no ID token to read: it must be an active IAM
        user of this provider's issuer. Its groups are not re-read (none came)."""
        with as_service_account(USER_WRITER):
            record = self._iam.get_principal(principal_id)
        if (
            record.kind != "user"
            or record.issuer != provider.issuer
            or record.subject is None
        ):
            raise SignInError(
                "subject_changed", "The session's user does not belong to this provider"
            )
        if record.status != "active":
            raise PrincipalSuspendedError(record.id, record.status)
        now = int(self._clock())
        token = VerifiedToken(
            provider=provider.name,
            issuer=record.issuer,
            subject=record.subject,
            audience=(provider.client_id,),
            issued_at=now,
            expires_at=now + MAX_SESSION_TOKEN_SECONDS,
            email=record.email,
            email_verified=record.email_verified,
            display_name=record.display_name,
        )
        return AuthenticatedUser(principal_id=record.id, token=token)

    def revoke(self, provider: str, *, refresh_token: str) -> bool:
        configured = self._provider("identity:SignIn", provider)
        endpoint = self._keys[provider].metadata().revocation_endpoint
        if not endpoint:
            return False
        status, _ = self._http.post_form(
            endpoint,
            {
                "token": refresh_token,
                "token_type_hint": "refresh_token",
                **self._client_fields(configured),
            },
            basic_auth=self._basic_auth(configured),
        )
        return status == 200

    def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
        state: str | None = None,
    ) -> str | None:
        configured = self._provider("identity:SignIn", provider)
        endpoint = self._keys[provider].metadata().end_session_endpoint
        if not endpoint:
            return None
        params = {"client_id": configured.client_id}
        if id_token_hint:
            params["id_token_hint"] = id_token_hint
        if post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri
        if state:
            params["state"] = state
        return _with_query(endpoint, params)

    # -- helpers ----------------------------------------------------------------

    def _token_request(
        self, provider: IdentityProvider, fields: Mapping[str, str]
    ) -> TokenSet:
        endpoint = self._keys[provider.name].metadata().token_endpoint
        status, body = self._http.post_form(
            endpoint,
            {**fields, **self._client_fields(provider)},
            basic_auth=self._basic_auth(provider),
        )
        if status != 200:
            error = body.get("error") if isinstance(body.get("error"), str) else None
            description = body.get("error_description")
            raise SignInError(
                error or f"http_{status}",
                description if isinstance(description, str) else None,
            )
        return _token_set(body)

    def _verify_issued(
        self, provider: IdentityProvider, tokens: TokenSet, *, nonce: str | None
    ) -> VerifiedToken:
        if not tokens.id_token:
            raise SignInError(
                "no_id_token", f"Provider {provider.name} sent no ID token"
            )
        return self._verifier.verify(
            tokens.id_token, nonce=nonce, provider=provider.name
        )

    def _sign_in(self, user: AuthenticatedUser, tokens: TokenSet) -> SignIn:
        now = int(self._clock())
        refresh_at = min(user.token.expires_at, now + MAX_SESSION_TOKEN_SECONDS)
        return SignIn(user=user, tokens=tokens, refresh_at=refresh_at)

    @staticmethod
    def _client_fields(provider: IdentityProvider) -> dict[str, str]:
        # A confidential client authenticates with HTTP Basic; a public one
        # names itself in the form (RFC 6749 §2.3.1, §3.2.1).
        return {} if provider.client_secret else {"client_id": provider.client_id}

    @staticmethod
    def _basic_auth(provider: IdentityProvider) -> tuple[str, str] | None:
        if not provider.client_secret:
            return None
        # RFC 6749 §2.3.1: both are form-urlencoded before the Basic encoding.
        return (quote_plus(provider.client_id), quote_plus(provider.client_secret))

    def _signing_in(self, name: str) -> IdentityProvider:
        """The provider of a code exchange or a refresh, which resolve (and may
        create) the IAM user: the caller needs ``SignIn`` and ``Authenticate``."""
        configured = self._provider("identity:SignIn", name)
        self._provider("identity:Authenticate", name)
        return configured

    def _provider(self, action: str, name: str) -> IdentityProvider:
        def not_found() -> UnknownProviderError:
            return UnknownProviderError(f"Provider {name!r} not found")

        if not isinstance(name, str) or not _PROVIDER_NAME.match(name):
            raise not_found()
        self._iam.require(action, provider_resource(name), not_found=not_found)
        provider = self._providers.get(name)
        if provider is None:
            raise not_found()
        return provider


# The configured name pattern (EngineConfiguration_Identity).
_PROVIDER_NAME = re.compile(r"^[a-z0-9-]{1,32}$")


def _unverified_issuer(token: str) -> str | None:
    try:
        issuer = jwt.decode(token, options={"verify_signature": False}).get("iss")
    except Exception:  # noqa: BLE001 - verify() reports the malformed token
        raise TokenRejectedError("malformed", "Not a signed JWT") from None
    return issuer if isinstance(issuer, str) else None


def _token_set(body: Mapping[str, object]) -> TokenSet:
    def text(key: str) -> str | None:
        value = body.get(key)
        return value if isinstance(value, str) and value else None

    expires_in = body.get("expires_in")
    if isinstance(expires_in, str) and expires_in.isdigit():
        expires_in = int(expires_in)
    return TokenSet(
        id_token=text("id_token"),
        access_token=text("access_token"),
        refresh_token=text("refresh_token"),
        expires_in=expires_in if isinstance(expires_in, int) else None,
        token_type=text("token_type"),
        scope=text("scope"),
    )


def _with_query(url: str, params: Mapping[str, str]) -> str:
    parts = urlsplit(url)
    query = urlencode(params)
    return urlunsplit(
        parts._replace(query=f"{parts.query}&{query}" if parts.query else query)
    )
