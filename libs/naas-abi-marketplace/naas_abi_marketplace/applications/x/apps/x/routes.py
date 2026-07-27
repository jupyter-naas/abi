"""Serve the X Recent Tweets dashboard + JSON snapshots from object storage.

Published layout under ``x/apps/x/``::

    index.html
    globals/*.json
    count_recent_tweets/*.json
    search_recents_tweets/*.json

Served through ``/app-html/x/apps/x/…`` before the Nexus static catch-all.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x.api.common import DEFAULT_APP_PREFIX
from starlette.middleware.base import BaseHTTPMiddleware

APP_HTML_INDEX_PATH = "/app-html/x/apps/x/index.html"
APP_HTML_PREFIX = "/app-html/x/apps/x/"
_SNAPSHOT_RE = re.compile(
    r"^(globals|count_recent_tweets|search_recents_tweets)/[A-Za-z0-9_.-]+\.json$"
)
# Legacy data/*.json paths (older hub publishes) — keep serving if present.
_LEGACY_DATA_RE = re.compile(r"^data/[A-Za-z0-9_.-]+\.json$")


def _frame_ancestor_headers(request: Request) -> dict[str, str]:
    ancestors = ["'self'"]
    for header in (request.headers.get("origin"), request.headers.get("referer")):
        if not header:
            continue
        try:
            from urllib.parse import urlparse

            origin = f"{urlparse(header).scheme}://{urlparse(header).netloc}".rstrip(
                "/"
            )
            if origin and origin not in ancestors:
                ancestors.append(origin)
        except Exception:  # noqa: BLE001,S110
            pass
    return {"Content-Security-Policy": f"frame-ancestors {' '.join(ancestors)};"}


def _serve_object(
    object_storage_service: ObjectStorageService,
    prefix: str,
    name: str,
    media_type: str,
    request: Request,
) -> Response:
    try:
        content = object_storage_service.get_object(prefix, name)
    except Exceptions.ObjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers=_frame_ancestor_headers(request),
    )


class XCountAppMiddleware(BaseHTTPMiddleware):
    """Serve the dashboard index + snapshot JSON before the static catch-all."""

    def __init__(self, app, object_storage_service: ObjectStorageService) -> None:
        super().__init__(app)
        self._object_storage = object_storage_service

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)

        path = request.url.path
        if path == APP_HTML_INDEX_PATH:
            try:
                return _serve_object(
                    self._object_storage,
                    DEFAULT_APP_PREFIX,
                    "index.html",
                    "text/html; charset=utf-8",
                    request,
                )
            except HTTPException as exc:
                if exc.status_code == 404:
                    return await call_next(request)
                raise

        if path.startswith(APP_HTML_PREFIX):
            rel = path[len(APP_HTML_PREFIX) :]
            if _SNAPSHOT_RE.fullmatch(rel) or _LEGACY_DATA_RE.fullmatch(rel):
                # rel is e.g. globals/scenarios.json → prefix=…/globals, key=scenarios.json
                if "/" not in rel:
                    return await call_next(request)
                subdir, name = rel.rsplit("/", 1)
                return _serve_object(
                    self._object_storage,
                    f"{DEFAULT_APP_PREFIX}/{subdir}",
                    name,
                    "application/json; charset=utf-8",
                    request,
                )

        return await call_next(request)


def register_x_count_app_routes(
    app: FastAPI,
    object_storage_service: ObjectStorageService,
) -> None:
    app.add_middleware(
        XCountAppMiddleware, object_storage_service=object_storage_service
    )
