"""``ViewGuardMiddleware``: during a view, answer only what it allows.

Runs after ``RequestIdentityMiddleware`` (which resolved the view and left it on the
scope's state as ``nexus_view``) and before the settings cache, so a write is refused
before the cache answers ``POST /api/settings-cache/refresh`` or drops its entries. It
sits inside CORS, so a refusal carries the CORS headers the web app needs to read it.

Judging is ``confinement.judge``; the refusals are 403 ``{"detail": ...}``. A request
whose view could not be verified (``nexus_view_unavailable``) is answered 503: it names
nobody, and a write must not run as the viewer meanwhile. Stop and the sign-out pass: they
end the view or the session without the verification that failed.
"""

from __future__ import annotations

import asyncio
import json

from naas_abi.apps.nexus.apps.api.app.services.view_as import confinement
from starlette.types import ASGIApp, Receive, Scope, Send


async def _answer(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _read_body(receive: Receive) -> bytes | None:
    """The request's whole body, None past ``MAX_BODY``."""
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > confinement.MAX_BODY:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks)


def _replay(body: bytes) -> Receive:
    """A ``receive`` that hands the app the body already read, then the client's end."""
    sent = False

    async def receive() -> dict:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Event().wait()  # no more: the client stays connected until the response
        raise AssertionError("unreachable")

    return receive


class ViewGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.get("state") or {}
        if state.get("nexus_view_unavailable") and scope.get("path", "").startswith(
            confinement.API_PREFIX
        ):
            # Stop and the sign-out only give access up: they need no verification.
            if not confinement.is_ending(scope):
                await _answer(send, 503, "The view could not be verified: try again")
                return
        view = state.get("nexus_view")
        if view is None:
            await self.app(scope, receive, send)
            return
        body: bytes | None = None
        if confinement.needs_body(scope):
            # A read sent by POST names its workspace in its body: read it (bounded), judge it,
            # and hand the app the same bytes.
            body = await _read_body(receive)
            if body is None:
                await _answer(send, 413, "Too large to be judged in a view")
                return
            receive = _replay(body)
        refusal = confinement.judge(
            scope,
            person=view.person_name,
            workspace_id=view.workspace_id,
            workspace_name=view.workspace_name,
            body=body,
        )
        if refusal is not None:
            await _answer(send, refusal.status, refusal.detail)
            return
        await self.app(scope, receive, send)
