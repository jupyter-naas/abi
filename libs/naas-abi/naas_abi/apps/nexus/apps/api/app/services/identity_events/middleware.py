"""Set who and which workspace every API request acts for.

Pure ASGI, so the ContextVars are set in the request's own context: async
endpoints, sync endpoints (Starlette copies the context into the threadpool)
and everything they await see them. ``EventService.publish()`` stamps them on
every event, and identity event capture uses them for ``created_by``.

The user is the bearer token's ``sub``. The workspace is the ``/workspaces/{id}``
path segment, else a ``workspace_id`` query parameter. Handlers that learn the
workspace from the body (chat) set ``agent_workspace_id`` themselves — it is
the same ContextVar.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_actor_workspace_id,
    event_triggered_via,
)
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

_WORKSPACE_PATH = re.compile(r"/workspaces/([^/?#]+)")


def _decode_token(token: str) -> dict[str, Any] | None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    return decode_token(token)


def user_id_from_headers(headers: Headers) -> str | None:
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
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        user_token = event_actor_user_id.set(user_id_from_headers(Headers(scope=scope)))
        workspace_token = event_actor_workspace_id.set(
            workspace_id_from_request(scope.get("path", ""), scope.get("query_string", b""))
        )
        via_token = event_triggered_via.set("api")
        try:
            await self.app(scope, receive, send)
        finally:
            event_triggered_via.reset(via_token)
            event_actor_workspace_id.reset(workspace_token)
            event_actor_user_id.reset(user_token)
