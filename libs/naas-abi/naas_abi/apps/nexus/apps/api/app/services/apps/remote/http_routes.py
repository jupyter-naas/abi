"""Browser requests to a remote module's app, forwarded over NATS
(docs/adr/20261012_remote-module-apps.md).

* ``/app-remote/<grant>/<module_id>/<app>/<path>`` serves the app. The page
  runs sandboxed in an opaque origin (``SANDBOX``), away from the Nexus session,
  so the browser sends it no cookie: the grant in the path is its credential
  (``grant.py``), and relative URLs carry it.
* ``/app-html/remote/<module_id>/<app>/<path>``, the catalog URL, runs the
  usual ``/app-html/`` access check and redirects a user to a fresh grant;
  an ``ABI_API_KEY`` caller (no user, no browser) is answered directly.

A grant names the workspace the app opens in (``access.py``) and ends when the
user logs out (``revocation.py``). The module gets the user's id and the
workspace, never the user's credential. Headers pass on allow-lists both ways.
The module's cookies stay on its own path, under names of their own, and only
those come back to it.
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime
from urllib.parse import unquote_plus, urljoin, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config
from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access, revocation
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
    get_remote_app_directory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
    GRANT_ROUTE_PREFIX,
    RemoteAppGrant,
    grant_root,
    is_segment,
    mint_remote_app_grant,
    read_remote_app_grant,
    redact_grant_path,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    INLINE_BYTES,
    MAX_STREAMS_PER_MODULE,
    MAX_UPLOADS_PER_MODULE,
    AppRequest,
    AppResponse,
    RemoteApp,
    RemoteAppStreamFailed,
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
    # carry no credential but the grant in their URL, and may read every
    # header the browser gets (the returned ones below).
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Expose-Headers": "*",
}

# Request headers the app may read: content negotiation, conditional and range
# requests, and its own x- headers. Never credentials or proxy headers.
_FORWARDED = frozenset({"content-type", "content-disposition", "range", "user-agent"})
_FORWARDED_PREFIXES = ("accept", "if-")
_NOT_THE_APPS = ("x-forwarded-", "x-real-ip", "x-api-key")
# Response headers the browser gets from the module, besides its x- headers,
# a same-app Location, app-scoped cookies and Content-Length. The content-*
# and range ones keep the forwarded Accept-Encoding and Range requests
# working; the others are an API's: rate limits, auth challenges, pagination.
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
        "retry-after",
        "www-authenticate",
        "link",
    }
)
# x- response headers that are not the app's to set: proxies, CDNs and edge
# runtimes in front of Nexus act on these (X-Accel-Redirect serves any file it
# names, X-Middleware-Rewrite reroutes), and Nexus sets framing and sniffing
# itself. A deny-list, not an allow-list: an app's API has headers of its own
# (request ids, rate limits) that no list could name. The deployments ABI
# ships (Caddy, Cloudflare) act on no x- response header.
_NOT_RETURNED = (
    "x-accel-",
    "x-sendfile",
    "x-lighttpd-",
    "x-litespeed-",
    "x-envoy-",
    "x-middleware-",
    "x-nextjs-",
    "x-vercel-",
    "x-nf-",
    "x-amz-",
    "x-amzn-",
    "x-goog-",
    "x-ms-",
    "x-azure-",
    "x-varnish",
    "x-cache",
    "x-original-",
    "x-rewrite-",
    "x-http-method-override",
    "x-forwarded-",
    "x-real-ip",
    "x-frame-options",
    "x-content-type-options",
)
# The module's cookies, renamed in the browser so that only they come back.
APP_COOKIE_PREFIX = "abi_app."
# RFC 6265 cookie names: an HTTP token.
_COOKIE_NAME = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
# Characters no header value may carry (they would split or end the header).
_BAD_VALUE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


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


def _presented_claims(request: Request) -> dict:
    """The claims of the Nexus credential behind the request; none for an
    ABI_API_KEY caller."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    token = extract_abi_api_token(request)
    payload = decode_token(token) if token else None
    return payload if isinstance(payload, dict) else {}


async def refuse_revoked_credential(user_id: str, request: Request) -> None:
    """401 when the credential was revoked or predates the user's latest
    logout: a logged-out browser's token or cookie mints no grant."""
    if await revocation.credential_revoked(user_id, _presented_claims(request)):
        raise HTTPException(
            status_code=401, detail="Sign in again to open this app", headers=SECURITY_HEADERS
        )


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


def _query(request: Request, *dropped: str) -> str:
    """The query as the browser sent it, byte for byte, without ``token`` (an
    access credential) and the ``dropped`` parameters (Nexus's own)."""
    names = {"token", *dropped}
    raw = request.scope.get("query_string", b"").decode("latin-1")
    return "&".join(
        part
        for part in raw.split("&")
        if part and unquote_plus(part.partition("=")[0]) not in names
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
    # The request's own path is joined in: "%252e%252e" reached the route as
    # "%2e%2e", which the browser would read as a dot segment.
    if _reinterpreted(resolved.path):
        return None
    location = resolved.path
    if resolved.query:
        location += f"?{resolved.query}"
    if resolved.fragment:
        location += f"#{resolved.fragment}"
    return location


def _app_cookie(value: str, root: str) -> str | None:
    """A cookie the module sets on its own path and host, renamed; else None."""
    pair, _, attributes = value.partition(";")
    name, separator, cookie_value = pair.partition("=")
    name = name.strip()
    if not separator or not _COOKIE_NAME.fullmatch(name) or name == APP_HTML_TOKEN_COOKIE:
        return None
    rest = f"{cookie_value.strip()};{attributes}" if attributes else cookie_value.strip()
    path = None
    for attribute in attributes.split(";"):
        key, _, attribute_value = attribute.partition("=")
        key = key.strip().lower()
        if key == "domain":
            return None
        if key == "path":
            path = attribute_value.strip()
    if path is None or _reinterpreted(path) or not _within(path.rstrip("/") or "/", root):
        return None
    return f"{APP_COOKIE_PREFIX}{name}={rest}"


def _is_returned(name: str) -> bool:
    if name in _RETURNED:
        return True
    return name.startswith("x-") and not name.startswith(_NOT_RETURNED)


def _sendable(name: str, value: str) -> bool:
    """A header HTTP can carry: latin-1, no line break, NUL or control byte."""
    try:
        name.encode("latin-1")
        value.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return bool(_COOKIE_NAME.fullmatch(name)) and not _BAD_VALUE.search(value)


def _returned_headers(
    headers: tuple[tuple[str, str], ...], root: str, path: str = "/", status: int = 200
) -> list[tuple[str, str]]:
    returned = []
    for name, value in headers:
        lower = name.lower()
        if not _sendable(name, value):
            continue
        if _is_returned(lower):
            returned.append((name, value))
        elif lower == "location" and not 300 <= status < 400:
            # A created resource's address (201): the browser does not go there.
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


def _content_length(headers: tuple[tuple[str, str], ...]) -> int | None:
    value = next((v for k, v in headers if k.lower() == "content-length"), "").strip()
    return int(value) if value.isdigit() else None


class _Slots:
    """Bodies streaming to or from each module from this worker, at most
    ``limit`` per module (uploads, or responses)."""

    def __init__(self, limit: int, busy: str) -> None:
        self.limit, self.busy = limit, busy
        self.active: dict[str, int] = {}

    def acquire(self, module_id: str) -> Callable[[], None]:
        """Take a slot (503 when none is left); call the result to give it back."""
        if self.active.get(module_id, 0) >= self.limit:
            raise HTTPException(status_code=503, detail=self.busy, headers=SECURITY_HEADERS)
        self.active[module_id] = self.active.get(module_id, 0) + 1
        released = False

        def release() -> None:
            nonlocal released
            if not released:
                released = True
                self.active[module_id] -= 1
                if not self.active[module_id]:
                    del self.active[module_id]

        return release

    @contextlib.contextmanager
    def slot(self, module_id: str) -> Iterator[None]:
        release = self.acquire(module_id)
        try:
            yield
        finally:
            release()


_uploads = _Slots(MAX_UPLOADS_PER_MODULE, "Too many uploads to this app")
_streams = _Slots(MAX_STREAMS_PER_MODULE, "Too many responses streaming from this app")


async def _close(body: AsyncIterator[bytes]) -> None:
    """Close a module's body: the module hears of it and stops its app."""
    closing = getattr(body, "aclose", None)
    if closing is not None:
        with contextlib.suppress(Exception):
            await closing()


class _RemoteAppStream(StreamingResponse):
    """A module's streamed body, holding one of its module's stream slots.

    It stops when the browser leaves, even while the stream is idle
    (server-sent events), whatever ASGI spec version the server speaks, and
    it always closes the body, so the module stops its app. A body that
    breaks off raises from its iterator (RemoteAppStreamFailed): the server
    then aborts the connection."""

    def __init__(
        self, body: AsyncIterator[bytes], release: Callable[[], None], status_code: int
    ) -> None:
        super().__init__(body, status_code=status_code)
        self._body, self._release = body, release

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        import anyio

        failed: list[Exception] = []
        try:
            async with anyio.create_task_group() as group:

                async def respond() -> None:
                    try:
                        await self.stream_response(send)
                    except RemoteAppStreamFailed as exc:  # raised below, not as a group
                        failed.append(exc)
                    except Exception:  # the browser left mid-stream: not an error
                        _log.debug("A remote app's reader left mid-stream", exc_info=True)
                    group.cancel_scope.cancel()

                group.start_soon(respond)
                await self.listen_for_disconnect(receive)
                group.cancel_scope.cancel()
        finally:
            self._release()
            with anyio.CancelScope(shield=True):
                await _close(self._body)
        if failed:
            raise failed[0]


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


_EXPIRED = "This app link has expired. Open the app again."


def _granted(grant: str, module_id: str, app: str) -> RemoteAppGrant:
    granted = read_remote_app_grant(grant, secret=current_secret_key())
    if granted is None or (granted.module_id, granted.app) != (module_id, app):
        raise HTTPException(status_code=401, detail=_EXPIRED, headers=SECURITY_HEADERS)
    return granted


async def _live_grant(grant: str, module_id: str, app: str) -> RemoteAppGrant:
    """The grant, unless it expired or the user logged out since it was issued."""
    granted = _granted(grant, module_id, app)
    assert granted.issued_at is not None  # read_remote_app_grant requires it
    if await revocation.grant_revoked(granted.user_id, granted.issued_at):
        raise HTTPException(status_code=401, detail=_EXPIRED, headers=SECURITY_HEADERS)
    return granted


def _unavailable(module_id: str, app: str, exc: RemoteAppUnavailable) -> HTTPException:
    if exc.status >= 500:
        _log.warning("Remote app %s/%s: %s", module_id, app, exc.reason)
    return HTTPException(status_code=exc.status, detail=exc.reason, headers=SECURITY_HEADERS)


async def serve_remote_app(
    grant: str, module_id: str, app: str, path: str, request: Request
) -> Response:
    granted = await _live_grant(grant, module_id, app)
    return await _forward(
        module_id,
        app,
        path,
        request,
        user_id=granted.user_id,
        workspace_id=granted.workspace_id,
        root=grant_root(grant, module_id, app),
    )


async def _forward(
    module_id: str,
    app: str,
    path: str,
    request: Request,
    *,
    user_id: str,
    workspace_id: str,
    root: str,
) -> Response:
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
        workspace_id=workspace_id,
        body_stream=rest,
        # The module holds to its own limit too, whatever this says.
        max_body_bytes=limit,
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
    return await _response(module_id, answer, request.method, root, "/" + path)


async def _response(
    module_id: str, answer: AppResponse, method: str, root: str, path: str
) -> Response:
    length = _content_length(answer.headers)
    response: Response
    if answer.body_stream is not None:
        try:
            release = _streams.acquire(module_id)
        except HTTPException:
            await _close(answer.body_stream)
            raise
        response = _RemoteAppStream(answer.body_stream, release, answer.status)
        if length is not None:
            # A body cut short then fails in the browser, through any proxy.
            response.headers["content-length"] = str(length)
    else:
        response = Response(content=answer.body, status_code=answer.status)
        if method.upper() == "HEAD" and length is not None:
            response.headers["content-length"] = str(length)  # what GET would send
    for name, value in _returned_headers(answer.headers, root, path, answer.status):
        response.headers.append(name, value)
    response.headers.update(SECURITY_HEADERS)
    return response


async def redirect_remote_app_root(
    grant: str, module_id: str, app: str, request: Request
) -> Response:
    """``.../<app>`` -> ``.../<app>/``: relative links in the entry page resolve."""
    await _live_grant(grant, module_id, app)
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        f"{request.url.path}/{query}", status_code=307, headers=SECURITY_HEADERS
    )


def remote_app_grant_url(
    user_id: str,
    module_id: str,
    app: str,
    not_after: datetime | None = None,
    workspace_id: str = "",
) -> str:
    """The app's root under a fresh grant, ending with ``/``."""
    grant = mint_remote_app_grant(
        secret=current_secret_key(),
        user_id=user_id,
        module_id=module_id,
        app=app,
        minutes=nexus_config.settings.remote_app_grant_expire_minutes,
        not_after=not_after,
        workspace_id=workspace_id,
    )
    return grant_root(grant, module_id, app) + "/"


async def open_remote_app(module_id: str, app: str, request: Request, path: str = "") -> Response:
    """The catalog URL, after the ``/app-html/`` access check.

    A user gets the same page under a fresh grant (307: a POST stays a POST),
    for the workspace ``?workspace_id=`` names, or the first of theirs that
    enables the app, and no longer than the credential that was presented (a
    share link stays a share link). An ``ABI_API_KEY`` caller is a script, not
    a browser: it is answered directly, with no user and no workspace."""
    if not is_segment(module_id, app):
        raise HTTPException(status_code=404, detail="Not Found")
    user_id, expires = _presented_user(request)
    if user_id:
        await refuse_revoked_credential(user_id, request)
    if not user_id:
        return await _forward(
            module_id,
            app,
            path,
            request,
            user_id="",
            workspace_id="",
            root=RemoteApp(module_id, app).root_path,
        )
    workspace_id = await access.remote_app_workspace(
        user_id,
        RemoteApp(module_id, app).app_id,
        request.query_params.get("workspace_id") or None,
    )
    query = _query(request, "workspace_id")
    target = (
        remote_app_grant_url(user_id, module_id, app, not_after=expires, workspace_id=workspace_id)
        + path
    )
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
