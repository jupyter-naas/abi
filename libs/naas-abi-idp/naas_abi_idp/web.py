"""The provider's public pages and endpoints, as an ASGI application.

Nexus serves it at the issuer URL (``https://<host>/idp``) over NATS, on a
dedicated route that carries no other credential than this module's own cookies:

* ``/.well-known/openid-configuration`` and ``/jwks.json``: discovery and keys;
* ``/authorize``: starts a sign-in, or finishes it at once when the browser holds
  the provider's own session; the login pages are ``/login/...``;
* ``/token``, ``/revoke``, ``/userinfo``, ``/logout``.

Every response says ``no-store``, sets a strict Content-Security-Policy, and no
page loads a script. Two cookies, both ``HttpOnly``, ``SameSite=Lax`` and
limited to the issuer's path: ``abi_idp_login`` names the authorization request
being signed in, ``abi_idp_session`` the provider's own session.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from authlib.oauth2.rfc6749 import OAuth2Error
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from naas_abi_idp import pages
from naas_abi_idp.oidc import (
    CLAIMS,
    SCOPES,
    TOKEN_AUTH_METHODS,
    HttpRequest,
    HttpResult,
    IdPAuthorizationServer,
    allow_local_issuer,
)
from naas_abi_idp.ports import IdPError, InvalidCode, RateLimited
from naas_abi_idp.service import IdPService

log = logging.getLogger(__name__)

LOGIN_COOKIE = "abi_idp_login"
SESSION_COOKIE = "abi_idp_session"
MAX_FORM_BYTES = 64 * 1024
# What a sign-in page may load: nothing but its own styles inline and the logo.
BASE_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' https: data:; "
    "base-uri 'none'; frame-ancestors 'none'"
)


class IdPWeb:
    def __init__(self, service: IdPService) -> None:
        self.service = service
        self.config = service.configuration
        self.server = IdPAuthorizationServer(service)
        allow_local_issuer(self.config.issuer)
        parts = urlsplit(self.config.issuer)
        self.secure = parts.scheme == "https"
        self.cookie_path = parts.path or "/"

    # -- the application ----------------------------------------------------------

    def app(self) -> Starlette:
        routes = [
            Route("/.well-known/openid-configuration", self.discovery, methods=["GET"]),
            Route("/jwks.json", self.jwks, methods=["GET"]),
            Route("/authorize", self.authorize, methods=["GET"]),
            Route("/login", self.login_page, methods=["GET"]),
            Route("/login/email", self.login_email, methods=["POST"]),
            Route("/login/code", self.login_code, methods=["POST"]),
            Route("/login/password", self.login_password, methods=["GET", "POST"]),
            Route("/token", self.token, methods=["POST"]),
            Route("/revoke", self.revoke, methods=["POST"]),
            Route("/userinfo", self.userinfo, methods=["GET", "POST"]),
            Route("/logout", self.logout, methods=["GET"]),
            Route("/healthz", self.health, methods=["GET"]),
        ]
        return Starlette(routes=routes)

    # -- discovery ------------------------------------------------------------------

    async def discovery(self, request: Request) -> Response:
        issuer = self.config.issuer
        document = {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "userinfo_endpoint": f"{issuer}/userinfo",
            "jwks_uri": f"{issuer}/jwks.json",
            "revocation_endpoint": f"{issuer}/revoke",
            "end_session_endpoint": f"{issuer}/logout",
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": [
                "authorization_code",
                "refresh_token",
                "client_credentials",
            ],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["ES256"],
            "scopes_supported": list(SCOPES),
            "claims_supported": list(CLAIMS),
            "token_endpoint_auth_methods_supported": TOKEN_AUTH_METHODS,
            "revocation_endpoint_auth_methods_supported": TOKEN_AUTH_METHODS,
            "code_challenge_methods_supported": ["S256"],
            "prompt_values_supported": ["none", "login"],
        }
        return self._json(document, cache="public, max-age=300")

    async def jwks(self, request: Request) -> Response:
        keys = await run_in_threadpool(self.service.keys.jwks)
        return self._json(keys, cache="public, max-age=300")

    async def health(self, request: Request) -> Response:
        return Response("ok", media_type="text/plain", headers=self._headers())

    # -- authorization --------------------------------------------------------------

    async def authorize(self, request: Request) -> Response:
        return await run_in_threadpool(self._authorize, _Context.of(request, self))

    def _authorize(self, ctx: _Context) -> Response:
        items = ctx.query_items
        params = dict(items)
        if len(params) != len(items):
            return self._page(
                400,
                pages.message_page(
                    self.config.branding, "Invalid request", "A parameter was repeated."
                ),
            )
        session = self.service.get_session(ctx.cookies.get(SESSION_COOKIE))
        prompt = params.get("prompt", "").split()
        if session is not None:
            max_age = params.get("max_age", "")
            now = self.service.clock()
            too_old = max_age.isdigit() and now - session[0].auth_time > int(max_age)
            if "login" in prompt or too_old:
                session = None
        oauth = self.server.create_oauth2_request(
            HttpRequest("GET", f"{self.config.issuer}/authorize", query=params)
        )
        user = session[1] if session is not None else None
        try:
            grant = self.server.get_consent_grant(request=oauth, end_user=user)
        except OAuth2Error as error:
            return self._oauth_error(oauth, error)
        if session is None:
            rid, csrf = self.service.save_auth_request(params)
            response = self._page(
                200,
                pages.email_page(
                    self.config.branding,
                    action=f"{self.config.issuer}/login/email",
                    csrf=csrf,
                    password_action=self._password_url(),
                ),
                form_origins=self._form_origins(params),
            )
            self._set_cookie(
                response, LOGIN_COOKIE, rid, self.config.authorization_request_seconds
            )
            return response
        assert user is not None
        oauth.auth_time, oauth.amr = session[0].auth_time, list(session[0].amr)
        result = self.server.create_authorization_response(
            request=oauth, grant_user=user, grant=grant
        )
        return self._result(result)

    # -- the login pages ---------------------------------------------------------------

    async def login_page(self, request: Request) -> Response:
        return await run_in_threadpool(self._login_page, _Context.of(request, self))

    def _login_page(self, ctx: _Context) -> Response:
        pending = self.service.get_auth_request(ctx.cookies.get(LOGIN_COOKIE))
        if pending is None:
            return self._expired()
        params, csrf = pending
        return self._page(
            200,
            pages.email_page(
                self.config.branding,
                action=f"{self.config.issuer}/login/email",
                csrf=csrf,
                password_action=self._password_url(),
            ),
            form_origins=self._form_origins(params),
        )

    async def login_email(self, request: Request) -> Response:
        ctx = await _Context.read(request, self)
        return await run_in_threadpool(self._login_email, ctx)

    def _login_email(self, ctx: _Context) -> Response:
        pending = self._pending(ctx)
        if isinstance(pending, Response):
            return pending
        params, csrf = pending
        email = ctx.form.get("email", "")
        branding = self.config.branding_for(email)
        origins = self._form_origins(params)
        try:
            self.service.request_code(email, ctx.client_ip)
        except RateLimited as limited:
            return self._limited(limited, branding, origins)
        except IdPError:
            # An address that is not one, or one that cannot be mailed: the page
            # says what it says for every address.
            log.info("Sign-in code not sent (invalid address)")
        except Exception:
            log.exception("Could not send a sign-in code")
        return self._page(
            200,
            pages.code_page(
                branding,
                action=f"{self.config.issuer}/login/code",
                again_action=f"{self.config.issuer}/login",
                csrf=csrf,
                email=ctx.form.get("email", "").strip().lower()[:254],
                code_length=self.config.code_length,
            ),
            form_origins=origins,
        )

    async def login_code(self, request: Request) -> Response:
        ctx = await _Context.read(request, self)
        return await run_in_threadpool(self._login_code, ctx)

    def _login_code(self, ctx: _Context) -> Response:
        pending = self._pending(ctx)
        if isinstance(pending, Response):
            return pending
        params, csrf = pending
        email = ctx.form.get("email", "")
        branding = self.config.branding_for(email)
        origins = self._form_origins(params)
        try:
            user = self.service.verify_code(
                email, ctx.form.get("code", ""), ctx.client_ip
            )
        except RateLimited as limited:
            return self._limited(limited, branding, origins)
        except InvalidCode:
            return self._page(
                400,
                pages.code_page(
                    branding,
                    action=f"{self.config.issuer}/login/code",
                    again_action=f"{self.config.issuer}/login",
                    csrf=csrf,
                    email=email.strip().lower()[:254],
                    error="That code is not valid, or it has expired.",
                    code_length=self.config.code_length,
                ),
                form_origins=origins,
            )
        return self._complete(ctx, params, user, ["otp"])

    async def login_password(self, request: Request) -> Response:
        ctx = await _Context.read(request, self)
        return await run_in_threadpool(self._login_password, ctx)

    def _login_password(self, ctx: _Context) -> Response:
        if not self.config.password_login_enabled:
            return self._page(
                404,
                pages.message_page(
                    self.config.branding, "Not found", "Password sign-in is off."
                ),
            )
        pending = self._pending(ctx, check_csrf=ctx.method == "POST")
        if isinstance(pending, Response):
            return pending
        params, csrf = pending
        email = ctx.form.get("email", "")
        branding = self.config.branding_for(email)
        origins = self._form_origins(params)

        def form(error: str | None = None, status: int = 200) -> Response:
            return self._page(
                status,
                pages.password_page(
                    branding,
                    action=f"{self.config.issuer}/login/password",
                    email_action=f"{self.config.issuer}/login",
                    csrf=csrf,
                    email=email.strip().lower()[:254],
                    error=error,
                ),
                form_origins=origins,
            )

        if ctx.method == "GET":
            return form()
        try:
            user = self.service.verify_password(
                email, ctx.form.get("password", ""), ctx.client_ip
            )
        except RateLimited as limited:
            return self._limited(limited, branding, origins)
        except InvalidCode:
            return form("Incorrect email or password.", 400)
        return self._complete(ctx, params, user, ["pwd"])

    def _complete(
        self, ctx: _Context, params: dict[str, str], user: Any, amr: list[str]
    ) -> Response:
        """The user is signed in: finish the authorization request that was
        waiting, and keep the provider's own session."""
        oauth = self.server.create_oauth2_request(
            HttpRequest("GET", f"{self.config.issuer}/authorize", query=params)
        )
        try:
            grant = self.server.get_consent_grant(request=oauth, end_user=user)
        except OAuth2Error as error:
            return self._oauth_error(oauth, error)
        cookie, session = self.service.create_session(user, amr)
        oauth.auth_time, oauth.amr = session.auth_time, list(amr)
        result = self.server.create_authorization_response(
            request=oauth, grant_user=user, grant=grant
        )
        self.service.drop_auth_request(ctx.cookies.get(LOGIN_COOKIE))
        response = self._result(result)
        self._set_cookie(
            response, SESSION_COOKIE, cookie, self.config.session_hours * 3600
        )
        self._clear_cookie(response, LOGIN_COOKIE)
        return response

    def _pending(
        self, ctx: _Context, *, check_csrf: bool = True
    ) -> tuple[dict[str, str], str] | Response:
        pending = self.service.get_auth_request(ctx.cookies.get(LOGIN_COOKIE))
        if pending is None:
            return self._expired()
        if check_csrf and not hmac.compare_digest(
            ctx.form.get("csrf", "").encode(), pending[1].encode()
        ):
            return self._page(
                400,
                pages.message_page(
                    self.config.branding,
                    "Sign-in expired",
                    "This page is out of date. Go back to the application and sign in again.",
                ),
            )
        return pending

    # -- tokens --------------------------------------------------------------------------

    async def token(self, request: Request) -> Response:
        ctx = await _Context.read(request, self, strict_form=True)
        if ctx.form_error:
            return self._json(
                {"error": "invalid_request", "error_description": ctx.form_error},
                status=400,
            )
        http = HttpRequest(
            "POST", f"{self.config.issuer}/token", headers=ctx.headers, form=ctx.form
        )
        result = await run_in_threadpool(self.server.create_token_response, http)
        return self._result(result)

    async def revoke(self, request: Request) -> Response:
        ctx = await _Context.read(request, self, strict_form=True)
        if ctx.form_error:
            return self._json(
                {"error": "invalid_request", "error_description": ctx.form_error},
                status=400,
            )
        http = HttpRequest(
            "POST", f"{self.config.issuer}/revoke", headers=ctx.headers, form=ctx.form
        )
        result = await run_in_threadpool(
            lambda: self.server.create_endpoint_response("revocation", http)
        )
        return self._result(result)

    async def userinfo(self, request: Request) -> Response:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return self._unauthorized()
        return await run_in_threadpool(self._userinfo, token.strip())

    def _userinfo(self, token: str) -> Response:
        claims = self.server.verify_access_token(token)
        if claims is None or claims.get("sub") == claims.get("client_id"):
            return self._unauthorized()
        try:
            user = self.service.get_user(claims["sub"])
        except IdPError:
            return self._unauthorized()
        if user.disabled or "openid" not in claims.get("scope", "").split():
            return self._unauthorized()
        return self._json(self.server.user_claims(user, claims.get("scope", "")))

    def _unauthorized(self) -> Response:
        return Response(
            status_code=401,
            headers={
                **self._headers(),
                "WWW-Authenticate": 'Bearer error="invalid_token"',
            },
        )

    # -- sign out -------------------------------------------------------------------------

    async def logout(self, request: Request) -> Response:
        return await run_in_threadpool(self._logout, _Context.of(request, self))

    def _logout(self, ctx: _Context) -> Response:
        self.service.end_session(ctx.cookies.get(SESSION_COOKIE))
        target = self._post_logout_target(ctx.query)
        if target is not None:
            response: Response = Response(
                status_code=302, headers={**self._headers(), "Location": target}
            )
        else:
            response = self._page(
                200,
                pages.message_page(
                    self.config.branding,
                    "Signed out",
                    "You are signed out. You can close this tab.",
                ),
            )
        self._clear_cookie(response, SESSION_COOKIE)
        return response

    def _post_logout_target(self, query: Mapping[str, str]) -> str | None:
        """``post_logout_redirect_uri`` when the client named by ``id_token_hint``
        has a redirect URI on the same origin; an unverified hint redirects nowhere."""
        uri, hint = query.get("post_logout_redirect_uri"), query.get("id_token_hint")
        if not uri or not hint:
            return None
        claims = self._unverified_id_token(hint)
        client = self.service.get_client((claims or {}).get("aud", ""))
        if client is None:
            return None
        origin = _origin(uri)
        if origin is None or origin not in {_origin(u) for u in client.redirect_uris}:
            return None
        if state := query.get("state"):
            from authlib.common.urls import add_params_to_uri

            uri = add_params_to_uri(uri, [("state", state)])
        return uri

    def _unverified_id_token(self, token: str) -> dict[str, Any] | None:
        """An ID token this provider signed, even an expired one (a hint)."""
        from authlib.jose import JsonWebToken

        from naas_abi_idp.oidc import _KeySet

        try:
            claims = JsonWebToken(["ES256"]).decode(token, _KeySet(self.service))
        except Exception:  # noqa: BLE001
            return None
        if claims.get("iss") != self.config.issuer:
            return None
        aud = claims.get("aud")
        return {"aud": aud[0] if isinstance(aud, list) and aud else aud}

    # -- responses ---------------------------------------------------------------------------

    def _headers(self, csp: str = BASE_CSP) -> dict[str, str]:
        return {
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Content-Security-Policy": csp,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
        }

    def _json(
        self, data: Any, *, status: int = 200, cache: str | None = None
    ) -> JSONResponse:
        headers = self._headers()
        if cache:
            headers["Cache-Control"] = cache
            headers.pop("Pragma")
        return JSONResponse(data, status_code=status, headers=headers)

    def _page(
        self, status: int, html: str, *, form_origins: list[str] | None = None
    ) -> Response:
        csp = BASE_CSP
        # A browser applies form-action to the redirect after a form post too:
        # the client's own origin must be allowed, or the sign-in ends on a block.
        csp += "; form-action 'self'" + "".join(f" {o}" for o in form_origins or [])
        return Response(
            html, status_code=status, media_type="text/html", headers=self._headers(csp)
        )

    def _result(self, result: HttpResult) -> Response:
        headers: dict[str, str] = {}
        for key, value in result.headers:
            headers[key] = value
        response = Response(result.body, status_code=result.status)
        for key, value in {**self._headers(), **headers}.items():
            response.headers[key] = value
        return response

    def _oauth_error(self, oauth: Any, error: OAuth2Error) -> Response:
        if error.redirect_uri:  # the client and its redirect URI were verified
            return self._result(self.server.handle_error_response(oauth, error))
        return self._page(
            400,
            pages.message_page(
                self.config.branding,
                "Cannot sign in",
                f"The application sent an invalid request ({error.error}).",
            ),
        )

    def _expired(self) -> Response:
        return self._page(
            400,
            pages.message_page(
                self.config.branding,
                "Sign-in expired",
                "Go back to the application and sign in again.",
            ),
        )

    def _limited(
        self, limited: RateLimited, branding: Any, origins: list[str]
    ) -> Response:
        minutes = max(1, (limited.retry_after + 59) // 60)
        response = self._page(
            429,
            pages.message_page(
                branding,
                "Too many attempts",
                f"Try again in {minutes} minute{'s' if minutes > 1 else ''}.",
            ),
            form_origins=origins,
        )
        response.headers["Retry-After"] = str(limited.retry_after)
        return response

    def _set_cookie(
        self, response: Response, name: str, value: str, max_age: int
    ) -> None:
        response.set_cookie(
            name,
            value,
            max_age=int(max_age),
            path=self.cookie_path,
            secure=self.secure,
            httponly=True,
            samesite="lax",
        )

    def _clear_cookie(self, response: Response, name: str) -> None:
        response.delete_cookie(
            name,
            path=self.cookie_path,
            secure=self.secure,
            httponly=True,
            samesite="lax",
        )

    def _password_url(self) -> str | None:
        return (
            f"{self.config.issuer}/login/password"
            if self.config.password_login_enabled
            else None
        )

    def _form_origins(self, params: Mapping[str, str]) -> list[str]:
        client = self.service.get_client(params.get("client_id", ""))
        if client is None:
            return []
        return sorted({o for o in (_origin(u) for u in client.redirect_uris) if o})


class _Context:
    """What a handler needs of a request, read once."""

    def __init__(self, request: Request, web: IdPWeb) -> None:
        self.method = request.method
        self.headers = request.headers  # case-insensitive, as authlib reads them
        self.cookies = dict(request.cookies)
        self.query_items = request.query_params.multi_items()
        self.query = dict(self.query_items)
        self.form: dict[str, str] = {}
        self.form_error: str | None = None
        header = web.config.client_ip_header
        self.client_ip = (self.headers.get(header) or "").strip()[:64] or None

    @classmethod
    def of(cls, request: Request, web: IdPWeb) -> _Context:
        return cls(request, web)

    @classmethod
    async def read(
        cls, request: Request, web: IdPWeb, *, strict_form: bool = False
    ) -> _Context:
        ctx = cls(request, web)
        if request.method != "POST":
            return ctx
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_FORM_BYTES:
            ctx.form_error = "The request is too large."
            return ctx
        body = await request.body()
        if len(body) > MAX_FORM_BYTES:
            ctx.form_error = "The request is too large."
            return ctx
        kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if kind != "application/x-www-form-urlencoded":
            if strict_form or body:
                ctx.form_error = "Send application/x-www-form-urlencoded."
            return ctx
        try:
            items = parse_qsl(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=bool(body)
            )
        except (UnicodeDecodeError, ValueError):
            ctx.form_error = "The form is malformed."
            return ctx
        ctx.form = dict(items)
        if len(ctx.form) != len(items):
            ctx.form_error = "A parameter was repeated."
        return ctx


def _origin(uri: str) -> str | None:
    parts = urlsplit(uri)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"
