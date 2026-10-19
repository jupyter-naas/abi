"""Who a request is, from the credential it presents (RFC §9.3).

Every credential has a *kind*, its audience, and the Nexus API honours a kind
only where it belongs:

| Kind      | Credential                                                        | Accepted by                                  |
|-----------|-------------------------------------------------------------------|----------------------------------------------|
| session   | a Nexus session: the cookie of an identity-provider login, a      | every route and the WebSocket                |
|           | session token (``abi:session``)                                   |                                              |
| api-key   | a personal API key (``abi_pk_``) or the ``abi:delegated:api-key`` | ``/api/*`` but the session-only routes       |
|           | token it is exchanged for                                         |                                              |
| coding    | a coding environment's key or its ``abi:delegated:coding`` token  | the OpenAI gateway, ``/api/v1/*``            |

Everything else is refused here: an app-html link, a preview link, a remote app
grant (they open their own routes, ``apps/links.py``), an agent delegation (it
is for the kernel and the module hosts). None of them is a session: the browser
or an app's JavaScript can read them, a coding agent runs in a container.
``is_session_token`` and ``decode_token`` (``service.py``) know the one kind
Nexus signs itself, until the login code leaves Nexus (#67).

A session-only route is one that must never be reached with a key: the account
(``/api/auth/*``), the IAM administration and the API-key management
(``/api/iam/*``).
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import jwt
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account, current_call_context
from naas_abi_core.engine.nats_auth import (
    API_KEY_AUDIENCE,
    CODING_AUDIENCE,
    PERSONAL_KEY_PREFIX,
    SESSION_AUDIENCE,
    InvalidServiceTokenError,
    JWKSVerifier,
    TokenClaims,
)
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_API_KEY,
    KeyRefusedError,
    PermissionDeniedError,
    TokenExchange,
)

CredentialKind = Literal["session", "api-key", "coding"]
SESSION: CredentialKind = "session"
API_KEY: CredentialKind = "api-key"
CODING: CredentialKind = "coding"

_KIND_OF_AUDIENCE: dict[str, CredentialKind] = {
    SESSION_AUDIENCE: SESSION,
    API_KEY_AUDIENCE: API_KEY,
    CODING_AUDIENCE: CODING,
}
# The routes that take no key at all: the account, and the credentials' own
# administration.
SESSION_ONLY_PREFIXES = ("/api/auth/", "/api/iam/")
GATEWAY_PREFIX = "/api/v1/"
API_PREFIX = "/api/"


def accepted_kinds(path: str) -> frozenset[CredentialKind]:
    """The kinds of credential the route at ``path`` accepts."""
    if path.startswith(GATEWAY_PREFIX):
        return frozenset({SESSION, API_KEY, CODING})
    if path.startswith(SESSION_ONLY_PREFIXES):
        return frozenset({SESSION})
    if path.startswith(API_PREFIX):
        return frozenset({SESSION, API_KEY})
    return frozenset({SESSION})


@dataclass(frozen=True)
class Credential:
    """A verified credential: whose it is and how far it reaches."""

    kind: CredentialKind
    user_id: str
    groups: frozenset[str] = frozenset()
    # The token's ``abi_scope``: a list of Allow statements that narrows what
    # the user may do through it (None: not narrowed).
    scope: tuple[dict[str, Any], ...] | None = None
    # What it is bound to: a coding environment's sidecar.
    resource: str | None = None
    token_id: str | None = None
    # The engine's ``Credential`` of a cookie session, for the CSRF rule.
    session: Any = field(default=None, compare=False, repr=False)


# -- the engine's IAM ---------------------------------------------------------------------------


def _default_iam() -> Any | None:
    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
        default_iam,
    )

    return default_iam()


IAM: Callable[[], Any | None] = _default_iam


def configure_iam(provider: Callable[[], Any | None]) -> Callable[[], Any | None]:
    """Replace where the engine's IAM comes from (tests); returns the previous."""
    global IAM
    previous, IAM = IAM, provider
    return previous


_verifiers: weakref.WeakKeyDictionary[Any, JWKSVerifier] = weakref.WeakKeyDictionary()


def _verifier(iam: Any) -> JWKSVerifier:
    """One verifier per IAM (it caches the JWKS), for the audiences this API
    reads and no other: an agent, app or preview token is not one of them."""
    verifier = _verifiers.get(iam)
    if verifier is None:
        verifier = JWKSVerifier(
            iam.jwks,
            audiences=tuple(_KIND_OF_AUDIENCE),
            revoked=getattr(iam, "token_revoked", None),
        )
        _verifiers[iam] = verifier
    return verifier


def refuse_a_limited_credential(what: str) -> None:
    """A request that came with a credential narrowed to something (a key with a
    scope) may not ``what``: a credential made here has a reach of its own (a
    link, a coding agent's key), and would be wider than the one that asked."""
    if current_call_context().scope is not None:
        raise PermissionDeniedError(message=f"A credential with a limit cannot {what}")


def session_allowed_by_iam(user_id: str, issued_at: Any) -> bool:
    """What the engine's IAM says about a session Nexus signed: it was issued
    after the last revocation of its user's tokens, and the user is not
    suspended. For the places that read a session token outside the API's
    bearer check (``/app-html/``); blocking, so called from a thread."""
    iam = IAM()
    if iam is None:
        return True
    revoked_since = getattr(iam, "revoked_since", None)
    if (
        revoked_since is not None
        and isinstance(issued_at, int | float)
        and revoked_since(user_id, int(issued_at))
    ):
        return False
    return _active(iam, user_id)


def _active(iam: Any, user_id: str) -> bool:
    """False for a user IAM knows and has suspended or deleted. A user it has no
    record of (a Nexus user of the built-in login) is not suspended."""
    resolve = getattr(iam, "resolve_user", None)
    if resolve is None:
        return True
    record = resolve(user_id)
    return record is None or record.active


# -- bearer tokens ------------------------------------------------------------------------------


async def bearer_credential(
    token: str,
    *,
    decode: Callable[[str], dict | None] | None = None,
    is_revoked: Callable[[str], Awaitable[bool]] | None = None,
) -> Credential | None:
    """The credential a bearer token is, or None: unknown, expired, revoked,
    suspended, or a kind this API does not read at all. Fails closed.

    ``decode`` and ``is_revoked`` are Nexus's own session-token functions, by
    default those of ``service.py`` and ``refresh_token``."""
    token = token.strip()
    if not token:
        return None
    try:
        if token.startswith(PERSONAL_KEY_PREFIX):
            return await asyncio.to_thread(_key_credential, token)
        if _is_engine_token(token):
            return await asyncio.to_thread(_engine_credential, token)
        return await _session_credential(token, decode, is_revoked)
    except Exception as exc:  # noqa: BLE001 - fail closed
        logger.warning(f"A credential could not be checked; it names no user: {exc}")
        return None


def _is_engine_token(token: str) -> bool:
    try:
        return jwt.get_unverified_header(token).get("alg") == "ES256"
    except jwt.InvalidTokenError:
        return False


def _credential_of(claims: TokenClaims) -> Credential | None:
    kind = _KIND_OF_AUDIENCE.get(claims.audience)
    if kind is None or claims.actor is not None or claims.kind != "user":
        return None  # a delegation (acting for someone) is not a user's own
    return Credential(
        kind=kind,
        user_id=claims.subject,
        groups=frozenset(claims.groups),
        scope=tuple(dict(s) for s in claims.scope) if claims.scope is not None else None,
        resource=claims.resource,
        token_id=claims.token_id,
    )


def _engine_credential(token: str) -> Credential | None:
    iam = IAM()
    if iam is None:
        return None
    try:
        claims = _verifier(iam).verify(token)
    except InvalidServiceTokenError:
        return None
    credential = _credential_of(claims)
    if credential is None or not _active(iam, credential.user_id):
        return None
    return credential


def _key_credential(value: str) -> Credential | None:
    """A personal API key presented as the bearer: exchanged for the token of
    its own audience on every request (IAM checks its hash, expiry, revocation
    and owner), so revoking it takes effect on the next request."""
    iam = IAM()
    if iam is None:
        return None
    try:
        # No audience named: the key's own (an API key's, or a coding agent's),
        # so the key is authenticated once whichever it is.
        with as_service_account("api"):
            issued = iam.exchange_token(
                TokenExchange(
                    subject_token=value,
                    subject_token_type=TOKEN_TYPE_API_KEY,
                    audience="",
                )
            )
    except KeyRefusedError:
        return None
    try:
        claims = _verifier(iam).verify(issued.token)
    except InvalidServiceTokenError:
        return None
    return _credential_of(claims)


async def _session_credential(
    token: str,
    decode: Callable[[str], dict | None] | None,
    is_revoked: Callable[[str], Awaitable[bool]] | None,
) -> Credential | None:
    """A session token Nexus signed itself: the audience ``abi:session`` and no
    scope, not revoked, issued after the last revocation of its user's tokens."""
    from naas_abi.apps.nexus.apps.api.app.services.auth import service

    payload = (decode or service.decode_token)(token)
    if not payload or not service.is_session_token(payload) or not payload.get("sub"):
        return None
    user_id = str(payload["sub"])
    jti = payload.get("jti")
    if jti and await (is_revoked or service.is_access_token_revoked)(str(jti)):
        return None
    if not await asyncio.to_thread(session_allowed_by_iam, user_id, payload.get("iat")):
        return None
    return Credential(kind=SESSION, user_id=user_id, token_id=str(jti) if jti else None)


# -- ending a user's credentials -----------------------------------------------------------------


async def revoke_user_credentials(user_id: str, *, include_keys: bool = False) -> bool:
    """Cut off every token the engine issued to or for ``user_id`` so far: their
    session tokens, the delegations made for them, their links and their coding
    agents' keys (``IAMService.revoke_tokens``). Their personal API keys stay
    unless ``include_keys``. False when it could not be done (no engine IAM, or
    IAM failed): what was issued then still expires within ten minutes, and the
    caller carries on with what it was doing (a password change must not fail
    for it)."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )

    iam = IAM()
    if iam is None:
        return False

    def revoke() -> None:
        with use_call_context(
            CallContext(principal=service_account("api"), on_behalf_of=user(user_id))
        ):
            iam.revoke_tokens(user_id, include_keys=include_keys)

    try:
        await asyncio.to_thread(revoke)
    except Exception as exc:  # noqa: BLE001 - logged; the sign-in credentials went already
        logger.error(f"The engine's tokens of user {user_id} were not revoked: {exc}")
        return False
    return True
