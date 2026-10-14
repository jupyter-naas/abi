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
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
DEFAULT_TTL = timedelta(hours=1)
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
) -> str:
    """Issue a token asserting ``identity`` (e.g. ``"api"``, ``"dagster"``), signed with the
    project secret. Only the engine's own processes hold it; modules use :func:`module_key`.
    """
    if not identity:
        raise ValueError("identity must be a non-empty string")
    return jwt.encode(_claims(identity, ttl, now), secret, algorithm=ALGORITHM)


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
) -> str:
    """Issue a token asserting ``identity`` with its module ``key`` (see :func:`module_key`)."""
    if not identity:
        raise ValueError("identity must be a non-empty string")
    return jwt.encode(
        _claims(identity, ttl, now),
        key,
        algorithm=ALGORITHM,
        headers={"kid": MODULE_KEY_ID},
    )


def _claims(identity: str, ttl: timedelta, now: datetime | None) -> dict:
    issued_at = now or datetime.now(UTC)
    return {"sub": identity, "iat": issued_at, "exp": issued_at + ttl}


def verify_service_token(token: str, secret: str) -> str:
    """Verify ``token`` and return the caller identity (the ``sub`` claim).

    A module token (``kid: "module"``) is checked against the key of the identity it
    asserts, which is never a first-party one; any other token against the secret.

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
        payload = jwt.decode(token, key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise InvalidServiceTokenError(str(exc)) from exc

    identity = payload.get("sub")
    if not isinstance(identity, str) or not identity:
        raise InvalidServiceTokenError("token is missing a valid 'sub' claim")
    return identity
