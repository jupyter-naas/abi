"""Stage 1 NATS service-identity tokens.

See docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md ("Decisions locked in" —
Stage 1's JWT is deliberately minimal, not the full Stage 2 design).

Stage 1 has no extracted or untrusted module: every NATS client is first-party infrastructure
already under this deployment's control (the API process, Dagster). These tokens exist to give
a NATS primary adapter a real, checkable caller identity instead of trusting "anyone who can
reach the NATS server" — but there is deliberately no per-module claim, scope, or resource ARN
here yet, because Stage 1 has nothing to scope *between*. That richer model (ARN-style resource
scopes, checked in the domain rather than the transport, propagated via a shared context
variable) is Stage 2 work — see the RFC's "Agents: the sub-agent composition problem" /
"Decisions locked in" for the target shape. Don't grow this module toward that design before
Stage 2 actually needs it.

One shared secret, HS256, one claim: which known first-party process issued/holds the token
(``"api"``, ``"dagster"``, ...). The secret itself is delivered exactly like any other secret
today — via ``SecretService``/``config.yaml`` — this module only signs and verifies; it never
reads the secret's value from anywhere on its own. Generate it with at least 32 bytes of
entropy (e.g. ``secrets.token_urlsafe(32)``) — HS256 warns below that length.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
DEFAULT_TTL = timedelta(hours=1)


class InvalidServiceTokenError(Exception):
    """Raised when a token fails signature verification or has expired."""


def issue_service_token(
    identity: str,
    secret: str,
    *,
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
) -> str:
    """Issue a token asserting ``identity`` (e.g. ``"api"``, ``"dagster"``).

    ``identity`` is a known, deployment-controlled process name — not a per-module or
    per-user claim. See the module docstring for why that's deliberate in Stage 1.
    """
    if not identity:
        raise ValueError("identity must be a non-empty string")
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": identity,
        "iat": issued_at,
        "exp": issued_at + ttl,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_service_token(token: str, secret: str) -> str:
    """Verify ``token`` and return the caller identity (the ``sub`` claim).

    Raises :class:`InvalidServiceTokenError` on a bad signature, malformed token, or an
    expired token — callers should treat all three identically (reject the call), not try
    to distinguish them.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise InvalidServiceTokenError(str(exc)) from exc

    identity = payload.get("sub")
    if not isinstance(identity, str) or not identity:
        raise InvalidServiceTokenError("token is missing a valid 'sub' claim")
    return identity
