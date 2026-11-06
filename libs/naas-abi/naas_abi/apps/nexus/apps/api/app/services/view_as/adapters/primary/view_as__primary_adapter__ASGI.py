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
        refusal = confinement.judge(
            scope,
            person=view.person_name,
            workspace_id=view.workspace_id,
            workspace_name=view.workspace_name,
        )
        if refusal is not None:
            await _answer(send, refusal.status, refusal.detail)
            return
        await self.app(scope, receive, send)
