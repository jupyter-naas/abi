"""Shared ABI API key (+ optional JWT) checks for ``/app-html/`` assets."""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from collections.abc import Callable
from typing import NamedTuple

from fastapi import HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Cookie stamped when a scoped ``?token=`` JWT opens ``/app-html/`` so SPA
# asset / soft-nav requests keep working without re-attaching the query param.
APP_HTML_TOKEN_COOKIE = "abi_app_html_token"
# A link is an IAM grant, eight hours at most; the cookie matches that ceiling.
APP_HTML_TOKEN_COOKIE_MAX_AGE = 8 * 60 * 60

# Extra validators (e.g. Nexus JWT) registered at startup. Signature:
# ``(token, request) -> bool``.
_EXTRA_APP_HTML_TOKEN_VALIDATORS: list[Callable[[str, Request], bool]] = []


def register_app_html_token_validator(validator: Callable[[str, Request], bool]) -> None:
    """Register an additional ``/app-html/`` token checker (Nexus JWT, etc.)."""
    _EXTRA_APP_HTML_TOKEN_VALIDATORS.append(validator)


def clear_app_html_token_validators() -> None:
    """Test helper — wipe registered validators."""
    _EXTRA_APP_HTML_TOKEN_VALIDATORS.clear()


def extract_abi_api_token(request: Request) -> str | None:
    """Return bearer / ``?token=`` / scoped cookie credential (agent parity)."""
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, header_token = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer" and header_token:
            return header_token

    query_token = request.query_params.get("token")
    if query_token:
        return query_token

    cookie_token = request.cookies.get(APP_HTML_TOKEN_COOKIE)
    if cookie_token:
        return cookie_token
    return None


def expected_abi_api_key() -> str | None:
    return os.environ.get("ABI_API_KEY")


def is_abi_api_token_valid(token: str | None) -> bool:
    expected = expected_abi_api_key()
    if not expected or not token:
        return False
    return hmac.compare_digest(token.encode(), expected.encode())


class AppHtmlCheck(NamedTuple):
    """What a request to ``/app-html/`` presents, checked once."""

    token: str | None
    authorized: bool
    # A scoped credential that arrived as ``?token=`` (not the API key): it is
    # kept in a cookie so the page's own requests carry it.
    stamp: bool


def check_app_html_request(request: Request) -> AppHtmlCheck:
    """Whether ``ABI_API_KEY`` matches or a registered validator accepts, and
    whether the credential is to be stamped into the cookie. The validators may
    ask IAM: this runs once per request, and off the event loop when called from
    the middleware."""
    token = extract_abi_api_token(request)
    if is_abi_api_token_valid(token):
        return AppHtmlCheck(token, True, False)
    if not token:
        return AppHtmlCheck(token, False, False)
    for validator in tuple(_EXTRA_APP_HTML_TOKEN_VALIDATORS):
        try:
            if validator(token, request):
                return AppHtmlCheck(
                    token, True, request.query_params.get("token") == token
                )
        except Exception as exc:  # noqa: BLE001 — never fail open on validator bugs
            logger.debug("app-html token validator error: %s", exc)
    return AppHtmlCheck(token, False, False)


def is_app_html_request_authorized(request: Request) -> bool:
    """True when ``ABI_API_KEY`` matches or any registered JWT validator accepts."""
    return check_app_html_request(request).authorized


def require_abi_api_token(request: Request) -> None:
    """Raise ``401`` when the request is missing a valid app-html credential."""
    if not is_app_html_request_authorized(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _stamp_app_html_token_cookie(
    response: Response,
    *,
    token: str,
    request: Request,
) -> None:
    response.set_cookie(
        key=APP_HTML_TOKEN_COOKIE,
        value=token,
        max_age=APP_HTML_TOKEN_COOKIE_MAX_AGE,
        path="/app-html/",
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


class AppHtmlAbiKeyMiddleware(BaseHTTPMiddleware):
    """Require auth for every ``/app-html/`` request.

    Accepted credentials (same channels as ``/agents``):
    * ``Authorization: Bearer <ABI_API_KEY>`` or ``?token=<ABI_API_KEY>``
    * A registered validator (Nexus user JWT / short-lived ``scope=app-html`` JWT)
    * HttpOnly cookie ``abi_app_html_token`` stamped from a prior ``?token=`` JWT

    CORS preflight (``OPTIONS``) is allowed through.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith("/app-html/") and request.method != "OPTIONS":
            check = await asyncio.to_thread(check_app_html_request, request)
            if not check.authorized:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication credentials"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            response = await call_next(request)
            if check.stamp and check.token is not None:
                _stamp_app_html_token_cookie(
                    response, token=check.token, request=request
                )
            return response
        return await call_next(request)
