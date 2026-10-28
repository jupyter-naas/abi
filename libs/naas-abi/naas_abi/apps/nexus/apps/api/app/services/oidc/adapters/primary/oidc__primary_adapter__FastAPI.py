"""``/api/auth/oidc``: sign-in through the engine's identity providers.

* ``GET  /providers``  the providers a login page offers (public).
* ``POST /route``      the provider an email goes to (public).
* ``GET  /login``      start a sign-in: 302 to the provider, with a browser-binding cookie.
* ``GET  /callback``   the provider's redirect: the session cookie, then 302 to the web app.
* ``GET  /session``    the signed-in user and the session's CSRF token.
* ``POST /logout``     end the session (CSRF-checked like every cookie request).

The session cookie is httpOnly, Secure (but on plain http on this machine) and SameSite; nothing the browser can
read holds a token.
"""

from __future__ import annotations

from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi.apps.nexus.apps.api.app.services.audit import log_login, log_logout
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    to_signed_in_user,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime
from naas_abi.apps.nexus.apps.api.app.services.oidc.service import (
    OidcLoginError,
    csrf_token,
)
from naas_abi_core import logger
from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

BINDING_COOKIE = "nexus_oidc_binding"
_BINDING_PATH = f"{settings.api_prefix}/auth/oidc"


class RouteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


def _frontend(path: str, **query: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}{path}" + (f"?{urlencode(query)}" if query else "")


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _secure_cookies() -> bool:
    """Secure, except for a deployment served over plain http on this machine
    (``abi dev``): a browser may keep a Secure cookie on http://localhost, but
    Safari, scripts and proxies do not, and the sign-in would end in
    ``browser_mismatch``. Anything else is Secure."""
    url = urlparse(settings.frontend_url)
    return not (url.scheme == "http" and url.hostname in _LOCAL_HOSTS)


def _cookie_options() -> dict:
    return {
        "httponly": True,
        "secure": _secure_cookies(),
        "samesite": settings.oidc_cookie_samesite,
    }


@router.get("/providers")
async def list_providers() -> dict:
    try:
        providers, default = await runtime.RUNTIME.identity.providers()
    except ProviderUnavailableError:
        return {"providers": [], "default_provider": None}
    return {
        "providers": [{"name": p.name, "display_name": p.display_name} for p in providers],
        "default_provider": default,
    }


@router.post("/route")
async def route_email(payload: RouteRequest, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        provider = await runtime.RUNTIME.service(db).route(payload.email)
    except ProviderUnavailableError:
        provider = None
    return {"provider": provider}


@router.get("/login")
async def login(
    provider: str | None = Query(default=None, max_length=32),
    email: str | None = Query(default=None, max_length=320),
    next: str | None = Query(default=None, max_length=2048),  # noqa: A002 - the web app's name
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    try:
        started = await runtime.RUNTIME.service(db).begin(
            provider=provider, email=email, next_path=next
        )
    except OidcLoginError as exc:
        return RedirectResponse(_frontend("/auth/login", sso_error=exc.code), status_code=302)
    response = RedirectResponse(started.authorization_url, status_code=302)
    response.set_cookie(
        BINDING_COOKIE,
        started.binding,
        max_age=600,
        path=_BINDING_PATH,
        # Lax at least: it must come back on the provider's top-level redirect.
        **{**_cookie_options(), "samesite": "lax"},
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None, max_length=4096),
    state: str | None = Query(default=None, max_length=512),
    error: str | None = Query(default=None, max_length=256),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if error or not code or not state:
        response = RedirectResponse(
            _frontend("/auth/login", sso_error=error or "sign_in_failed"), status_code=302
        )
        response.delete_cookie(BINDING_COOKIE, path=_BINDING_PATH)
        return response
    try:
        signed_in = await runtime.RUNTIME.service(db).complete(
            code=code,
            state=state,
            binding=request.cookies.get(BINDING_COOKIE),
            user_agent=request.headers.get("user-agent"),
        )
    except OidcLoginError as exc:
        await log_login(
            None,
            success=False,
            request=request,
            details={"method": "oidc", "reason": exc.code},
        )
        response = RedirectResponse(_frontend("/auth/login", sso_error=exc.code), status_code=302)
        response.delete_cookie(BINDING_COOKIE, path=_BINDING_PATH)
        return response
    await log_login(signed_in.user_id, success=True, request=request, details={"method": "oidc"})
    response = RedirectResponse(
        _frontend("/auth/callback", next=signed_in.next_path), status_code=302
    )
    response.delete_cookie(BINDING_COOKIE, path=_BINDING_PATH)
    response.set_cookie(
        settings.oidc_session_cookie,
        signed_in.session_secret,
        max_age=settings.oidc_session_max_age_hours * 3600,
        path="/",
        **_cookie_options(),
    )
    return response


@router.get("/session")
async def get_session(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """The cookie session's user and CSRF token. The web app keeps the token in
    memory and sends it as ``X-CSRF-Token`` on every request that changes state."""
    session = getattr(request.state, "nexus_session", None)
    secret = runtime.session_secret(request.headers)
    if session is None or secret is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    record = await AuthSecondaryAdapterPostgres(db=db).get_user_by_id(session.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    return {
        "user": (await to_signed_in_user(record)).model_dump(mode="json"),
        "csrf_token": csrf_token(secret),
        "provider": session.provider,
        "refresh_at": session.refresh_at.isoformat(),
    }


async def _end_remote_app_grants(user_id: str) -> None:
    """A remote app's grant ends with the sign-out, on every device; the sign-out
    itself never fails for it."""
    try:
        await links.arevoke_remote_app_links(user_id)
    except Exception as exc:  # noqa: BLE001 - the session is ended anyway
        logger.warning(f"Remote app grants of user {user_id} were not ended at logout: {exc}")


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    if getattr(request.state, "nexus_csrf_failed", False):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    session = getattr(request.state, "nexus_session", None)
    end_session_url = await runtime.RUNTIME.service(db).logout(
        runtime.session_secret(request.headers),
        post_logout_redirect_uri=_frontend("/auth/login"),
    )
    if session is not None:
        await _end_remote_app_grants(session.user_id)
        await log_logout(session.user_id, request)
    response = JSONResponse({"status": "logged out", "end_session_url": end_session_url})
    response.delete_cookie(settings.oidc_session_cookie, path="/", **_cookie_options())
    return response
