"""Set who and which workspace every API request acts for.

Each request runs with a ``CallContext`` (``naas_abi_core.engine.call_context``):
the ``api`` service account acting on behalf of the signed-in user. In process,
every kernel call Nexus makes for the request carries it directly; over NATS the
call carries a delegation naming ``api`` and the user (``engine_credentials``),
never a header. So the user is named only as strictly as the credential that
proves them (``services/auth/credentials.py``): a session, or an API key, a
coding agent's key where the route takes one, each not revoked and not
suspended. A link (app-html, preview, remote app grant), an agent delegation, a
revoked or unknown credential, or none, leaves the request ``ANONYMOUS``, not
``api``: a public route must never get ``api``'s rights.

A credential of a kind the route does not take (a coding key on ``/api/chat``,
an API key on ``/api/auth/*``) names nobody either, and is marked so
(``request.state.nexus_credential_refused``) for a 403. A key narrows the
context: its scope is the context's ``scope``, intersected with the user's own
policy (RFC §5.3).

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

from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import (
    Credential,
    CredentialKind,
    accepted_kinds,
    bearer_credential,
)
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


async def verified_credential(
    headers: Headers, path: str
) -> tuple[Credential | None, CredentialKind | None]:
    """The credential of a request's bearer token, checked as ``AuthService``
    checks a session and IAM checks a key: ``(credential, None)``; or
    ``(None, kind)`` for a valid credential of a kind ``path`` does not take;
    or ``(None, None)``. Fails closed."""
    token = _bearer(headers)
    if token is None:
        return None, None
    credential = await bearer_credential(token, decode=_decode_token, is_revoked=_is_revoked)
    if credential is None:
        return None, None
    if credential.kind not in accepted_kinds(path):
        return None, credential.kind
    return credential, None


async def verified_user_id(headers: Headers) -> str | None:
    """The signed-in user of a request's session token (no route in mind: a
    session is the one kind every route takes)."""
    credential, _ = await verified_credential(headers, "")
    return credential.user_id if credential is not None else None


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
    """``api`` on behalf of the request's verified user, narrowed by the scope of
    the credential that proved them; without one, ``ANONYMOUS`` (with the
    request's workspace and trigger)."""
    headers = Headers(scope=scope)
    state = scope.setdefault("state", {})
    credential, refused = await verified_credential(headers, scope.get("path", ""))
    if credential is not None:
        state["nexus_credential"] = credential
    elif refused is not None:
        state["nexus_credential_refused"] = refused
    if credential is None:
        from naas_abi.apps.nexus.apps.api.app.services.oidc.runtime import cookie_auth

        auth = await cookie_auth(scope)
        if auth is not None:
            if auth.session is not None:
                state["nexus_session"] = auth.session
                state.pop("nexus_credential_refused", None)
                credential = Credential(
                    kind="session",
                    user_id=auth.session.user_id,
                    groups=frozenset(auth.session.group_ids),
                    session=auth.session,
                )
                state["nexus_credential"] = credential
            elif auth.csrf_failed:
                state["nexus_csrf_failed"] = True
    named = (
        Principal(id=credential.user_id, kind="user", groups=credential.groups)
        if credential is not None
        else None
    )
    return replace(
        ANONYMOUS,
        principal=service_account(NEXUS_IDENTITY) if named else ANONYMOUS.principal,
        on_behalf_of=named,
        scope=credential.scope if credential is not None else None,
        workspace_id=workspace_id_from_request(
            scope.get("path", ""), scope.get("query_string", b"")
        ),
        triggered_via="api",
    )
