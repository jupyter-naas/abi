"""Shared ABI API key (+ optional JWT) checks for ``/app-html/`` assets."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from fastapi import HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Cookie stamped when a scoped ``?token=`` JWT opens ``/app-html/`` so SPA
# asset / soft-nav requests keep working without re-attaching the query param.
APP_HTML_TOKEN_COOKIE = "abi_app_html_token"
# Email share links use 24h JWTs; cookie lifetime matches that ceiling.
APP_HTML_TOKEN_COOKIE_MAX_AGE = 24 * 60 * 60

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
    return bool(expected) and token == expected


def is_app_html_request_authorized(request: Request) -> bool:
    """True when ``ABI_API_KEY`` matches or any registered JWT validator accepts."""
    token = extract_abi_api_token(request)
    if is_abi_api_token_valid(token):
        return True
    if not token:
        return False
    for validator in tuple(_EXTRA_APP_HTML_TOKEN_VALIDATORS):
        try:
            if validator(token, request):
                return True
        except Exception as exc:  # noqa: BLE001 — never fail open on validator bugs
            logger.debug("app-html token validator error: %s", exc)
    return False


def require_abi_api_token(request: Request) -> None:
    """Raise ``401`` when the request is missing a valid app-html credential."""
    if not is_app_html_request_authorized(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _should_stamp_app_html_cookie(request: Request, token: str | None) -> bool:
    """Stamp cookie only for scoped JWTs arriving via ``?token=`` (not API keys)."""
    if not token:
        return False
    if is_abi_api_token_valid(token):
        return False
    if request.query_params.get("token") != token:
        return False
    # Must be accepted by a registered JWT validator (not a random string).
    for validator in tuple(_EXTRA_APP_HTML_TOKEN_VALIDATORS):
        try:
            if validator(token, request):
                return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("app-html cookie stamp validator error: %s", exc)
    return False


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
            if not is_app_html_request_authorized(request):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication credentials"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            token = extract_abi_api_token(request)
            response = await call_next(request)
            if _should_stamp_app_html_cookie(request, token):
                assert token is not None
                _stamp_app_html_token_cookie(response, token=token, request=request)
            return response
        return await call_next(request)
