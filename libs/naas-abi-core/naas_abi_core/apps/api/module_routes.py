"""What a module's ``api(app)`` mounts is behind the engine's credential check.

A module adds routes to the engine's API through its ``api(app)`` hook. Each
route and mount it adds there answers only a request that carries a credential
the engine accepts: ``ABI_API_KEY``, or one a registered validator vouches for
(the same check as ``/app-html/``). A module opts out explicitly:

* ``api_checks_its_callers = True``: every route it mounts checks its caller
  itself (Nexus: its sessions, keys and public pages are its own decision);
* ``unguarded_api_paths``: paths below which it serves public files, or routes
  that check their caller themselves.

``/app-html/`` keeps its own middleware.

The guard decides which route a request reaches the way the router does: the
same routes, in the same order, matched on the same scope (never the URL rebuilt
from the Host header). It runs innermost, inside the app's other middleware, so
a 401 carries the CORS headers a browser needs to read it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, status
from naas_abi_core.apps.api.abi_api_key_auth import check_app_html_request
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute, Match, Router
from starlette.types import ASGIApp, Receive, Scope, Send

APP_HTML_PREFIX = "/app-html/"


def _under(path: str, prefixes: Iterable[str]) -> bool:
    for prefix in prefixes:
        base = prefix.rstrip("/")
        if base and (path == base or path.startswith(base + "/")):
            return True
    return False


def guarded_routes(module: Any, routes: Iterable[BaseRoute]) -> list[BaseRoute]:
    """The routes of ``routes`` (what ``module`` mounted) the guard checks."""
    if getattr(module, "api_checks_its_callers", False) is True:
        return []
    unguarded = tuple(getattr(module, "unguarded_api_paths", ()) or ())
    guarded: list[BaseRoute] = []
    for route in routes:
        path = getattr(route, "path", "") or ""
        if path.startswith(APP_HTML_PREFIX) or _under(path, unguarded):
            continue
        guarded.append(route)
    return guarded


def routed_to(router: Router, scope: Scope) -> BaseRoute | None:
    """The route ``router`` hands ``scope`` to: the first full match, else the
    first partial one (a method mismatch), as ``Router`` itself picks."""
    partial: BaseRoute | None = None
    for route in router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
        if match == Match.PARTIAL and partial is None:
            partial = route
    return partial


class ModuleRouteGuardMiddleware:
    """401 (or a closed websocket) for a request routed to a guarded module
    route without a credential the engine accepts. CORS preflight passes."""

    def __init__(
        self, app: ASGIApp, router: Router, routes: Iterable[BaseRoute]
    ) -> None:
        self.app = app
        self._router = router
        self._guarded = {id(route) for route in routes}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] not in ("http", "websocket")
            or scope.get("method") == "OPTIONS"
        ):
            await self.app(scope, receive, send)
            return
        route = routed_to(self._router, scope)
        if route is None or id(route) not in self._guarded:
            await self.app(scope, receive, send)
            return
        check = await asyncio.to_thread(check_app_html_request, Request(scope))
        if check.authorized:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid authentication credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)


def mount_module_apis(app: FastAPI, modules: Iterable[Any]) -> list[BaseRoute]:
    """Run each module's ``api(app)`` and guard what it mounted (see the module
    docstring). Returns the guarded routes."""
    if app.middleware_stack is not None:
        raise RuntimeError("Module routes must be mounted before the app starts")
    guarded: list[BaseRoute] = []
    for module in modules:
        before = {id(route) for route in app.router.routes}
        module.api(app)
        added = [route for route in app.router.routes if id(route) not in before]
        guarded += guarded_routes(module, added)
    if guarded:
        # Innermost: after (inside) every middleware already added, CORS included.
        app.user_middleware.append(
            Middleware(ModuleRouteGuardMiddleware, router=app.router, routes=guarded)
        )
    return guarded
