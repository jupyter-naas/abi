"""JWT validators and minting for time-limited ``/app-html/`` access."""

from __future__ import annotations

from datetime import timedelta

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    create_access_token,
    decode_token,
)
from naas_abi_core.apps.api.abi_api_key_auth import register_app_html_token_validator
from starlette.requests import Request

APP_HTML_TOKEN_SCOPE = "app-html"


def validate_app_html_jwt(token: str, request: Request) -> bool:
    """Accept Nexus user JWTs and scoped ``app-html`` JWTs (``exp`` enforced by jose)."""
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        return False

    scope = payload.get("scope")
    # Scoped tokens must explicitly target app-html; bare session JWTs are OK.
    if scope is not None and scope != APP_HTML_TOKEN_SCOPE:
        return False

    path_prefix = payload.get("path_prefix")
    if path_prefix:
        prefix = str(path_prefix)
        if not prefix.startswith("/app-html/"):
            return False
        if not request.url.path.startswith(prefix):
            return False

    return True


def mint_app_html_access_token(
    *,
    user_id: str,
    expires_minutes: int | None = None,
    path_prefix: str | None = None,
) -> tuple[str, int]:
    """Return ``(jwt, expires_in_seconds)`` for ``/app-html/`` access."""
    minutes = expires_minutes or settings.app_html_access_token_expire_minutes
    minutes = max(1, min(minutes, 24 * 60))
    claims: dict[str, str] = {
        "sub": user_id,
        "scope": APP_HTML_TOKEN_SCOPE,
    }
    if path_prefix:
        prefix = path_prefix.strip()
        if not prefix.startswith("/app-html/"):
            raise ValueError("path_prefix must start with /app-html/")
        claims["path_prefix"] = prefix

    token, _ = create_access_token(
        data=claims,
        expires_delta=timedelta(minutes=minutes),
    )
    return token, minutes * 60


def register_nexus_app_html_jwt_auth() -> None:
    """Wire Nexus JWT validation into the shared ``/app-html/`` middleware."""
    register_app_html_token_validator(validate_app_html_jwt)
