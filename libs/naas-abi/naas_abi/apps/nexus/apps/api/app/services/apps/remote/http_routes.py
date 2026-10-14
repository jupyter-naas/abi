"""Browser requests to a remote module's app, forwarded over NATS
(docs/adr/20261012_remote-module-apps.md).

* ``/app-remote/<grant>/<module_id>/<app>/<path>`` serves the app. The page
  runs sandboxed in an opaque origin (``SANDBOX``), away from the Nexus session,
  so the browser sends it no cookie: the grant in the path is its credential
  (``grant.py``), and relative URLs carry it.
* ``/app-html/remote/<module_id>/<app>/<path>``, the catalog URL, runs the
  usual ``/app-html/`` access check and redirects to a fresh grant.

The module gets the user's id, never the user's credential. Headers pass on
allow-lists both ways. The module's cookies stay on its own path, under names
of their own, and only those come back to it.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config
from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
    get_remote_app_directory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
    GRANT_ROUTE_PREFIX,
    grant_root,
    is_segment,
    mint_remote_app_grant,
    read_remote_app_grant,
    redact_grant_path,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    INLINE_BYTES,
    MAX_UPLOADS_PER_MODULE,
    AppRequest,
    RemoteAppUnavailable,
)
from naas_abi_core.apps.api.abi_api_key_auth import (
    APP_HTML_TOKEN_COOKIE,
    extract_abi_api_token,
)
from starlette.types import ASGIApp, Receive, Scope, Send

_log = logging.getLogger(__name__)

METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
# No allow-same-origin: the page cannot reach the Nexus origin's storage, and
# the API takes nothing from it but the grant.
SANDBOX = "sandbox allow-scripts allow-forms allow-popups allow-downloads"
SECURITY_HEADERS = {
    "Content-Security-Policy": SANDBOX,
    # The page's URL holds the grant: no Referer carries it anywhere.
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    # From the opaque origin, the app's fetch() calls are cross-origin. They
    # carry no credential but the grant in their URL.
    "Access-Control-Allow-Origin": "*",
}

# Request headers the app may read: content negotiation, conditional and range
# requests, and its own x- headers. Never credentials or proxy headers.
_FORWARDED = frozenset({"content-type", "content-disposition", "range", "user-agent"})
_FORWARDED_PREFIXES = ("accept", "if-")
_NOT_THE_APPS = ("x-forwarded-", "x-real-ip", "x-api-key")
# Response headers the browser gets from the module, besides a same-app
# Location and app-scoped cookies. The content-* and range ones keep the
# forwarded Accept-Encoding and Range requests working.
_RETURNED = frozenset(
    {
        "content-type",
        "content-disposition",
        "cache-control",
        "etag",
        "last-modified",
        "vary",
        "content-encoding",
        "content-language",
        "content-range",
        "accept-ranges",
    }
)
# The module's cookies, renamed in the browser so that only they come back.
APP_COOKIE_PREFIX = "abi_app."


def _presented_user(request: Request) -> tuple[str, datetime | None]:
    """The signed-in user behind the request and when their credential
    expires; no user for an ABI_API_KEY caller."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    token = extract_abi_api_token(request)
    payload = decode_token(token) if token else None
    if not isinstance(payload, dict):
        return "", None
    subject, exp = payload.get("sub"), payload.get("exp")
    expires = datetime.fromtimestamp(exp, UTC) if isinstance(exp, int | float) else None
    return (subject if isinstance(subject, str) else ""), expires


def _is_forwarded(name: str) -> bool:
    if name in _FORWARDED or name.startswith(_FORWARDED_PREFIXES):
        return True
    return name.startswith("x-") and not name.startswith(_NOT_THE_APPS)


def _forwarded_headers(request: Request) -> tuple[tuple[str, str], ...]:
    headers = [
        (name, value) for name, value in request.headers.items() if _is_forwarded(name.lower())
    ]
    cookies = "; ".join(
        f"{name[len(APP_COOKIE_PREFIX) :]}={value}"
        for name, value in request.cookies.items()
        if name.startswith(APP_COOKIE_PREFIX) and len(name) > len(APP_COOKIE_PREFIX)
    )
    if cookies:
        headers.append(("cookie", cookies))
    return tuple(headers)


def _query(request: Request) -> str:
    return urlencode(
        [
            (key, value)
            for key, value in parse_qsl(request.url.query, keep_blank_values=True)
            if key != "token"
        ]
    )


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def _reinterpreted(path: str) -> bool:
    """Browsers read "%2e" as "." and "\\" as "/" when they resolve a path:
    a dot segment the check below cannot see. Such paths are refused."""
    lowered = path.lower()
    return "%2e" in lowered or "%5c" in lowered or "\\" in path


def _same_app_location(value: str, root: str, path: str) -> str | None:
    """A redirect that stays in the app, as an absolute path; else None."""
    target = urlsplit(value.strip())
    if target.scheme or target.netloc or _reinterpreted(target.path):
        return None
    resolved = urlsplit(urljoin(f"http://nexus{root}{path}", value.strip()))
    if resolved.netloc != "nexus" or not _within(resolved.path, root):
        return None
    location = resolved.path
    if resolved.query:
        location += f"?{resolved.query}"
    if resolved.fragment:
        location += f"#{resolved.fragment}"
    return location


def _app_cookie(value: str, root: str) -> str | None:
    """A cookie the module sets on its own path and host, renamed; else None."""
    name, separator, rest = value.partition("=")
    name = name.strip()
    if not separator or not name or name == APP_HTML_TOKEN_COOKIE:
        return None
    path = None
    for attribute in rest.split(";")[1:]:
        key, _, attribute_value = attribute.partition("=")
        key = key.strip().lower()
        if key == "domain":
            return None
        if key == "path":
            path = attribute_value.strip()
    if path is None or _reinterpreted(path) or not _within(path.rstrip("/") or "/", root):
        return None
    return f"{APP_COOKIE_PREFIX}{name}={rest}"


def _returned_headers(
    headers: tuple[tuple[str, str], ...], root: str, path: str = "/"
) -> list[tuple[str, str]]:
    returned = []
    for name, value in headers:
        lower = name.lower()
        if lower in _RETURNED:
            returned.append((name, value))
        elif lower == "location":
            location = _same_app_location(value, root, path)
            if location is not None:
                returned.append((name, location))
        elif lower == "set-cookie":
            cookie = _app_cookie(value, root)
            if cookie is not None:
                returned.append((name, cookie))
    return returned


class _Uploads:
    """Uploads streaming to each module from this worker (MAX_UPLOADS_PER_MODULE)."""

    def __init__(self) -> None:
        self.active: dict[str, int] = {}

    @contextlib.contextmanager
    def slot(self, module_id: str) -> Iterator[None]:
        if self.active.get(module_id, 0) >= MAX_UPLOADS_PER_MODULE:
            raise HTTPException(
                status_code=503, detail="Too many uploads to this app", headers=SECURITY_HEADERS
            )
        self.active[module_id] = self.active.get(module_id, 0) + 1
        try:
            yield
        finally:
            self.active[module_id] -= 1
            if not self.active[module_id]:
                del self.active[module_id]


_uploads = _Uploads()


async def _read_head(request: Request) -> tuple[bytes, AsyncIterator[bytes] | None]:
    """The whole body when it is small; else its first bytes and the rest,
    read only as the module pulls it."""
    stream = request.stream().__aiter__()
    head = bytearray()
    async for chunk in stream:
        head += chunk
        if len(head) > INLINE_BYTES:
            return b"", _rest(bytes(head), stream)
    return bytes(head), None


async def _rest(head: bytes, stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    yield head
    async for chunk in stream:
        if chunk:
            yield chunk


def _granted_user(grant: str, module_id: str, app: str) -> str:
    granted = read_remote_app_grant(grant, secret=current_secret_key())
    if granted is None or (granted.module_id, granted.app) != (module_id, app):
        raise HTTPException(
            status_code=401,
            detail="This app link has expired. Open the app again.",
            headers=SECURITY_HEADERS,
        )
    return granted.user_id


def _unavailable(module_id: str, app: str, exc: RemoteAppUnavailable) -> HTTPException:
    if exc.status >= 500:
        _log.warning("Remote app %s/%s: %s", module_id, app, exc.reason)
    return HTTPException(status_code=exc.status, detail=exc.reason, headers=SECURITY_HEADERS)


async def serve_remote_app(
    grant: str, module_id: str, app: str, path: str, request: Request
) -> Response:
    user_id = _granted_user(grant, module_id, app)
    root = grant_root(grant, module_id, app)
    directory = get_remote_app_directory()
    try:
        limit = await directory.upload_limit(module_id, app)
    except RemoteAppUnavailable as exc:
        raise _unavailable(module_id, app, exc) from exc
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(
            status_code=413, detail=f"Upload exceeds {limit} bytes", headers=SECURITY_HEADERS
        )
    body, rest = await _read_head(request)
    forwarded = AppRequest(
        method=request.method,
        path="/" + path,
        query=_query(request),
        headers=_forwarded_headers(request),
        body=body,
        user_id=user_id,
        body_stream=rest,
        max_body_bytes=limit if rest is not None else 0,
        root_path=root,
    )
    try:
        if rest is None:
            answer = await directory.forward(module_id, app, forwarded)
        else:
            with _uploads.slot(module_id):
                answer = await directory.forward(module_id, app, forwarded)
    except RemoteAppUnavailable as exc:
        raise _unavailable(module_id, app, exc) from exc
    if answer.body_stream is not None:
        response: Response = StreamingResponse(answer.body_stream, status_code=answer.status)
    else:
        response = Response(content=answer.body, status_code=answer.status)
    for name, value in _returned_headers(answer.headers, root, "/" + path):
        response.headers.append(name, value)
    response.headers.update(SECURITY_HEADERS)
    return response


async def redirect_remote_app_root(
    grant: str, module_id: str, app: str, request: Request
) -> Response:
    """``.../<app>`` -> ``.../<app>/``: relative links in the entry page resolve."""
    _granted_user(grant, module_id, app)
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        f"{request.url.path}/{query}", status_code=307, headers=SECURITY_HEADERS
    )


def remote_app_grant_url(
    user_id: str, module_id: str, app: str, not_after: datetime | None = None
) -> str:
    """The app's root under a fresh grant, ending with ``/``."""
    grant = mint_remote_app_grant(
        secret=current_secret_key(),
        user_id=user_id,
        module_id=module_id,
        app=app,
        minutes=nexus_config.settings.remote_app_grant_expire_minutes,
        not_after=not_after,
    )
    return grant_root(grant, module_id, app) + "/"


async def open_remote_app(module_id: str, app: str, request: Request, path: str = "") -> Response:
    """The catalog URL, after the ``/app-html/`` access check: the same page
    under a fresh grant, for the same user and no longer than the credential
    that was presented (a share link stays a share link)."""
    if not is_segment(module_id, app):
        raise HTTPException(status_code=404, detail="Not Found")
    user_id, expires = _presented_user(request)
    if not user_id:
        raise HTTPException(status_code=403, detail="A remote app opens for a signed-in user")
    query = _query(request)
    target = remote_app_grant_url(user_id, module_id, app, not_after=expires) + path
    return RedirectResponse(f"{target}?{query}" if query else target, status_code=307)


class RedactGrantFilter(logging.Filter):
    """Hides the grant in uvicorn's access log (its third argument is the path)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], redact_grant_path(args[2]), *args[3:])
        return True


def redact_grants_in_access_log() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactGrantFilter) for f in access.filters):
        access.addFilter(RedactGrantFilter())


class RemoteAppPreflight:
    """Answers CORS preflights of remote app pages (``Origin: null``) before
    the API's CORS middleware, which allows only the Nexus origins. Allowing
    any origin is safe here: no request to these routes carries a cookie or
    an Authorization, only the grant in its URL."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "OPTIONS"
            or not scope["path"].startswith(GRANT_ROUTE_PREFIX + "/")
        ):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        if "access-control-request-method" not in headers:
            await self.app(scope, receive, send)
            return
        response = Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": ", ".join(METHODS),
                "Access-Control-Allow-Headers": headers.get("access-control-request-headers", ""),
                "Access-Control-Max-Age": "600",
            },
        )
        await response(scope, receive, send)
