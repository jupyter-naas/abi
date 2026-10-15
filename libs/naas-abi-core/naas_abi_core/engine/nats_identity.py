"""The ``CallContext`` of a NATS request, from its verified credentials.

Every kernel NATS primary adapter builds the context of a call here, and only
here (docs/specs/rfcs/20261013_identity-and-authorization.md, §10.2):

* the actor is the ``sub`` of the verified ``Nats-Auth-Token``;
* the user it acts for is the ``Abi-On-Behalf-Of`` header, accepted only when
  the actor is a trusted identity (``api``, ``engine``) until delegated tokens
  replace the header. From anyone else the call is refused;
* the trace id and the target workspace come from the request's ``context``
  envelope: request data, not identity.

``CallContext.principal_id`` and ``tenant_id`` in the request are never read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    ON_BEHALF_OF_HEADER,
    CallContext,
    service_account,
    user,
)
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)

AUTH_HEADER = "Nats-Auth-Token"
# The identities trusted to name the user they act for, until subtask 8's
# delegated tokens carry the user in the token itself.
ON_BEHALF_OF_IDENTITIES = frozenset({"api", "engine"})
# Longer than any principal id: usr_ plus a ULID, a UUID, email-sha256:<hex>.
_MAX_PRINCIPAL_ID = 256
_CALL_CONTEXT_MESSAGE = "abi.common.v1.CallContext"


class OnBehalfOfRefusedError(InvalidServiceTokenError):
    """The caller named a user it may not act for."""


def caller_context(headers: Mapping[str, str] | None, secret: str) -> CallContext:
    """The verified caller of a NATS request.

    Raises :class:`InvalidServiceTokenError` for a missing or invalid token,
    and its subclass :class:`OnBehalfOfRefusedError` for an
    ``Abi-On-Behalf-Of`` header the caller may not send.
    """
    headers = headers or {}
    identity = verify_service_token(headers.get(AUTH_HEADER, ""), secret)
    named = headers.get(ON_BEHALF_OF_HEADER, "")
    if not named:
        return CallContext(principal=service_account(identity))
    if identity not in ON_BEHALF_OF_IDENTITIES:
        raise OnBehalfOfRefusedError(f"{identity!r} may not act on behalf of a user")
    if len(named) > _MAX_PRINCIPAL_ID or named != named.strip():
        raise OnBehalfOfRefusedError("Malformed on-behalf-of principal id")
    return CallContext(principal=service_account(identity), on_behalf_of=user(named))


def refusal(exc: InvalidServiceTokenError, invalid_token: str) -> str:
    """The UNAUTHENTICATED message for a refused caller.

    A refused ``Abi-On-Behalf-Of`` header gets its own message, and a log
    line: the token was fine, so nobody should go chasing the JWT secret.
    """
    if isinstance(exc, OnBehalfOfRefusedError):
        logger.warning(f"Refused a NATS call naming a user: {exc}")
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
