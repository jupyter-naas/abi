"""``/app-html/remote/<module_id>/<app>/<path>``: browser requests to a remote
module's app, forwarded over NATS (docs/adr/20261012_remote-module-apps.md).

The ``/app-html/`` access check has already run. The module gets the user's
id, never the user's credential: the Authorization header, the access cookie
and a ``?token=`` are removed before forwarding.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
    get_remote_app_directory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    MAX_REQUEST_BODY,
    AppRequest,
    RemoteAppUnavailable,
)
from naas_abi_core.apps.api.abi_api_key_auth import (
    APP_HTML_TOKEN_COOKIE,
    extract_abi_api_token,
)

_log = logging.getLogger(__name__)

# Connection-level headers never cross the hop (RFC 9110 section 7.6.1).
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
)
_CREDENTIALS = frozenset({"authorization", "cookie"})
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _user_id(request: Request) -> str:
    """The signed-in user behind the request; empty for an ABI_API_KEY caller."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

    token = extract_abi_api_token(request)
    payload = decode_token(token) if token else None
    subject = payload.get("sub") if isinstance(payload, dict) else None
    return subject if isinstance(subject, str) else ""


def _forwarded_headers(request: Request) -> tuple[tuple[str, str], ...]:
    headers = [
        (name, value)
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP | _CREDENTIALS
    ]
    # The app's own cookies pass; the access cookie does not.
    cookies = "; ".join(
        f"{name}={value}"
        for name, value in request.cookies.items()
        if name != APP_HTML_TOKEN_COOKIE
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


def _returned_headers(headers: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    return [
        (name, value)
        for name, value in headers
        if name.lower() not in HOP_BY_HOP
        # A module must not overwrite the access cookie of every app.
        and not (
            name.lower() == "set-cookie" and value.split("=", 1)[0].strip() == APP_HTML_TOKEN_COOKIE
        )
    ]


async def serve_remote_app(module_id: str, app: str, path: str, request: Request) -> Response:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_REQUEST_BODY:
        raise HTTPException(status_code=413, detail="App request exceeds 1 MiB")
    body = await request.body()
    if len(body) > MAX_REQUEST_BODY:
        raise HTTPException(status_code=413, detail="App request exceeds 1 MiB")
    forwarded = AppRequest(
        method=request.method,
        path="/" + path,
        query=_query(request),
        headers=_forwarded_headers(request),
        body=body,
        user_id=_user_id(request),
    )
    try:
        answer = await get_remote_app_directory().forward(module_id, app, forwarded)
    except RemoteAppUnavailable as exc:
        if exc.status >= 500:
            _log.warning("Remote app %s/%s: %s", module_id, app, exc.reason)
        raise HTTPException(status_code=exc.status, detail=exc.reason) from exc
    response = Response(content=answer.body, status_code=answer.status)
    for name, value in _returned_headers(answer.headers):
        response.headers.append(name, value)
    return response


async def redirect_remote_app_root(module_id: str, app: str, request: Request) -> Response:
    """``.../<app>`` -> ``.../<app>/``: relative links in the entry page resolve."""
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(f"{request.url.path}/{query}", status_code=307)
