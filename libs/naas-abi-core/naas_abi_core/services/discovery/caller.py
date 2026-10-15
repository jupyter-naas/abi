"""The caller a hosting module vouches for: its token and on-behalf-of user.

A module hosting an agent, a model, an app or a job receives its caller's
``Nats-Auth-Token`` and ``Abi-On-Behalf-Of`` header and forwards both to
discovery. Discovery builds the caller's ``CallContext`` from them exactly as a
kernel NATS endpoint builds its own (``nats_identity.caller_context``), and IAM
decides in that context.

A job trigger is a stored message: it may be consumed long after its token
expired, so its token is checked as of the moment JetStream stored it.
"""

from __future__ import annotations

import math

import jwt
from naas_abi_core.engine.call_context import (
    ON_BEHALF_OF_HEADER,
    CallContext,
    service_account,
    user,
)
from naas_abi_core.engine.nats_auth import ALGORITHM, InvalidServiceTokenError
from naas_abi_core.engine.nats_identity import (
    AUTH_HEADER,
    ON_BEHALF_OF_IDENTITIES,
    OnBehalfOfRefusedError,
    caller_context,
)

# Clock skew tolerated between the token's issuer and the broker's timestamp.
LEEWAY_SECONDS = 30.0


def caller_of(
    token: str,
    on_behalf_of: str,
    secret: str,
    *,
    at: float | None = None,
) -> CallContext:
    """The verified caller of a forwarded call; ``at``: when the token had to be
    valid (seconds since the epoch), by default now.

    Raises ``InvalidServiceTokenError``, or its subclass
    ``OnBehalfOfRefusedError`` for a user the caller may not act for.
    """
    if not at:
        return caller_context(
            {AUTH_HEADER: token, ON_BEHALF_OF_HEADER: on_behalf_of}, secret
        )
    if not math.isfinite(at):
        raise InvalidServiceTokenError("Invalid stored time")
    try:
        claims = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"verify_exp": False}
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidServiceTokenError(str(exc)) from exc
    identity, issued, expires = claims.get("sub"), claims.get("iat"), claims.get("exp")
    if not isinstance(identity, str) or not identity:
        raise InvalidServiceTokenError("token is missing a valid 'sub' claim")
    if not all(isinstance(v, int | float) for v in (issued, expires)):
        raise InvalidServiceTokenError("token is missing its validity window")
    assert isinstance(issued, int | float) and isinstance(expires, int | float)
    if not issued - LEEWAY_SECONDS <= at <= expires + LEEWAY_SECONDS:
        raise InvalidServiceTokenError("token was not valid when the call was stored")
    if not on_behalf_of:
        return CallContext(principal=service_account(identity))
    if identity not in ON_BEHALF_OF_IDENTITIES:
        raise OnBehalfOfRefusedError(f"{identity!r} may not act on behalf of a user")
    if len(on_behalf_of) > 256 or on_behalf_of != on_behalf_of.strip():
        raise OnBehalfOfRefusedError("Malformed on-behalf-of principal id")
    return CallContext(
        principal=service_account(identity), on_behalf_of=user(on_behalf_of)
    )


def run_owner(context: CallContext) -> str:
    """Who owns what a call starts: the user it acts for, else the actor."""
    served = context.user
    return served.id if served is not None else context.principal.id
