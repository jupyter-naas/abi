"""Browser requests to the built-in IdP, forwarded over NATS.

``/idp/...`` is the issuer URL of the built-in identity provider
(``identity.providers[].issuer``, ``https://<host>/idp``). It is a dedicated,
trusted route, unlike the sandboxed ``/app-remote/<grant>/`` of other modules'
apps: a login page needs access before
anyone is signed in, a cookie of its own and form posts.

What makes it safe to let one module do that:

* **Who answers.** Only the instance running as the service account
  ``module/<project>/idp`` (``binding.py``), while a provider is configured with
  ``provisioning: builtin``. Never discovered by name.
* **Which paths.** An allow-list of the provider's public pages and endpoints,
  each with its methods. Its admin app is not served here: services reach it over
  NATS.
* **Which cookies.** Only ``abi_idp_*``, on the path ``/idp``, with no
  ``Domain``, ``HttpOnly`` and ``SameSite=Lax`` always, ``Secure`` over https.
  Of the browser's cookies the module gets those and no other: never the Nexus
  session.
* **Which headers.** Requests: content negotiation, ``Content-Type``,
  ``User-Agent``, the module's cookies, and ``Authorization`` on its token
  endpoints only (a client's own credential there). The client address is set
  here, never taken from the request: it is ``request.client.host``, which
  uvicorn resolves from ``X-Forwarded-For`` only for the proxies in
  ``FORWARDED_ALLOW_IPS`` (the setting the rest of Nexus's rate limits use). Responses:
  ``Content-Type``, ``Cache-Control``, ``Pragma``, ``ETag``, ``Vary``,
  ``Retry-After``, ``WWW-Authenticate``, ``Location`` (an http(s) URL) and the
  cookies above.
* **Which policy.** The page's Content-Security-Policy is Nexus's, not the
  module's: no script, no object, no framing, and a form may only post to this
  origin and the relying parties' origins (the sign-in redirects to them).
* **Which relying parties.** Nexus's (the origins of its redirect URI and of
  the web app) and those listed in ``idp_client_origins``. ``/authorize`` refuses
  any other ``redirect_uri``: its sign-in would end in a blocked redirect.
* **No user.** The module is told nothing of who is signed in to Nexus: it
  answers a browser, not a Nexus user.
"""

from __future__ import annotations

import contextlib
import logging
import re
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response
from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
    get_remote_app_directory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import (
    AppRequest,
    RemoteAppUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.idp import binding
from naas_abi.apps.nexus.apps.api.app.services.idp.paths import IDP_PREFIX

_log = logging.getLogger(__name__)

# (path -> methods) of what the provider serves to browsers and relying parties.
ROUTES: dict[str, frozenset[str]] = {
    "/.well-known/openid-configuration": frozenset({"GET"}),
    "/jwks.json": frozenset({"GET"}),
    "/authorize": frozenset({"GET"}),
    "/login": frozenset({"GET"}),
    "/login/email": frozenset({"POST"}),
    "/login/code": frozenset({"POST"}),
    "/login/password": frozenset({"GET", "POST"}),
    "/token": frozenset({"POST"}),
    "/revoke": frozenset({"POST"}),
    "/userinfo": frozenset({"GET", "POST"}),
    "/logout": frozenset({"GET"}),
}
METHODS = ["GET", "POST"]
# Where a client's own credential (Basic, or an access token) is the point.
CREDENTIAL_PATHS = frozenset({"/token", "/revoke", "/userinfo"})
MAX_BODY_BYTES = 64 * 1024
MAX_QUERY_BYTES = 8 * 1024
CLIENT_IP_HEADER = "x-abi-client-ip"
COOKIE_PREFIX = "abi_idp_"

_FORWARDED = frozenset({"accept", "accept-language", "content-type", "user-agent"})
_RETURNED = frozenset(
    {
        "content-type",
        "cache-control",
        "pragma",
        "etag",
        "vary",
        "retry-after",
        "www-authenticate",
        "content-language",
    }
)
_COOKIE_NAME = re.compile(r"^abi_idp_[a-z_]{1,32}$")
_COOKIE_VALUE = re.compile(r"^[A-Za-z0-9_.~-]{0,512}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f\\]")


def _reinterpreted(path: str) -> bool:
    """Browsers read "%2e" as "." and "\\" as "/": a dot segment no check below sees."""
    lowered = path.lower()
    return "%2e" in lowered or "%5c" in lowered or "%2f" in lowered or "\\" in path


def _origin(url: str | None) -> str | None:
    parts = urlsplit(url or "")
    if parts.scheme in ("http", "https") and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return None


def relying_party_origins() -> list[str]:
    """The origins that may sign in here: Nexus's (where the redirect URI and the
    web app are) and the ones the config adds (``idp_client_origins``). This
    route serves them and no other relying party: a login page's forms are
    allowed to redirect to exactly these (a browser applies ``form-action`` to
    the redirect after a post), and ``/authorize`` refuses the rest."""
    from naas_abi.apps.nexus.apps.api.app.services.oidc.runtime import redirect_uri

    settings = nexus_config.settings
    candidates = [
        _origin(redirect_uri()),
        _origin(str(settings.frontend_url)),
        *(_origin(o) for o in getattr(settings, "idp_client_origins", ())),
    ]
    return list(dict.fromkeys(o for o in candidates if o))


def content_security_policy() -> str:
    """No script and nothing but the page itself; a form posts here, and the
    sign-in it ends redirects to a relying party's origin (``relying_party_origins``)."""
    form_action = " ".join(dict.fromkeys(["'self'", *relying_party_origins()]))
    return (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' https: data:; "
        f"base-uri 'none'; form-action {form_action}; frame-ancestors 'none'"
    )


def security_headers() -> dict[str, str]:
    return {
        "Content-Security-Policy": content_security_policy(),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }


def _module_cookies(request: Request) -> str:
    return "; ".join(
        f"{name}={value}"
        for name, value in request.cookies.items()
        if _COOKIE_NAME.match(name) and _COOKIE_VALUE.match(value)
    )


def forwarded_headers(request: Request, path: str) -> tuple[tuple[str, str], ...]:
    headers = [
        (name, value) for name, value in request.headers.items() if name.lower() in _FORWARDED
    ]
    if path in CREDENTIAL_PATHS and (auth := request.headers.get("authorization")):
        headers.append(("authorization", auth))
    if cookies := _module_cookies(request):
        headers.append(("cookie", cookies))
    # The connection's peer, set here: the module cannot be told another by a request.
    if request.client is not None and request.client.host:
        headers.append((CLIENT_IP_HEADER, request.client.host))
    return tuple(headers)


def _location(value: str) -> str | None:
    """A redirect the browser may follow: an absolute http(s) URL (the provider
    verified the client's redirect URI) or an absolute path on this origin."""
    value = value.strip()
    if not value or _CONTROL.search(value):
        return None
    parts = urlsplit(value)
    if parts.scheme in ("http", "https") and parts.netloc:
        return value
    if (
        not parts.scheme
        and not parts.netloc
        and value.startswith("/")
        and not value.startswith("//")
    ):
        return value
    return None


def module_cookie(value: str, *, secure: bool) -> str | None:
    """The module's ``Set-Cookie``, normalized, or None when it is not one the
    route lets through: another name, another path, a domain. ``Secure`` stays
    when the module set it or the caller says so."""
    name, separator, rest = value.partition("=")
    name = name.strip()
    if not separator or not _COOKIE_NAME.match(name):
        return None
    content, *attributes = rest.split(";")
    content = content.strip()
    # A cookie being cleared has an empty value, which Starlette quotes (name="").
    if len(content) >= 2 and content[0] == content[-1] == '"':
        content = content[1:-1]
    if not _COOKIE_VALUE.match(content):
        return None
    path = max_age = None
    module_secure = False
    for attribute in attributes:
        key, _, attribute_value = attribute.partition("=")
        key, attribute_value = key.strip().lower(), attribute_value.strip()
        if key == "domain":
            return None
        if key == "secure":
            module_secure = True
        if key == "path":
            path = attribute_value
        elif key == "max-age" and attribute_value.lstrip("-").isdigit():
            max_age = int(attribute_value)
    if (
        path is None
        or _reinterpreted(path)
        or not (path == IDP_PREFIX or path.startswith(IDP_PREFIX + "/"))
        or ".." in path.split("/")
    ):
        return None
    cookie = f"{name}={content}; Path={path}; HttpOnly; SameSite=Lax"
    if max_age is not None:
        cookie += f"; Max-Age={max_age}"
    if secure or module_secure:
        cookie += "; Secure"
    return cookie


def _refuse(status: int, message: str) -> Response:
    return PlainTextResponse(message, status_code=status, headers=security_headers())


async def serve_idp(path: str, request: Request) -> Response:
    below = "/" + path
    if _reinterpreted(below):
        return _refuse(404, "Not Found")
    methods = ROUTES.get(below)
    if methods is None:
        return _refuse(404, "Not Found")
    if request.method not in methods:
        return Response(
            status_code=405, headers={**security_headers(), "Allow": ", ".join(sorted(methods))}
        )
    try:
        target = await binding.BINDING.target()
    except binding.IdpNotConfigured:
        return _refuse(404, "Not Found")
    except binding.IdpUnavailable as exc:
        _log.warning("The built-in IdP is unavailable: %s", exc)
        return _refuse(503, "The identity provider is not available.")
    query = request.url.query
    if len(query.encode()) > MAX_QUERY_BYTES:
        return _refuse(414, "The URL is too long")
    if below == "/authorize" and _origin(request.query_params.get("redirect_uri")) not in (
        relying_party_origins()
    ):
        # Not a relying party this route serves: its sign-in would end in a
        # blocked redirect (form-action), so it never starts. Others are added
        # with `idp_client_origins`.
        return _refuse(400, "This application may not sign in here.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return _refuse(413, "The request is too large")
    body = b""
    if request.method == "POST":
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY_BYTES:
                return _refuse(413, "The request is too large")
    forwarded = AppRequest(
        method=request.method,
        path=below,
        query=query,
        headers=forwarded_headers(request, below),
        body=body,
        user_id="",
        root_path=IDP_PREFIX,
    )
    try:
        answer = await get_remote_app_directory().forward(
            binding.IDP_MODULE,
            binding.IDP_APP,
            forwarded,
            service_account=target.service_account,
        )
    except RemoteAppUnavailable as exc:
        if exc.status >= 500:
            _log.warning("The built-in IdP: %s", exc.reason)
        return _refuse(
            502 if exc.status == 404 else exc.status, "The identity provider did not answer."
        )
    if answer.body_stream is not None:
        with contextlib.suppress(Exception):
            await answer.body_stream.aclose()  # type: ignore[attr-defined]
        return _refuse(502, "The identity provider answered with a stream.")
    # Secure follows the issuer (https where it is served), not only the hop
    # uvicorn sees: behind a TLS-terminating proxy that sends no forwarded
    # headers the request itself looks like http.
    secure = request.url.scheme == "https" or urlsplit(target.issuer).scheme == "https"
    response = Response(content=answer.body, status_code=min(max(answer.status, 200), 599))
    for name, value in answer.headers:
        lower = name.lower()
        if lower in _RETURNED:
            response.headers.append(name, value)
        elif lower == "location":
            location = _location(value)
            if location is not None:
                response.headers.append(name, location)
        elif lower == "set-cookie":
            cookie = module_cookie(value, secure=secure)
            if cookie is not None:
                response.headers.append("set-cookie", cookie)
    for name, value in security_headers().items():
        response.headers[name] = value
    return response
