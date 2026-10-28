"""The ``CallContext`` of a NATS request, from its verified credentials.

Every kernel NATS primary adapter builds the context of a call here, and only
here (``engine/AGENTS.md``, "The call context"):

* the ``Nats-Auth-Token`` is an engine token, verified against the JWKS
  (``nats_auth.TokenVerifier``) for an audience the endpoint accepts;
* the actor is its ``sub``, a principal id (``abi_name`` names a service
  account); with ``act``, the actor is ``act.sub`` and ``sub`` the user it
  acts for. ``grp`` and ``abi_scope`` become the groups and the narrowing;
* the user it acts for is named by the token and nothing else: a delegated
  token (``abi:delegated:agent``) carries it. The ``Abi-On-Behalf-Of`` header
  of the earlier stage is gone, and a request that carries one is refused (a
  header naming a user can only narrow a call, so dropping it would widen it);
* the trace id and the target workspace come from the request's ``context``
  envelope: request data, not identity.

``CallContext.principal_id`` and ``tenant_id`` in the request are never read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.call_context import CallContext, Principal
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    TokenClaims,
    TokenVerifier,
)

AUTH_HEADER = "Nats-Auth-Token"
# The header of the earlier stage, which named the user a trusted caller acted
# for. A delegated token carries the user now; a request with this header is
# refused, never ignored.
REFUSED_HEADER = "abi-on-behalf-of"
_CALL_CONTEXT_MESSAGE = "abi.common.v1.CallContext"


class OnBehalfOfRefusedError(InvalidServiceTokenError):
    """The request carried the ``Abi-On-Behalf-Of`` header."""


def caller_context(
    headers: Mapping[str, str] | None,
    verifier: TokenVerifier,
    *,
    at: float | None = None,
) -> CallContext:
    """The verified caller of a NATS request; ``at``: when its token had to be
    valid, by default now (``TokenVerifier.verify``).

    Raises :class:`InvalidServiceTokenError` for a missing or invalid token,
    and its subclass :class:`OnBehalfOfRefusedError` for a request carrying
    the ``Abi-On-Behalf-Of`` header.
    """
    headers = headers or {}
    claims = verifier.verify(headers.get(AUTH_HEADER, ""), at=at)
    if any(name.lower() == REFUSED_HEADER and value for name, value in headers.items()):
        identity = claims.name or claims.subject
        raise OnBehalfOfRefusedError(
            f"{identity!r} sent the Abi-On-Behalf-Of header, which is no longer "
            "accepted: act for a user with a delegated token"
        )
    return token_context(claims)


def token_context(claims: TokenClaims) -> CallContext:
    """The ``CallContext`` a verified token stands for."""
    groups = frozenset(claims.groups)
    sub = Principal(
        id=claims.subject,
        kind=claims.kind,  # type: ignore[arg-type]  # user | service_account
        name=claims.name if claims.kind == "service_account" else None,
        groups=groups if claims.kind == "user" else frozenset(),
    )
    if claims.actor is not None:
        actor = Principal(
            id=claims.actor, kind="service_account", name=claims.actor_name
        )
        principal, on_behalf_of = actor, sub
    else:
        principal, on_behalf_of = sub, None
    return CallContext(
        principal=principal,
        on_behalf_of=on_behalf_of,
        audience=claims.audience,
        token_id=claims.token_id,
        token_issued_at=claims.issued_at,
        scope=claims.scope,
    )


def refusal(exc: InvalidServiceTokenError, invalid_token: str) -> str:
    """The UNAUTHENTICATED message for a refused caller.

    A refused ``Abi-On-Behalf-Of`` header gets its own message, and a log
    line: the token was fine, so nobody should go chasing the signing key.
    """
    if isinstance(exc, OnBehalfOfRefusedError):
        logger.warning(f"Refused a NATS call with the Abi-On-Behalf-Of header: {exc}")
        return f"on-behalf-of refused: {exc}"
    return invalid_token


def for_request(caller: CallContext, request: Any) -> CallContext:
    """``caller`` with the trace id and target workspace of ``request``'s
    ``context`` envelope, when it has one."""
    envelope = _envelope(request)
    if envelope is None:
        return caller
    return replace(
        caller,
        trace_id=envelope.trace_id or caller.trace_id,
        workspace_id=envelope.workspace_id or caller.workspace_id,
    )


def request_envelope(request: Any) -> Any:
    """``request``'s ``context`` envelope (``abi.common.v1.CallContext``), or None."""
    return _envelope(request)


def _envelope(request: Any) -> Any:
    descriptor = getattr(request, "DESCRIPTOR", None)
    field = descriptor.fields_by_name.get("context") if descriptor else None
    if field is None or field.message_type is None:
        return None
    if field.message_type.full_name != _CALL_CONTEXT_MESSAGE:
        return None
    return request.context
