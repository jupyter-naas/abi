"""Set who and which workspace every API request acts for.

Each request runs with a ``CallContext`` (``naas_abi_core.engine.call_context``):
the ``api`` service account acting on behalf of the signed-in user. Every
kernel call Nexus makes for the request carries it: in process directly, over
NATS as the ``Abi-On-Behalf-Of`` header, which the kernel trusts from ``api``.
So the user is named only as strictly as ``AuthService`` signs a user in: a
session token (no ``scope``) whose ``jti`` is not revoked. A link token
(app-html, preview, grants), a revoked token or no token leaves the request
``ANONYMOUS``, not ``api``: a public route must never get ``api``'s rights.

Without a bearer token, the session cookie of a sign-in through an identity
provider names the user (``services/oidc``): its IAM principal id, with the
IAM groups its provider's groups claim maps to. A cookie request that changes
state without the session's CSRF token names nobody, and is marked so
(``request.state.nexus_csrf_failed``) for a 403. The session is left on
``request.state.nexus_session``.

Pure ASGI, so the context is set in the request's own context: async
endpoints, sync endpoints (Starlette copies the context into the threadpool)
and everything they await see it. ``EventService.publish()`` stamps the user
and workspace on every event, and identity event capture uses the user for
``created_by``.

The workspace is the ``/workspaces/{id}`` path segment, else a
``workspace_id`` query parameter.
Handlers that learn the workspace from the body (chat) set
``agent_workspace_id`` themselves — a view of the same context.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from urllib.parse import parse_qs

from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    Principal,
    service_account,
    use_call_context,
)
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

_WORKSPACE_PATH = re.compile(r"/workspaces/([^/?#]+)")
# The service account Nexus serves its requests as.
NEXUS_IDENTITY = "api"


def _decode_token(token: str) -> dict[str, Any] | None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    return decode_token(token)


def _bearer(headers: Headers) -> str | None:
    auth = headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def _is_revoked(jti: str) -> bool:
    from naas_abi.apps.nexus.apps.api.app.services.refresh_token import (
        is_access_token_revoked,
    )

    return await is_access_token_revoked(jti)


async def verified_user_id(headers: Headers) -> str | None:
    """The signed-in user of a request, checked as ``AuthService`` does.

    A session token only (not a scoped link token), not revoked. Fails
    closed: a revocation lookup that fails names nobody.
    """
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
        is_session_token,
    )

    token = _bearer(headers)
    if token is None:
        return None
    try:
        payload = _decode_token(token)
    except Exception:  # noqa: BLE001
        return None
    if not payload or not is_session_token(payload) or not payload.get("sub"):
        return None
    jti = payload.get("jti")
    if jti:
        try:
            if await _is_revoked(str(jti)):
                return None
        except Exception as exc:  # noqa: BLE001 - fail closed
            logger.warning(f"Revocation check failed; the request names no user: {exc}")
            return None
    return str(payload["sub"])


def user_id_from_headers(headers: Headers) -> str | None:
    """The bearer token's ``sub``, unchecked beyond its signature: a cache key
    (settings_cache), never identity. Identity is ``verified_user_id``."""
    auth = headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        payload = _decode_token(token.strip())
    except Exception:  # noqa: BLE001
        return None
    sub = (payload or {}).get("sub")
    return str(sub) if sub else None


def workspace_id_from_request(path: str, query_string: bytes) -> str | None:
    match = _WORKSPACE_PATH.search(path)
    if match:
        return match.group(1)
    values = parse_qs(query_string.decode("latin-1")).get("workspace_id")
    return values[0] if values and values[0] else None


class RequestIdentityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Websockets too (Socket.IO): their handlers run in this context.
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        with use_call_context(await request_call_context(scope)):
            await self.app(scope, receive, send)


async def request_call_context(scope: Scope) -> CallContext:
    """``api`` on behalf of the request's verified signed-in user; without
    one, ``ANONYMOUS`` (with the request's workspace and trigger)."""
    user_id = await verified_user_id(Headers(scope=scope))
    groups: frozenset[str] = frozenset()
    if user_id is None:
        from naas_abi.apps.nexus.apps.api.app.services.oidc.runtime import cookie_auth

        auth = await cookie_auth(scope)
        if auth is not None:
            state = scope.setdefault("state", {})
            if auth.session is not None:
                state["nexus_session"] = auth.session
                user_id = auth.session.user_id
                groups = frozenset(auth.session.group_ids)
            elif auth.csrf_failed:
                state["nexus_csrf_failed"] = True
    return replace(
        ANONYMOUS,
        principal=service_account(NEXUS_IDENTITY) if user_id else ANONYMOUS.principal,
        on_behalf_of=Principal(id=user_id, kind="user", groups=groups) if user_id else None,
        workspace_id=workspace_id_from_request(
            scope.get("path", ""), scope.get("query_string", b"")
        ),
        triggered_via="api",
    )
