"""Serve the X Recent Tweets dashboard + its dataset from object storage.

Published layout under ``x/apps/x_proxy/``::

    index.html
    posts/get-posts-counts-recent/index.html  (+ index.txt)
    posts/search-posts-recent/index.html      (+ index.txt)
    users/search/index.html                   (+ index.txt)
    parameters/index.html                     (+ index.txt)
    _next/static/...
    globals/*.json
    count_recent_tweets/*.json
    search_recents_tweets/*.json
    search_users/users.json
    search_users/shards.json
    search_users/posts/<shard>.json

Each page of the app is a real path, exported as its own ``index.html`` (plus
the ``index.txt`` payload the client router fetches when moving between pages
without a reload), so a deep link opens on that page directly.

Everything the app reads is a published object: there is no SPARQL at request
time, so the API process needs no triple store and a page load costs one GET per
file instead of a graph query. The publisher
(``api.publish.publish_app``) is what refreshes these, and the ingestion
orchestrations run it after every pipeline run.

Served through ``/app-html/x/apps/x_proxy/…`` before the Nexus static catch-all.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import threading
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
)
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.apps.x_proxy.cache.reader import (
        CacheReader,
    )

APP_HTML_INDEX_PATH = "/app-html/x/apps/x_proxy/index.html"
APP_HTML_INDEX_DIR = "/app-html/x/apps/x_proxy/"
APP_HTML_PREFIX = "/app-html/x/apps/x_proxy/"
# Pre-rename publish lived here. Catalog URLs moved to x_proxy before the
# objects were re-uploaded, so look here when the new prefix is empty.
LEGACY_APP_PREFIX = "x/apps/x"
LEGACY_APP_HTML_INDEX_PATH = "/app-html/x/apps/x/index.html"
LEGACY_APP_HTML_INDEX_DIR = "/app-html/x/apps/x/"
LEGACY_APP_HTML_PREFIX = "/app-html/x/apps/x/"
# Dataset JSON. ``search_users/posts/<shard>.json`` is one level deeper than the
# page snapshots, hence the optional second segment.
_SNAPSHOT_RE = re.compile(
    r"^(globals|count_recent_tweets|search_recents_tweets|search_tweets|search_users)"
    r"(/[A-Za-z0-9_-]+)?/[A-Za-z0-9_.-]+\.json$"
)
_DIRECT_ARTIFACT_RE = re.compile(
    r"^(?:posts/by-id/\d+/(?:post\.json|media/[a-f0-9]{64}\.[a-z0-9]{1,5})"
    r"|users/by-handle/[a-z0-9_]{1,64}/"
    r"(?:user\.json|media/(?:avatar|banner)-[a-f0-9]{64}\.[a-z0-9]{1,5}))$"
)
_DATASET_MEDIA_RE = re.compile(
    r"^dataset/media/[A-Za-z0-9_:-]{1,128}/[a-f0-9]{64}\.[a-z0-9]{1,5}$"
)
# Legacy data/*.json paths (older hub publishes) - keep serving if present.
_LEGACY_DATA_RE = re.compile(r"^data/[A-Za-z0-9_.-]+\.json$")
# Next.js static export assets (hashed JS/CSS under _next/static/...).
_ASSET_RE = re.compile(
    r"^(_next/[A-Za-z0-9_./-]+|favicon\.ico|robots\.txt|manifest\.json|[A-Za-z0-9_.-]+\.(js|css|map|woff2?|ttf|svg|png|jpg|webp|ico))$"
)
# One page of the app: `users/search/` and the `users/search/index.txt` payload
# its client-side router fetches. Both come from the static export.
_ROUTE_DIR_RE = re.compile(r"^([A-Za-z0-9_-]+/)+$")
_ROUTE_PAYLOAD_RE = re.compile(r"^([A-Za-z0-9_-]+/)*index\.txt$")
# The same page asked for without the trailing slash the export publishes.
_ROUTE_UNSLASHED_RE = re.compile(r"^([A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+$")
# Next may fetch ``users/search.txt`` when the URL has no trailing slash.
# ``…/index.txt`` is the real export payload and must not be rewritten.
_ROUTE_UNSLASHED_PAYLOAD_RE = re.compile(
    r"^([A-Za-z0-9_-]+/)+(?!index\.txt$)[A-Za-z0-9_-]+\.txt$"
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


def _storage_prefixes(app_prefix: str, subdir: str | None = None) -> tuple[str, ...]:
    """Preferred object-storage prefix, then the other app root (rename fallback)."""
    primary = app_prefix.rstrip("/")
    alt = LEGACY_APP_PREFIX if primary == DEFAULT_APP_PREFIX else DEFAULT_APP_PREFIX
    if subdir:
        return (f"{primary}/{subdir}", f"{alt}/{subdir}")
    return (primary, alt)


def _serve_object(
    object_storage_service: ObjectStorageService,
    prefixes: tuple[str, ...] | str,
    name: str,
    media_type: str,
    request: Request,
) -> Response:
    if isinstance(prefixes, str):
        prefixes = (prefixes,)
    last_exc: Exceptions.ObjectNotFound | None = None
    for prefix in prefixes:
        try:
            content = object_storage_service.get_object(prefix, name)
        except Exceptions.ObjectNotFound as exc:
            last_exc = exc
            continue
        etag = f'"{hashlib.sha256(content).hexdigest()}"'
        headers = _frame_ancestor_headers(request)
        headers["ETag"] = etag
        full_path = f"{prefix}/{name}"
        if "/media/" in full_path or "/_next/static/" in full_path:
            headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(
            content=content,
            media_type=media_type,
            headers=headers,
        )
    raise HTTPException(status_code=404, detail=str(last_exc)) from last_exc


def _serve_relative(
    object_storage_service: ObjectStorageService,
    rel: str,
    request: Request,
    media_type: str | None = None,
    *,
    app_prefix: str = DEFAULT_APP_PREFIX,
) -> Response:
    if "/" not in rel:
        return _serve_object(
            object_storage_service,
            _storage_prefixes(app_prefix),
            rel,
            media_type or _media_type(rel, "text/html; charset=utf-8"),
            request,
        )
    subdir, name = rel.rsplit("/", 1)
    return _serve_object(
        object_storage_service,
        _storage_prefixes(app_prefix, subdir),
        name,
        media_type or _media_type(name),
        request,
    )


def _html_rel(path: str) -> tuple[str, str] | None:
    """Return ``(object-storage app prefix, relative path)`` for a catalog URL."""
    if path in (APP_HTML_INDEX_PATH, APP_HTML_INDEX_DIR):
        return DEFAULT_APP_PREFIX, ""
    if path.startswith(APP_HTML_PREFIX):
        return DEFAULT_APP_PREFIX, path[len(APP_HTML_PREFIX) :]
    if path in (LEGACY_APP_HTML_INDEX_PATH, LEGACY_APP_HTML_INDEX_DIR):
        return LEGACY_APP_PREFIX, ""
    if path.startswith(LEGACY_APP_HTML_PREFIX):
        return LEGACY_APP_PREFIX, path[len(LEGACY_APP_HTML_PREFIX) :]
    return None


class XCountAppMiddleware(BaseHTTPMiddleware):
    """Serve the dashboard index, its static assets and its JSON dataset.

    Implemented as middleware rather than plain FastAPI routes because Nexus
    registers a ``/app-html/{path:path}`` static catch-all ahead of this
    module's routes: anything left to normal routing is answered by that
    catch-all with "App HTML not found" before it can reach us. Middleware runs
    before the router, so this is the only ordering that holds.
    """

    def __init__(
        self,
        app,
        object_storage_service: ObjectStorageService,
        *,
        dataset: IDatasetPort | None = None,
        module: ABIModule | None = None,
    ) -> None:
        super().__init__(app)
        self._object_storage = object_storage_service
        self._dataset = dataset
        self._module = module
        self._search_reader: CacheReader | None = None
        self._search_state: dict = {}
        self._search_lock = threading.Lock()

    def _dataset_read_enabled(self) -> bool:
        if self._module is None or self._dataset is None:
            return False
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
            x_dataset_read_enabled,
        )

        return x_dataset_read_enabled(self._module)

    def _dataset_graph_totals(self) -> bytes:
        from datetime import UTC, datetime

        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import (
            api as ds_api,
        )

        totals = ds_api.graph_totals(self._dataset)
        doc = {
            "updated_at": datetime.now(UTC).isoformat(),
            **totals,
        }
        return json.dumps(doc, separators=(",", ":")).encode()

    def _dataset_search_tweets(self, query: str, page: int, per_page: int) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import (
            api as ds_api,
        )

        total, posts = ds_api.search_tweets(
            self._dataset,
            query,
            offset=page * per_page,
            limit=per_page,
        )
        return json.dumps(
            {
                "count": total,
                "page": page,
                "per_page": per_page,
                "posts": ds_api.serialize_search_posts(posts),
            },
            separators=(",", ":"),
            default=str,
        ).encode()

    def _dataset_users_search(self, query: str, page: int, per_page: int) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import (
            api as ds_api,
        )

        total, rows = ds_api.search_users(
            self._dataset,
            query,
            offset=page * per_page,
            limit=per_page,
        )
        return json.dumps(
            {"count": total, "page": page, "per_page": per_page, "users": rows},
            separators=(",", ":"),
            default=str,
        ).encode()

    def _cached_dataset_search_response(
        self,
        if_none_match: str | None,
        scope: str,
        query: str,
        page: int,
        per_page: int,
    ) -> tuple[int, bytes, dict[str, str]]:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.read_cache import (
            SearchScope,
            cached_search_response,
            optional_module_kv,
            read_cache_generation,
        )

        kv = optional_module_kv(self._module)
        generation = read_cache_generation(self._dataset, kv=kv)
        typed_scope: SearchScope = "posts" if scope == "posts" else "users"

        def compute_body() -> bytes:
            if typed_scope == "posts":
                return self._dataset_search_tweets(query, page, per_page)
            return self._dataset_users_search(query, page, per_page)

        return cached_search_response(
            if_none_match=if_none_match,
            generation=generation,
            scope=typed_scope,
            query=query,
            page=page,
            per_page=per_page,
            compute_body=compute_body,
        )

    def _dataset_user_posts(
        self, username: str, page: int, per_page: int, kind: str | None
    ) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import (
            api as ds_api,
        )

        profile, total, posts = ds_api.user_posts(
            self._dataset,
            username,
            offset=page * per_page,
            limit=per_page,
            kind=kind,
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="user not found")
        return json.dumps(
            {
                "profile": profile,
                "count": total,
                "page": page,
                "per_page": per_page,
                "posts": posts,
            },
            separators=(",", ":"),
            default=str,
        ).encode()

    def _dataset_post(self, tweet_id: str) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import (
            api as ds_api,
        )

        post = ds_api.post_by_id(self._dataset, tweet_id)
        if post is None:
            raise HTTPException(status_code=404, detail="post not found")
        return json.dumps({"post": post}, separators=(",", ":"), default=str).encode()

    def _dataset_ensure_post_media(self, tweet_id: str) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_resolve import (
            ensure_tweet_media,
        )
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker import (
            DEFAULT_MAX_BYTES,
        )

        app_cfg = getattr(self._module.configuration, "app", None) if self._module else None
        dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
        max_bytes = int(
            getattr(dataset_cfg, "media_max_bytes", DEFAULT_MAX_BYTES)
            if dataset_cfg
            else DEFAULT_MAX_BYTES
        )
        doc = ensure_tweet_media(
            self._dataset,
            self._object_storage,
            tweet_id,
            max_bytes=max_bytes,
        )
        return json.dumps(doc, separators=(",", ":")).encode()

    def _search_tweets(self, query: str, page: int, per_page: int) -> bytes:
        from naas_abi_marketplace.applications.x.apps.x_proxy.cache.reader import (
            CacheReader,
        )

        with self._search_lock:
            current = CacheReader(self._object_storage)
            state = current.projection_state()
            if self._search_reader is None or state != self._search_state:
                reader = current
                self._search_reader = reader
                self._search_state = state
            else:
                reader = self._search_reader
            total, posts = reader.search_tweets(
                query,
                offset=page * per_page,
                limit=per_page,
            )
        return json.dumps(
            {
                "count": total,
                "page": page,
                "per_page": per_page,
                "posts": posts,
            },
            separators=(",", ":"),
        ).encode()

    def _index(self, request: Request, *, app_prefix: str = DEFAULT_APP_PREFIX):
        return _serve_object(
            self._object_storage,
            _storage_prefixes(app_prefix),
            "index.html",
            "text/html; charset=utf-8",
            request,
        )

    def _page(
        self, rel: str, request: Request, *, app_prefix: str = DEFAULT_APP_PREFIX
    ):
        """The exported HTML for one page of the app.

        A page the current publish does not carry falls back to the app root,
        which boots the client app and forwards from there - an old bookmark
        lands on the dashboard rather than on a 404. Raises 404 only when even
        the root is missing, i.e. nothing has been published yet.
        """
        try:
            return _serve_relative(
                self._object_storage,
                f"{rel}index.html",
                request,
                "text/html; charset=utf-8",
                app_prefix=app_prefix,
            )
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        return self._index(request, app_prefix=app_prefix)

    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)

        matched = _html_rel(request.url.path)
        if matched is None:
            return await call_next(request)
        app_prefix, rel = matched

        if rel == "dataset/posts/search.json":
            query = str(request.query_params.get("q") or "")[:200]
            try:
                page = max(0, int(request.query_params.get("page") or 0))
                per_page = max(
                    1, min(100, int(request.query_params.get("per_page") or 100))
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="page and per_page must be integers"
                ) from exc
            if not self._dataset_read_enabled():
                raise HTTPException(
                    status_code=503,
                    detail="X Proxy dataset read path is disabled",
                )
            status, content, cache_headers = await run_in_threadpool(
                self._cached_dataset_search_response,
                request.headers.get("if-none-match"),
                "posts",
                query,
                page,
                per_page,
            )
            return Response(
                content=content,
                status_code=status,
                media_type="application/json; charset=utf-8",
                headers={
                    **_frame_ancestor_headers(request),
                    **cache_headers,
                },
            )

        if self._dataset_read_enabled() and rel == "globals/graph.json":
            content = await run_in_threadpool(self._dataset_graph_totals)
            return Response(
                content=content,
                media_type="application/json; charset=utf-8",
                headers={
                    **_frame_ancestor_headers(request),
                    "Cache-Control": "private, max-age=60",
                },
            )

        if rel == "dataset/users/search.json":
            query = str(request.query_params.get("q") or "")[:200]
            try:
                page = max(0, int(request.query_params.get("page") or 0))
                per_page = max(
                    1, min(100, int(request.query_params.get("per_page") or 100))
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="page and per_page must be integers"
                ) from exc
            if not self._dataset_read_enabled():
                raise HTTPException(
                    status_code=503,
                    detail="X Proxy dataset read path is disabled",
                )
            status, content, cache_headers = await run_in_threadpool(
                self._cached_dataset_search_response,
                request.headers.get("if-none-match"),
                "users",
                query,
                page,
                per_page,
            )
            return Response(
                content=content,
                status_code=status,
                media_type="application/json; charset=utf-8",
                headers={
                    **_frame_ancestor_headers(request),
                    **cache_headers,
                },
            )

        if self._dataset_read_enabled() and rel.startswith("dataset/users/"):
            suffix = rel[len("dataset/users/") :]
            if suffix.endswith("/posts.json"):
                username = suffix[: -len("/posts.json")]
                kind = str(request.query_params.get("kind") or "") or None
                if kind not in (None, "matched", "referenced"):
                    raise HTTPException(status_code=400, detail="invalid kind")
                try:
                    page = max(0, int(request.query_params.get("page") or 0))
                    per_page = max(
                        1, min(200, int(request.query_params.get("per_page") or 100))
                    )
                except ValueError as exc:
                    raise HTTPException(
                        status_code=400, detail="page and per_page must be integers"
                    ) from exc
                content = await run_in_threadpool(
                    self._dataset_user_posts, username, page, per_page, kind
                )
                return Response(
                    content=content,
                    media_type="application/json; charset=utf-8",
                    headers={
                        **_frame_ancestor_headers(request),
                        "Cache-Control": "private, max-age=15",
                    },
                )

        if self._dataset_read_enabled() and rel.startswith("dataset/posts/"):
            suffix = rel[len("dataset/posts/") :]
            if suffix.endswith("/media.json"):
                tweet_id = suffix[: -len("/media.json")]
                if not tweet_id.isdigit():
                    raise HTTPException(status_code=400, detail="invalid tweet id")
                content = await run_in_threadpool(
                    self._dataset_ensure_post_media, tweet_id
                )
                return Response(
                    content=content,
                    media_type="application/json; charset=utf-8",
                    headers={
                        **_frame_ancestor_headers(request),
                        "Cache-Control": "private, max-age=31536000, immutable",
                    },
                )
            tweet_id = suffix.removesuffix(".json")
            if not tweet_id.isdigit():
                raise HTTPException(status_code=400, detail="invalid tweet id")
            content = await run_in_threadpool(self._dataset_post, tweet_id)
            return Response(
                content=content,
                media_type="application/json; charset=utf-8",
                headers={
                    **_frame_ancestor_headers(request),
                    "Cache-Control": "private, max-age=60",
                },
            )

        if self._dataset_read_enabled() and _DATASET_MEDIA_RE.fullmatch(rel):
            from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_resolve import (
                object_storage_prefix_for_public_rel,
            )

            mapped = object_storage_prefix_for_public_rel(rel)
            if mapped is None:
                raise HTTPException(status_code=404, detail="media not found")
            prefix, name = mapped
            return _serve_object(
                self._object_storage,
                prefix,
                name,
                _media_type(name),
                request,
            )

        if not rel or rel == "index.html":
            try:
                return self._index(request, app_prefix=app_prefix)
            except HTTPException as exc:
                if exc.status_code == 404:
                    # Nothing published yet - let the Nexus catch-all answer.
                    return await call_next(request)
                raise

        if _ROUTE_DIR_RE.fullmatch(rel):
            try:
                return self._page(rel, request, app_prefix=app_prefix)
            except HTTPException as exc:
                if exc.status_code == 404:
                    return await call_next(request)
                raise

        if _ROUTE_UNSLASHED_PAYLOAD_RE.fullmatch(rel):
            payload = f"{rel[:-4]}/index.txt"
        elif _ROUTE_PAYLOAD_RE.fullmatch(rel):
            payload = rel
        else:
            payload = None
        if payload is not None:
            try:
                return _serve_relative(
                    self._object_storage,
                    payload,
                    request,
                    "text/plain; charset=utf-8",
                    app_prefix=app_prefix,
                )
            except HTTPException as exc:
                # An older publish carries no payloads. Falling through leaves
                # the catch-all to answer, and the client router falls back to
                # a full page load - raising here would surface as a 500,
                # because exception handlers do not wrap middleware.
                if exc.status_code == 404:
                    return await call_next(request)
                raise

        if self._dataset_read_enabled() and (
            rel.startswith("search_users/") or rel.startswith("search_tweets/")
        ):
            raise HTTPException(
                status_code=410,
                detail=(
                    "Legacy search JSON is disabled; use "
                    "dataset/posts/search.json or dataset/users/search.json"
                ),
            )

        if _SNAPSHOT_RE.fullmatch(rel) or _LEGACY_DATA_RE.fullmatch(rel):
            return _serve_relative(
                self._object_storage,
                rel,
                request,
                "application/json; charset=utf-8",
                app_prefix=app_prefix,
            )

        if _DIRECT_ARTIFACT_RE.fullmatch(rel):
            return _serve_relative(
                self._object_storage,
                rel,
                request,
                app_prefix=app_prefix,
            )

        if _ASSET_RE.fullmatch(rel):
            return _serve_relative(
                self._object_storage, rel, request, app_prefix=app_prefix
            )

        # `…/users/search` - serve the page without bouncing to the slashed
        # form, so the URL can be ``search?user=`` rather than ``search/?user=``.
        if _ROUTE_UNSLASHED_RE.fullmatch(rel):
            try:
                return self._page(f"{rel}/", request, app_prefix=app_prefix)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
            return await call_next(request)

        return await call_next(request)


def register_x_count_app_routes(
    app: FastAPI,
    object_storage_service: ObjectStorageService,
    *,
    dataset=None,
    module=None,
) -> None:
    """Mount the dashboard middleware.

    Object storage is the only dependency: the app is served entirely from the
    published dataset, so no triple store is needed in the API process.

    ``signals.x`` loads the same routes but has no ``app.dataset`` flags; only
    register once from ``naas_abi_marketplace.applications.x`` so dataset read
    is not shadowed by a second middleware layer.
    """
    if module is not None and type(module).__module__ != "naas_abi_marketplace.applications.x":
        return
    if getattr(app.state, "x_count_app_middleware_registered", False):
        return
    app.add_middleware(
        XCountAppMiddleware,
        object_storage_service=object_storage_service,
        dataset=dataset,
        module=module,
    )
    app.state.x_count_app_middleware_registered = True
