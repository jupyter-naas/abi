"""The Recent Tweets app: an ASGI app the X module serves with ``expose_app``.

Nexus forwards ``/app-remote/<grant>/applications.x/x_proxy/<path>`` to the
module, which serves the files of ``apps/x_proxy/`` itself (only its
``manifest.json``: nothing there) and hands everything else to this app, with
``root_path`` set to the path the browser sees. The app serves what the
in-engine routes served under ``/app-html/x/apps/x_proxy/``:

- the published Next.js export and JSON snapshots, from object storage under
  ``x/apps/x_proxy/`` (``x/apps/x``, the pre-rename prefix, as a fallback for
  the JSON snapshots only)::

      index.html, <page>/index.html (+ index.txt router payloads), _next/...,
      globals/*.json, count_recent_tweets/*.json, search_recents_tweets/*.json,
      data/*.json (legacy), posts/by-id/<id>/..., users/by-handle/<h>/...

- the dataset-backed JSON (when ``app.dataset.read_enabled``):
  ``globals/graph.json``, ``dataset/posts/search.json``,
  ``dataset/users/search.json``, ``dataset/users/<handle>/posts.json``,
  ``dataset/posts/<id>.json``, ``dataset/posts/<id>/media.json`` (downloads
  pending media on first view) and ``dataset/media/<key>/<file>``.

**Base path.** The export is built with a placeholder ``basePath``
(``APP_ROOT_PLACEHOLDER``, ``web/next.config.js``), because the grant in the
path changes per session. Every text response (HTML, scripts, styles, router
payloads, JSON) has the placeholder replaced by the request's ``root_path``, so
``<Link>`` hrefs, ``_next/`` assets and the app's own ``fetch`` URLs carry the
grant. So has the in-engine export's base (``LEGACY_BASE_PATH``), which an
installation upgraded from it still holds until the module publishes its own
(at start, ``flows/maintenance.publish_web_export_at_start``). The ETag is
computed after the rewrite.

Each request's storage and dataset calls are blocking (``SyncModule``): they run
on the module's threads (``module.sync.call``), never on the module's event loop
nor on its default executor.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from naas_abi_apps.x.services import ObjectNotFound
from naas_abi_apps.x.x_proxy.api.common import DEFAULT_APP_PREFIX
from naas_abi_sdk.services.errors import ServiceError

# Keep equal to ``basePath`` in web/next.config.js and APP_BASE in
# web/src/lib/base.ts.
APP_ROOT_PLACEHOLDER = "/__x_proxy_app_root__"
# The in-engine export's ``basePath`` (served by the engine's /app-html route).
LEGACY_BASE_PATH = "/app-html/x/apps/x_proxy"
# Each build base, plain and JSON-escaped (``\/...``); the escaped spelling
# first, since rewriting the plain one would not see it.
_BASES = tuple(
    spelling
    for base in (APP_ROOT_PLACEHOLDER, LEGACY_BASE_PATH)
    for spelling in (base.replace("/", "\\/").encode(), base.encode())
)

# Pre-rename publish lived here. Only its JSON snapshots are still read from it:
# its HTML and scripts were built for another base and other routes.
LEGACY_APP_PREFIX = "x/apps/x"
# Shown at the app's root while nothing is published.
FALLBACK_INDEX = Path(__file__).resolve().parent / "index.html"

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
# Largest page the dataset search endpoints serve - and the page the app asks
# for, which is what makes the unsearched listings worth warming.
_MAX_SEARCH_PER_PAGE = 100
_GRAPH_TOTALS_KEY = ("graph",)
# Legacy data/*.json paths (older hub publishes) - keep serving if present.
_LEGACY_DATA_RE = re.compile(r"^data/[A-Za-z0-9_.-]+\.json$")
# Next.js static export assets (hashed JS/CSS under _next/static/...).
_ASSET_RE = re.compile(
    r"^(_next/[A-Za-z0-9_./-]+|favicon\.ico|robots\.txt|manifest\.json"
    r"|[A-Za-z0-9_.-]+\.(js|css|map|woff2?|ttf|svg|png|jpg|webp|ico))$"
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
_TEXT_TYPES = ("text/", "application/javascript", "application/json")
_HTML = "text/html; charset=utf-8"
_JSON = "application/json; charset=utf-8"
_TEXT = "text/plain; charset=utf-8"


class NotPublished(Exception):
    """Neither prefix holds the object."""


def browser_root(root_path: str) -> str:
    """``root_path`` as it may go into HTML, scripts and JSON: percent-encoded
    outside an unreserved set, so a path can never close a string or a tag."""
    return quote(root_path.rstrip("/"), safe="/-._~%")


def rewrite_root(content: bytes, root: str) -> bytes:
    """``content`` with the build's base path (the placeholder, or the in-engine
    export's ``LEGACY_BASE_PATH``) replaced by ``root``, plain and JSON-escaped."""
    found = [base for base in _BASES if base in content]
    if not found:
        return content
    plain, escaped = root.encode(), root.replace("/", "\\/").encode()
    for base in found:
        content = content.replace(base, escaped if b"\\/" in base else plain)
    return content


def _safe_rel(rel: str) -> bool:
    """Whether every segment of ``rel`` is a name: no ``.``, ``..`` or empty
    segment (one trailing slash, a page directory, is allowed)."""
    if not rel:
        return True
    segments = rel.split("/")
    if segments[-1] == "":
        segments.pop()
    return all(segment not in ("", ".", "..") for segment in segments)


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
        return _JSON
    return default


def _storage_prefixes(
    subdir: str | None = None, *, legacy: bool = False
) -> tuple[str, ...]:
    """Where the app's object ``subdir/...`` is read: the current prefix, then
    the pre-rename one with ``legacy`` (JSON snapshots only)."""
    roots = (DEFAULT_APP_PREFIX, LEGACY_APP_PREFIX) if legacy else (DEFAULT_APP_PREFIX,)
    return tuple(f"{root}/{subdir}" if subdir else root for root in roots)


def _invalid_path(error: BaseException) -> bool:
    """The object storage refusing a key or prefix (``INVALID_ARGUMENT``)."""
    return isinstance(error, ServiceError) and error.code == "INVALID_ARGUMENT"


def _int_param(request: Request, name: str, default: int) -> int:
    try:
        return int(request.query_params.get(name) or default)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="page and per_page must be integers"
        ) from exc


class XProxyApp:
    """The request handling, over the module's blocking services."""

    def __init__(self, module: Any) -> None:
        self._module = module
        self._warmed_generation: str | None = None

    # -- the module's services (blocking; from worker threads only) -----------

    @property
    def sync(self) -> Any:
        """The ``SyncModule``: ``module.sync`` once the module initialized."""
        return getattr(self._module, "sync", None) or self._module

    @property
    def storage(self) -> Any:
        return self.sync.engine.services.object_storage

    @property
    def dataset(self) -> Any:
        return self.sync.engine.services.dataset

    def dataset_read_enabled(self) -> bool:
        from naas_abi_apps.x.x_proxy.dataset.store import x_dataset_read_enabled

        return x_dataset_read_enabled(self.sync)

    # -- object storage --------------------------------------------------------

    def _object(self, prefixes: tuple[str, ...], name: str) -> tuple[str, bytes]:
        for prefix in prefixes:
            try:
                return prefix, self.storage.get_object(prefix, name)
            except ObjectNotFound:
                continue
            except ServiceError as error:
                # A path the store refuses is one that cannot be published.
                if _invalid_path(error):
                    raise NotPublished(name) from error
                raise
        raise NotPublished(name)

    def serve_object(
        self,
        prefixes: tuple[str, ...],
        name: str,
        media_type: str,
        request: Request,
        root: str,
    ) -> Response:
        prefix, content = self._object(prefixes, name)
        if media_type.startswith(_TEXT_TYPES):
            content = rewrite_root(content, root)
        etag = f'"{hashlib.sha256(content).hexdigest()}"'
        headers = {"ETag": etag}
        full_path = f"{prefix}/{name}"
        if "/media/" in full_path or "/_next/static/" in full_path:
            headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(content=content, media_type=media_type, headers=headers)

    def serve_relative(
        self,
        rel: str,
        request: Request,
        root: str,
        media_type: str | None = None,
        *,
        legacy: bool = False,
    ) -> Response:
        if "/" not in rel:
            return self.serve_object(
                _storage_prefixes(legacy=legacy),
                rel,
                media_type or _media_type(rel, _HTML),
                request,
                root,
            )
        subdir, name = rel.rsplit("/", 1)
        return self.serve_object(
            _storage_prefixes(subdir, legacy=legacy),
            name,
            media_type or _media_type(name),
            request,
            root,
        )

    def index(self, request: Request, root: str) -> Response:
        try:
            return self.serve_object(
                _storage_prefixes(), "index.html", _HTML, request, root
            )
        except NotPublished:
            # Nothing published yet: say how to publish rather than 404.
            content = FALLBACK_INDEX.read_bytes()
            return Response(
                content=rewrite_root(content, root),
                media_type=_HTML,
                headers={"Cache-Control": "no-cache"},
            )

    def page(self, rel: str, request: Request, root: str) -> Response:
        """The exported HTML for one page of the app.

        A page the current publish does not carry falls back to the app root,
        which boots the client app and forwards from there - an old bookmark
        lands on the dashboard rather than on a 404.
        """
        try:
            return self.serve_relative(f"{rel}index.html", request, root, _HTML)
        except NotPublished:
            return self.index(request, root)

    # -- dataset JSON ------------------------------------------------------------

    def graph_totals_body(self) -> bytes:
        from naas_abi_apps.x.x_proxy.dataset import api as ds_api

        doc = {
            "updated_at": datetime.now(UTC).isoformat(),
            **ds_api.graph_totals(self.dataset),
        }
        return json.dumps(doc, separators=(",", ":")).encode()

    def search_tweets_body(self, query: str, page: int, per_page: int) -> bytes:
        from naas_abi_apps.x.x_proxy.dataset import api as ds_api

        total, posts = ds_api.search_tweets(
            self.dataset, query, offset=page * per_page, limit=per_page
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

    def search_users_body(self, query: str, page: int, per_page: int) -> bytes:
        from naas_abi_apps.x.x_proxy.dataset import api as ds_api

        total, rows = ds_api.search_users(
            self.dataset, query, offset=page * per_page, limit=per_page
        )
        return json.dumps(
            {"count": total, "page": page, "per_page": per_page, "users": rows},
            separators=(",", ":"),
            default=str,
        ).encode()

    def user_posts_body(
        self, username: str, page: int, per_page: int, kind: str | None
    ) -> bytes:
        from naas_abi_apps.x.x_proxy.dataset import api as ds_api

        profile, total, posts = ds_api.user_posts(
            self.dataset,
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

    def post_body(self, tweet_id: str) -> bytes:
        from naas_abi_apps.x.x_proxy.dataset import api as ds_api

        post = ds_api.post_by_id(self.dataset, tweet_id)
        if post is None:
            raise HTTPException(status_code=404, detail="post not found")
        return json.dumps({"post": post}, separators=(",", ":"), default=str).encode()

    def post_media(self, tweet_id: str) -> dict[str, Any]:
        from naas_abi_apps.x.x_proxy.dataset.media_resolve import ensure_tweet_media
        from naas_abi_apps.x.x_proxy.dataset.media_worker import DEFAULT_MAX_BYTES

        app_cfg = getattr(self.sync.configuration, "app", None)
        dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
        max_bytes = int(
            getattr(dataset_cfg, "media_max_bytes", DEFAULT_MAX_BYTES)
            if dataset_cfg
            else DEFAULT_MAX_BYTES
        )
        return ensure_tweet_media(
            self.dataset, self.storage, tweet_id, max_bytes=max_bytes
        )

    def cached(
        self,
        request: Request,
        key: tuple[str, ...],
        compute_body: Callable[[], bytes],
    ) -> Response:
        from naas_abi_apps.x.x_proxy.dataset.read_cache import (
            cached_dataset_response,
            read_cache_generation,
        )

        generation = read_cache_generation(self.dataset)
        self.warm_landing_views(generation)
        status, content, headers = cached_dataset_response(
            if_none_match=request.headers.get("if-none-match"),
            generation=generation,
            key=key,
            compute_body=compute_body,
        )
        return Response(
            content=content, status_code=status, media_type=_JSON, headers=headers
        )

    def warm_landing_views(self, generation: str) -> None:
        """Recompute what every visit opens on as soon as a generation is seen.

        The graph totals gate the app's first paint, and the unsearched Users /
        Search Tweets listings are the landing views - refreshing them in the
        background keeps the first request after an ingest from waiting.
        """
        if generation == self._warmed_generation:
            return
        self._warmed_generation = generation
        from naas_abi_apps.x.x_proxy.dataset.read_cache import (
            SEARCH_RESPONSE_CACHE,
            search_cache_key,
        )

        per_page = _MAX_SEARCH_PER_PAGE
        views: list[tuple[tuple[str, ...], Callable[[], bytes]]] = [
            (_GRAPH_TOTALS_KEY, self.graph_totals_body),
            (
                search_cache_key("posts", "", 0, per_page),
                lambda: self.search_tweets_body("", 0, per_page),
            ),
            (
                search_cache_key("users", "", 0, per_page),
                lambda: self.search_users_body("", 0, per_page),
            ),
        ]
        for key, compute in views:
            SEARCH_RESPONSE_CACHE.refresh_async(generation, key, compute)

    def _search(self, request: Request, scope: str) -> Response:
        from naas_abi_apps.x.x_proxy.dataset.read_cache import search_cache_key

        query = str(request.query_params.get("q") or "")[:200]
        page = max(0, _int_param(request, "page", 0))
        per_page = max(
            1,
            min(
                _MAX_SEARCH_PER_PAGE,
                _int_param(request, "per_page", _MAX_SEARCH_PER_PAGE),
            ),
        )
        if not self.dataset_read_enabled():
            raise HTTPException(
                status_code=503, detail="X Proxy dataset read path is disabled"
            )
        if scope == "posts":
            return self.cached(
                request,
                search_cache_key("posts", query, page, per_page),
                lambda: self.search_tweets_body(query, page, per_page),
            )
        return self.cached(
            request,
            search_cache_key("users", query, page, per_page),
            lambda: self.search_users_body(query, page, per_page),
        )

    # -- dispatch ----------------------------------------------------------------

    def handle(self, rel: str, request: Request) -> Response:
        """Answer one GET / HEAD for ``rel``, the path below the app's root."""
        if not _safe_rel(rel):
            # ``_next/../..``, ``a//b``: never a published path, and never sent
            # to the object storage, which refuses it (``INVALID_ARGUMENT``).
            raise HTTPException(status_code=404, detail="Not found")
        root = browser_root(request.scope.get("root_path") or "")
        try:
            return self._handle(rel, request, root)
        except NotPublished as exc:
            raise HTTPException(status_code=404, detail="Not published") from exc

    def _handle(self, rel: str, request: Request, root: str) -> Response:
        if rel == "dataset/posts/search.json":
            return self._search(request, "posts")
        if rel == "dataset/users/search.json":
            return self._search(request, "users")

        read_enabled = self.dataset_read_enabled()
        if read_enabled and rel == "globals/graph.json":
            return self.cached(request, _GRAPH_TOTALS_KEY, self.graph_totals_body)

        if read_enabled and rel.startswith("dataset/users/"):
            suffix = rel[len("dataset/users/") :]
            if suffix.endswith("/posts.json"):
                username = suffix[: -len("/posts.json")]
                kind = str(request.query_params.get("kind") or "") or None
                if kind not in (None, "matched", "referenced"):
                    raise HTTPException(status_code=400, detail="invalid kind")
                page = max(0, _int_param(request, "page", 0))
                per_page = max(1, min(200, _int_param(request, "per_page", 100)))
                return self.cached(
                    request,
                    (
                        "user_posts",
                        username.strip().lstrip("@").casefold(),
                        str(page),
                        str(per_page),
                        kind or "",
                    ),
                    lambda: self.user_posts_body(username, page, per_page, kind),
                )

        if read_enabled and rel.startswith("dataset/posts/"):
            suffix = rel[len("dataset/posts/") :]
            if suffix.endswith("/media.json"):
                tweet_id = suffix[: -len("/media.json")]
                if not tweet_id.isdigit():
                    raise HTTPException(status_code=400, detail="invalid tweet id")
                doc = self.post_media(tweet_id)
                # Final once every media of the post is stored; until then the
                # next view asks again (a failed download is retried later).
                cache = (
                    "private, max-age=31536000, immutable"
                    if doc.get("complete")
                    else "no-cache"
                )
                return Response(
                    content=json.dumps(doc, separators=(",", ":")).encode(),
                    media_type=_JSON,
                    headers={"Cache-Control": cache},
                )
            tweet_id = suffix.removesuffix(".json")
            if not tweet_id.isdigit():
                raise HTTPException(status_code=400, detail="invalid tweet id")
            return self.cached(
                request, ("post", tweet_id), lambda: self.post_body(tweet_id)
            )

        if read_enabled and _DATASET_MEDIA_RE.fullmatch(rel):
            from naas_abi_apps.x.x_proxy.dataset.media_resolve import (
                object_storage_prefix_for_public_rel,
            )

            mapped = object_storage_prefix_for_public_rel(rel)
            if mapped is None:
                raise HTTPException(status_code=404, detail="media not found")
            prefix, name = mapped
            return self.serve_object((prefix,), name, _media_type(name), request, root)

        if not rel or rel == "index.html":
            return self.index(request, root)

        if _ROUTE_DIR_RE.fullmatch(rel):
            return self.page(rel, request, root)

        if _ROUTE_UNSLASHED_PAYLOAD_RE.fullmatch(rel):
            payload: str | None = f"{rel[:-4]}/index.txt"
        elif _ROUTE_PAYLOAD_RE.fullmatch(rel):
            payload = rel
        else:
            payload = None
        if payload is not None:
            # An older publish carries no payloads: 404, and the client router
            # falls back to a full page load.
            return self.serve_relative(payload, request, root, _TEXT)

        if read_enabled and rel.startswith(("search_users/", "search_tweets/")):
            raise HTTPException(
                status_code=410,
                detail=(
                    "Legacy search JSON is disabled; use "
                    "dataset/posts/search.json or dataset/users/search.json"
                ),
            )

        if _SNAPSHOT_RE.fullmatch(rel) or _LEGACY_DATA_RE.fullmatch(rel):
            return self.serve_relative(rel, request, root, _JSON, legacy=True)

        if _DIRECT_ARTIFACT_RE.fullmatch(rel) or _ASSET_RE.fullmatch(rel):
            return self.serve_relative(rel, request, root)

        # `…/users/search` - serve the page without bouncing to the slashed
        # form, so the URL can be ``search?user=`` rather than ``search/?user=``.
        if _ROUTE_UNSLASHED_RE.fullmatch(rel):
            return self.page(f"{rel}/", request, root)

        raise HTTPException(status_code=404, detail="Not found")


def create_app(module: Any) -> FastAPI:
    """The Recent Tweets ASGI app of ``module``: the X ``ABIModule`` once
    initialized, or anything whose ``sync`` has ``configuration``, blocking
    ``engine.services`` and ``call`` (``services.SyncModule``)."""
    handler = XProxyApp(module)
    app = FastAPI(
        title="X Proxy",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.x_proxy = handler

    @app.api_route("/{rel:path}", methods=["GET", "HEAD"])
    async def serve(rel: str, request: Request) -> Response:
        # The module's threads: not the loop's default executor (host-name
        # lookups), on which a request waiting for the loop would starve them.
        return await handler.sync.call(handler.handle, rel, request)

    return app
