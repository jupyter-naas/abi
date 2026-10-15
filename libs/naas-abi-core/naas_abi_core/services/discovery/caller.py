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

from naas_abi_core.engine.call_context import (
    ON_BEHALF_OF_HEADER,
    CallContext,
    call_subject,
)
from naas_abi_core.engine.nats_auth import TokenVerifier
from naas_abi_core.engine.nats_identity import AUTH_HEADER, caller_context


def caller_of(
    token: str,
    on_behalf_of: str,
    verifier: TokenVerifier,
    *,
    at: float | None = None,
) -> CallContext:
    """The verified caller of a forwarded call; ``at``: when the token had to be
    valid (seconds since the epoch), by default now.

    Raises ``InvalidServiceTokenError``, or its subclass
    ``OnBehalfOfRefusedError`` for a user the caller may not act for.
    """
    return caller_context(
        {AUTH_HEADER: token, ON_BEHALF_OF_HEADER: on_behalf_of},
        verifier,
        at=at or None,
    )


def run_owner(context: CallContext) -> str:
    """Who owns what a call starts (``call_subject``): the user it acts for,
    else the actor."""
    return call_subject(context) or context.principal.id
