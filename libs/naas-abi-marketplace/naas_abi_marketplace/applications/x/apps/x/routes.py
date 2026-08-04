"""Serve the X Recent Tweets dashboard + JSON snapshots from object storage.

Published layout under ``x/apps/x/``::

    index.html
    _next/static/...
    globals/*.json
    count_recent_tweets/*.json
    search_recents_tweets/*.json
    search_users/*.json

Served through ``/app-html/x/apps/x/…`` before the Nexus static catch-all.
"""

from __future__ import annotations

import json
import mimetypes
import re
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x.api.common import (
    DEFAULT_APP_PREFIX,
    DEFAULT_TWEET_LIMIT,
    DEFAULT_USER_LIMIT,
    TWEET_FACET_COLUMNS,
    SnapshotContext,
    normalize_tweet_filters,
)
from starlette.middleware.base import BaseHTTPMiddleware

APP_HTML_INDEX_PATH = "/app-html/x/apps/x/index.html"
APP_HTML_INDEX_DIR = "/app-html/x/apps/x/"
APP_HTML_PREFIX = "/app-html/x/apps/x/"
_SNAPSHOT_RE = re.compile(
    r"^(globals|count_recent_tweets|search_recents_tweets|search_users)"
    r"/[A-Za-z0-9_.-]+\.json$"
)
# Legacy data/*.json paths (older hub publishes) — keep serving if present.
_LEGACY_DATA_RE = re.compile(r"^data/[A-Za-z0-9_.-]+\.json$")
# Next.js static export assets (hashed JS/CSS under _next/static/...).
_ASSET_RE = re.compile(
    r"^(_next/[A-Za-z0-9_./-]+|favicon\.ico|robots\.txt|[A-Za-z0-9_.-]+\.(js|css|map|woff2?|ttf|svg|png|jpg|webp|ico))$"
)


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


def _media_type(name: str, default: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        if guessed.startswith("text/") or guessed in {
            "application/javascript",
            "application/json",
            "image/svg+xml",
        }:
            return f"{guessed}; charset=utf-8"
        return guessed
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".map"):
        return "application/json; charset=utf-8"
    return default


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


def _serve_relative(
    object_storage_service: ObjectStorageService,
    rel: str,
    request: Request,
    media_type: str | None = None,
) -> Response:
    if "/" not in rel:
        return _serve_object(
            object_storage_service,
            DEFAULT_APP_PREFIX,
            rel,
            media_type or _media_type(rel, "text/html; charset=utf-8"),
            request,
        )
    subdir, name = rel.rsplit("/", 1)
    return _serve_object(
        object_storage_service,
        f"{DEFAULT_APP_PREFIX}/{subdir}",
        name,
        media_type or _media_type(name),
        request,
    )


class XCountAppMiddleware(BaseHTTPMiddleware):
    """Serve the dashboard index, assets, snapshot JSON *and* the live API.

    The API paths are handled here rather than as plain FastAPI routes because
    Nexus registers a ``/app-html/{path:path}`` static catch-all ahead of this
    module's routes: anything left to normal routing is answered by that
    catch-all with "App HTML not found" before it can reach us. Middleware runs
    before the router, so this is the only ordering that holds.
    """

    def __init__(
        self,
        app,
        object_storage_service: ObjectStorageService,
        triple_store_service: TripleStoreService | None = None,
    ) -> None:
        super().__init__(app)
        self._object_storage = object_storage_service
        self._triple_store = triple_store_service

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)

        path = request.url.path
        # trailingSlash:true export may request /app-html/x/apps/x/
        if path in (APP_HTML_INDEX_PATH, APP_HTML_INDEX_DIR):
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
            if not rel or rel.endswith("/"):
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

            handler = API_HANDLERS.get(rel)
            if handler is not None:
                if self._triple_store is None:
                    # Storage-only deployment: let the page fall back to the
                    # published snapshot rather than pretending to search.
                    return _json_error(
                        503, "live search unavailable (no triple store)", request
                    )
                return handler(
                    SnapshotContext(None, self._triple_store, queries=[]),  # type: ignore[arg-type]
                    request,
                )

            if _SNAPSHOT_RE.fullmatch(rel) or _LEGACY_DATA_RE.fullmatch(rel):
                return _serve_relative(
                    self._object_storage,
                    rel,
                    request,
                    "application/json; charset=utf-8",
                )

            if _ASSET_RE.fullmatch(rel):
                return _serve_relative(self._object_storage, rel, request)

        return await call_next(request)


TWEET_SEARCH_PATH = f"{APP_HTML_PREFIX}api/tweets"
TWEET_COLUMN_VALUES_PATH = f"{APP_HTML_PREFIX}api/tweets/values"
USER_SEARCH_PATH = f"{APP_HTML_PREFIX}api/users"
USER_POSTS_PATH = f"{APP_HTML_PREFIX}api/users/posts"
# Hard ceiling for a single live query, independent of what the caller asks for.
MAX_TWEET_SEARCH_LIMIT = 5000
# One page of an author's posts. The Users page walks the graph with OFFSET
# rather than pulling every post at once.
DEFAULT_USER_POSTS_PAGE = 100
MAX_USER_POSTS_PAGE = 500


def _json_error(status: int, detail: str, request: Request) -> Response:
    """Error as a JSONResponse — middleware bypasses FastAPI exception handlers."""
    return JSONResponse(
        {"detail": detail},
        status_code=status,
        headers=_frame_ancestor_headers(request),
    )


def _int_param(
    request: Request, name: str, default: int, low: int, high: int
) -> int | None:
    """Bounded int query param, or ``None`` when the value is unusable."""
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < low or value > high:
        return None
    return value


def _parse_filters(raw: str) -> dict:
    """Decode the ``filters`` query param (JSON) into validated column filters.

    ``normalize_tweet_filters`` drops unknown columns, so a malformed or hostile
    payload degrades to "no filter" rather than reaching the SPARQL builder.
    """
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail="filters must be a JSON object"
        ) from None
    if not isinstance(decoded, dict):
        raise HTTPException(status_code=400, detail="filters must be a JSON object")
    return normalize_tweet_filters(decoded)


def register_x_count_app_routes(
    app: FastAPI,
    object_storage_service: ObjectStorageService,
    triple_store_service: TripleStoreService | None = None,
) -> None:
    """Mount the dashboard middleware, which also serves the live search API.

    *triple_store_service* is optional so an object-storage-only deployment
    keeps serving the published snapshots; without it the API paths answer 503
    and the web app falls back to the rows already in the snapshot.
    """
    app.add_middleware(
        XCountAppMiddleware,
        object_storage_service=object_storage_service,
        triple_store_service=triple_store_service,
    )


def _handle_tweet_search(ctx: SnapshotContext, request: Request) -> Response:
    """Newest tweets for a query + window, narrowed by column filters."""
    params = request.query_params
    query = params.get("query") or ""
    start_time = params.get("start_time") or ""
    end_time = params.get("end_time") or ""
    if not query or not start_time or not end_time:
        return _json_error(400, "query, start_time and end_time are required", request)
    limit = _int_param(request, "limit", DEFAULT_TWEET_LIMIT, 1, MAX_TWEET_SEARCH_LIMIT)
    if limit is None:
        return _json_error(400, "limit out of range", request)
    try:
        parsed = _parse_filters(params.get("filters") or "")
    except HTTPException as exc:
        return _json_error(exc.status_code, str(exc.detail), request)
    try:
        rows = ctx.search_tweets(
            query, start_time, end_time, filters=parsed, limit=limit
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X app tweet search failed for {query!r} ({exc})")
        return _json_error(502, "tweet search failed", request)
    return JSONResponse(
        {
            "rows": rows,
            "count": len(rows),
            "limit": limit,
            "truncated": len(rows) >= limit,
        },
        headers=_frame_ancestor_headers(request),
    )


def _handle_tweet_values(ctx: SnapshotContext, request: Request) -> Response:
    """Distinct values + counts for one faceted column."""
    params = request.query_params
    query = params.get("query") or ""
    start_time = params.get("start_time") or ""
    end_time = params.get("end_time") or ""
    column = params.get("column") or ""
    if not query or not start_time or not end_time:
        return _json_error(400, "query, start_time and end_time are required", request)
    if column not in TWEET_FACET_COLUMNS:
        return _json_error(
            400, f"column must be one of {', '.join(TWEET_FACET_COLUMNS)}", request
        )
    limit = _int_param(request, "limit", 500, 1, 2000)
    if limit is None:
        return _json_error(400, "limit out of range", request)
    try:
        parsed = _parse_filters(params.get("filters") or "")
    except HTTPException as exc:
        return _json_error(exc.status_code, str(exc.detail), request)
    try:
        values = ctx.distinct_column_values(
            query,
            start_time,
            end_time,
            column,
            contains=params.get("contains") or "",
            filters=parsed,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X app column values failed for {query!r} ({exc})")
        return _json_error(502, "column values failed", request)
    return JSONResponse(
        {"column": column, "values": values, "truncated": len(values) >= limit},
        headers=_frame_ancestor_headers(request),
    )


def _handle_user_search(ctx: SnapshotContext, request: Request) -> Response:
    """Authors matching a username substring — graph-wide, no query or window."""
    contains = request.query_params.get("contains") or ""
    limit = _int_param(request, "limit", DEFAULT_USER_LIMIT, 1, DEFAULT_USER_LIMIT)
    if limit is None:
        return _json_error(400, "limit out of range", request)
    try:
        users = ctx.find_users(contains, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X app user search failed for {contains!r} ({exc})")
        return _json_error(502, "user search failed", request)
    return JSONResponse(
        {"users": users, "count": len(users), "truncated": len(users) >= limit},
        headers=_frame_ancestor_headers(request),
    )


def _handle_user_posts(ctx: SnapshotContext, request: Request) -> Response:
    """One page of an author's posts (newest first) plus their graph totals."""
    username = request.query_params.get("username") or ""
    if not username:
        return _json_error(400, "username is required", request)
    limit = _int_param(
        request, "limit", DEFAULT_USER_POSTS_PAGE, 1, MAX_USER_POSTS_PAGE
    )
    offset = _int_param(request, "offset", 0, 0, 1_000_000)
    if limit is None or offset is None:
        return _json_error(400, "limit or offset out of range", request)
    try:
        profile = ctx.user_profile(username)
        rows = ctx.tweets_by_username(username, limit=limit, offset=offset)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X app user posts failed for {username!r} ({exc})")
        return _json_error(502, "user posts failed", request)
    return JSONResponse(
        {
            "username": username,
            "profile": profile,
            "rows": rows,
            "count": len(rows),
            "total": profile.get("posts", 0),
            "limit": limit,
            "offset": offset,
        },
        headers=_frame_ancestor_headers(request),
    )


# Relative path (under /app-html/x/apps/x/) → handler. Served by the middleware.
API_HANDLERS: dict[str, Callable[[SnapshotContext, Request], Response]] = {
    "api/tweets": _handle_tweet_search,
    "api/tweets/values": _handle_tweet_values,
    "api/users": _handle_user_search,
    "api/users/posts": _handle_user_posts,
}
