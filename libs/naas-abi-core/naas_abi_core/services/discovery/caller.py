"""The caller a hosting module vouches for: the token it received.

A module hosting an agent, a model, an app or a job receives its caller's
``Nats-Auth-Token`` and forwards it to discovery. Discovery builds the caller's
``CallContext`` from it exactly as a kernel NATS endpoint builds its own
(``nats_identity.caller_context``), and IAM decides in that context. A token
that carries a user is a delegation (``abi:delegated:agent``) naming the module
that acts for them: its host and nobody else may forward it.

A job trigger is a stored message: it may be consumed long after its token
expired, so its token is checked as of the moment JetStream stored it.
"""

from __future__ import annotations

from naas_abi_core.engine.call_context import CallContext, call_subject
from naas_abi_core.engine.nats_auth import TokenVerifier
from naas_abi_core.engine.nats_identity import AUTH_HEADER, caller_context


def caller_of(
    token: str,
    verifier: TokenVerifier,
    *,
    at: float | None = None,
) -> CallContext:
    """The verified caller of a forwarded call; ``at``: when the token had to be
    valid (seconds since the epoch), by default now.

    Raises ``InvalidServiceTokenError``."""
    return caller_context({AUTH_HEADER: token}, verifier, at=at or None)


def run_owner(context: CallContext) -> str:
    """Who owns what a call starts (``call_subject``): the user it acts for,
    else the actor."""
    return call_subject(context) or context.principal.id
