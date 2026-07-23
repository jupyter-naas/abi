"""Serve the X post-count dashboard + its JSON snapshots from object storage.

Mirrors the counter_uas report-hub middleware: the published ``index.html`` and
``data/*.json`` under ``x/apps/x/`` in object storage are served through
``/app-html/x/apps/x/…`` before the Nexus static ``/app-html/{path}`` handler.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

from naas_abi_marketplace.applications.x.apps.x.hub import DEFAULT_APP_PREFIX

APP_HTML_INDEX_PATH = "/app-html/x/apps/x/index.html"
APP_HTML_DATA_PREFIX = "/app-html/x/apps/x/data/"
_DATA_FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+\.json$")


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
        except Exception:
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
    """Serve the dashboard index + data snapshots before the static catch-all."""

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
                # Fall through to the bundled stub index.html when the dashboard
                # has not been published to object storage yet.
                if exc.status_code == 404:
                    return await call_next(request)
                raise

        if path.startswith(APP_HTML_DATA_PREFIX):
            name = path[len(APP_HTML_DATA_PREFIX) :]
            if not _DATA_FILE_RE.fullmatch(name):
                return await call_next(request)
            return _serve_object(
                self._object_storage,
                f"{DEFAULT_APP_PREFIX}/data",
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
