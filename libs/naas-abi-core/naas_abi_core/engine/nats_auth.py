"""NATS service-identity tokens.

See docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md ("Decisions locked in" —
Stage 1's JWT is deliberately minimal, not the full Stage 2 design) and
docs/adr/20261014_module-identities.md.

HS256, one claim: which process holds the token (``sub``). Two kinds of key sign it:

- **The project secret** (``nats.jwt_secret``), held by the engine's own processes (the
  API, the engine, Dagster). Its tokens may assert any identity.
- **A module key**, derived from the project secret for one identity
  (:func:`module_key`). An SDK module gets its own key instead of the secret, so its tokens
  can assert only that identity, and never a first-party one (:data:`FIRST_PARTY_IDENTITIES`).
  Its tokens carry the header ``kid: "module"``; the verifier derives the key from ``sub``.

**Audience.** A token sent to a module (its agents, models and apps) is bound to the module
instance it calls (``aud``, :data:`BOUND_TTL`), so the module cannot replay it anywhere else:
the engine's services refuse a token with an audience, and discovery accepts one only for the
instance it names. Tokens for the engine's services carry no audience.

There is still no scope or resource claim: rights between modules are Stage 2 work. Discovery
binds a registration's module id to the token's identity, and Nexus is the only caller whose
user ids a module trusts. The secret itself is delivered like any other secret, via
``SecretService``/``config.yaml``; this module only signs and verifies. Generate it with at
least 32 bytes of entropy (e.g. ``secrets.token_urlsafe(32)``) — HS256 warns below that length.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
DEFAULT_TTL = timedelta(hours=1)
# A token bound to one module instance (``aud``): short, so one a module kept is soon
# useless, and handed out with most of it left (naas_abi_sdk.service_token).
BOUND_TTL = timedelta(minutes=5)
# The ``kid`` header of a token signed with a module key.
MODULE_KEY_ID = "module"
# The engine's own processes. No module key exists for them, and no module token asserts them.
FIRST_PARTY_IDENTITIES = frozenset({"api", "engine", "dagster"})


class InvalidServiceTokenError(Exception):
    """Raised when a token fails signature verification or has expired."""


def issue_service_token(
    identity: str,
    secret: str,
    *,
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
    audience: str | None = None,
) -> str:
    """Issue a token asserting ``identity`` (e.g. ``"api"``, ``"dagster"``), signed with the
    project secret. Only the engine's own processes hold it; modules use :func:`module_key`.
    ``audience``: the module instance it is sent to (see the module docstring).
    """
    if not identity:
        raise ValueError("identity must be a non-empty string")
    return jwt.encode(
        _claims(identity, ttl, now, audience), secret, algorithm=ALGORITHM
    )


def module_key(secret: str, identity: str) -> str:
    """The key a module signs its tokens with: they can assert ``identity`` only.

    Derived from the project secret (HMAC-SHA256), so it needs no storage of its own and
    changes when the secret does. Refused for a first-party identity.
    """
    if not identity:
        raise ValueError("identity must be a non-empty string")
    if identity in FIRST_PARTY_IDENTITIES:
        raise ValueError(f"{identity!r} is a first-party identity: no module key exists for it")
    digest = hmac.new(
        secret.encode(), f"abi.module-key.v1:{identity}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_module_token(
    identity: str,
    key: str,
    *,
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
    audience: str | None = None,
) -> str:
    """Issue a token asserting ``identity`` with its module ``key`` (see :func:`module_key`)."""
    if not identity:
        raise ValueError("identity must be a non-empty string")
    return jwt.encode(
        _claims(identity, ttl, now, audience),
        key,
        algorithm=ALGORITHM,
        headers={"kid": MODULE_KEY_ID},
    )


def _claims(
    identity: str, ttl: timedelta, now: datetime | None, audience: str | None = None
) -> dict:
    issued_at = now or datetime.now(UTC)
    claims: dict = {"sub": identity, "iat": issued_at, "exp": issued_at + ttl}
    if audience is not None:
        if not audience:
            raise ValueError("audience must be a non-empty string")
        claims["aud"] = audience
    return claims


class ServiceTokenSource:
    """Token source for an engine process's ``Transport``: ``source()`` gives a token for
    the engine's services, ``source.for_audience(instance_id)`` one bound to that module
    instance (:data:`BOUND_TTL`, handed out with most of it left). The cache is the
    SDK's ``TokenCache``, shared with ``ModuleToken``."""

    def __init__(
        self,
        identity: str,
        secret: str,
        *,
        ttl: timedelta = DEFAULT_TTL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        from naas_abi_sdk.service_token import TokenCache

        if not identity:
            raise ValueError("identity must be a non-empty string")
        self.identity, self.secret = identity, secret
        self._cache = TokenCache(
            self._sign, ttl_seconds=int(ttl.total_seconds()), clock=clock
        )

    def __call__(self) -> str:
        return self._cache.unbound()

    def for_audience(self, audience: str) -> str:
        return self._cache.bound(audience)

    def _sign(self, audience: str | None, issued_at: int, ttl: int) -> str:
        return issue_service_token(
            self.identity,
            self.secret,
            ttl=timedelta(seconds=ttl),
            now=datetime.fromtimestamp(issued_at, UTC),
            audience=audience,
        )


def verify_service_token(
    token: str, secret: str, *, audience: str | None = None
) -> str:
    """Verify ``token`` and return the caller identity (the ``sub`` claim).

    A module token (``kid: "module"``) is checked against the key of the identity it
    asserts, which is never a first-party one; any other token against the secret.

    ``audience``: the module instance the token must be bound to (a call to that
    module). Without it, a token bound to an audience is refused: a module cannot
    replay a token it was sent.

    Raises :class:`InvalidServiceTokenError` on a bad signature, malformed token, or an
    expired token — callers should treat all three identically (reject the call), not try
    to distinguish them.
    """
    try:
        key = secret
        if jwt.get_unverified_header(token).get("kid") == MODULE_KEY_ID:
            # Read only to know whose key checks the signature.
            claimed = jwt.decode(token, options={"verify_signature": False}).get("sub")
            if not isinstance(claimed, str) or not claimed:
                raise InvalidServiceTokenError("token is missing a valid 'sub' claim")
            if claimed in FIRST_PARTY_IDENTITIES:
                raise InvalidServiceTokenError(
                    "a module token cannot assert a first-party identity"
                )
            key = module_key(secret, claimed)
        payload = jwt.decode(
            token,
            key,
            algorithms=[ALGORITHM],
            audience=audience,
            options={"require": ["aud"]} if audience is not None else None,
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidServiceTokenError(str(exc)) from exc

    identity = payload.get("sub")
    if not isinstance(identity, str) or not identity:
        raise InvalidServiceTokenError("token is missing a valid 'sub' claim")
    return identity
