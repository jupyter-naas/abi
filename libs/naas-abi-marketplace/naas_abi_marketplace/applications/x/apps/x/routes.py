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

from fastapi import FastAPI, HTTPException, Query, Request
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
    """Serve the dashboard index + assets + snapshot JSON before the static catch-all."""

    def __init__(self, app, object_storage_service: ObjectStorageService) -> None:
        super().__init__(app)
        self._object_storage = object_storage_service

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
    """Mount the static dashboard middleware plus the live tweet-search routes.

    *triple_store_service* is optional so an object-storage-only deployment
    keeps serving the published snapshots; without it the live search routes
    are simply not registered and the web app falls back to filtering the rows
    already in the snapshot.
    """
    if triple_store_service is not None:
        _register_tweet_search_routes(app, triple_store_service)
        _register_user_routes(app, triple_store_service)

    # Added last so it wraps (and is evaluated before) the routes above; the
    # middleware only intercepts snapshot/asset paths, so /api/* falls through.
    app.add_middleware(
        XCountAppMiddleware, object_storage_service=object_storage_service
    )


def _register_tweet_search_routes(
    app: FastAPI,
    triple_store_service: TripleStoreService,
) -> None:
    """Live SPARQL-backed search behind the Search page's tweet table.

    The published snapshot only carries the newest ``DEFAULT_TWEET_LIMIT``
    tweets per query + window. These routes re-query the graph so a column
    filter returns the newest matching tweets across the *whole* window rather
    than the matches that happen to fall inside that snapshot page.
    """

    def _context() -> SnapshotContext:
        # queries=[] — these routes take the query string per request.
        return SnapshotContext(None, triple_store_service, queries=[])  # type: ignore[arg-type]

    @app.get(TWEET_SEARCH_PATH, include_in_schema=False)
    def search_tweets(
        request: Request,
        query: str = Query(..., description="Followed query string."),
        start_time: str = Query(..., description="Window start (ISO-8601)."),
        end_time: str = Query(..., description="Window end (ISO-8601, exclusive)."),
        filters: str = Query("", description="JSON {column: {contains, values}}."),
        limit: int = Query(DEFAULT_TWEET_LIMIT, ge=1, le=MAX_TWEET_SEARCH_LIMIT),
    ) -> Response:
        parsed = _parse_filters(filters)
        try:
            rows = _context().search_tweets(
                query, start_time, end_time, filters=parsed, limit=limit
            )
        except Exception as exc:
            logger.warning(f"X app tweet search failed for {query!r} ({exc})")
            raise HTTPException(status_code=502, detail="tweet search failed") from exc
        return JSONResponse(
            {
                "rows": rows,
                "count": len(rows),
                "limit": limit,
                "truncated": len(rows) >= limit,
            },
            headers=_frame_ancestor_headers(request),
        )

    @app.get(TWEET_COLUMN_VALUES_PATH, include_in_schema=False)
    def tweet_column_values(
        request: Request,
        query: str = Query(..., description="Followed query string."),
        start_time: str = Query(..., description="Window start (ISO-8601)."),
        end_time: str = Query(..., description="Window end (ISO-8601, exclusive)."),
        column: str = Query(..., description="Column to enumerate."),
        contains: str = Query("", description="Narrow the value list."),
        filters: str = Query("", description="Other columns' active filters."),
        limit: int = Query(500, ge=1, le=2000),
    ) -> Response:
        if column not in TWEET_FACET_COLUMNS:
            raise HTTPException(
                status_code=400,
                detail=f"column must be one of {', '.join(TWEET_FACET_COLUMNS)}",
            )
        parsed = _parse_filters(filters)
        try:
            values = _context().distinct_column_values(
                query,
                start_time,
                end_time,
                column,
                contains=contains,
                filters=parsed,
                limit=limit,
            )
        except Exception as exc:
            logger.warning(
                f"X app column values failed for {query!r} column={column!r} ({exc})"
            )
            raise HTTPException(status_code=502, detail="column values failed") from exc
        return JSONResponse(
            {"column": column, "values": values, "truncated": len(values) >= limit},
            headers=_frame_ancestor_headers(request),
        )


def _register_user_routes(
    app: FastAPI,
    triple_store_service: TripleStoreService,
) -> None:
    """Graph-wide author lookup behind the Users page.

    Unlike the tweet-search routes these take no query or window: the Users
    page searches every author in the tweet graph and pages through all of a
    selected author's posts, newest first.
    """

    def _context() -> SnapshotContext:
        return SnapshotContext(None, triple_store_service, queries=[])  # type: ignore[arg-type]

    @app.get(USER_SEARCH_PATH, include_in_schema=False)
    def search_users(
        request: Request,
        contains: str = Query("", description="Username substring (empty = top)."),
        limit: int = Query(DEFAULT_USER_LIMIT, ge=1, le=DEFAULT_USER_LIMIT),
    ) -> Response:
        try:
            users = _context().find_users(contains, limit=limit)
        except Exception as exc:
            logger.warning(f"X app user search failed for {contains!r} ({exc})")
            raise HTTPException(status_code=502, detail="user search failed") from exc
        return JSONResponse(
            {"users": users, "count": len(users), "truncated": len(users) >= limit},
            headers=_frame_ancestor_headers(request),
        )

    @app.get(USER_POSTS_PATH, include_in_schema=False)
    def user_posts(
        request: Request,
        username: str = Query(..., min_length=1, description="Author username."),
        limit: int = Query(DEFAULT_USER_POSTS_PAGE, ge=1, le=MAX_USER_POSTS_PAGE),
        offset: int = Query(0, ge=0),
    ) -> Response:
        ctx = _context()
        try:
            profile = ctx.user_profile(username)
            rows = ctx.tweets_by_username(username, limit=limit, offset=offset)
        except Exception as exc:
            logger.warning(f"X app user posts failed for {username!r} ({exc})")
            raise HTTPException(status_code=502, detail="user posts failed") from exc
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
