"""Links for time-limited ``/app-html/`` access: IAM grants (``links.py``).

The link is a grant of the user who made it, for the audience
``abi:delegated:app``, bound to the path it opens (``resource``: a prefix below
``/app-html/``) and narrowed to nothing at the kernel: it opens pages, it does
not act as the user. Eight hours at most, revocable, and never a session.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi_core.apps.api.abi_api_key_auth import register_app_html_token_validator
from naas_abi_core.engine.nats_auth import APP_AUDIENCE, GRANT_KEY_PREFIX
from starlette.requests import Request


def validate_app_html_jwt(token: str, request: Request) -> bool:
    """Accept a link (an ``abi:delegated:app`` grant) that opens the requested
    path. Name kept: it validates what a request to ``/app-html/`` presents. A
    session is no credential here: the page's own link is, which the web app
    makes for the signed-in user."""
    if not token.startswith(GRANT_KEY_PREFIX):
        return False
    link = links.open_link(token, APP_AUDIENCE)
    if link is None or not link.resource.startswith(links.APP_HTML_ROOT):
        return False
    path = request.url.path
    if not path.startswith(link.resource):
        return False
    if link.resource == links.APP_HTML_ROOT:
        return True
    # A lock is an app's folder: the file asked for must be that app's, not one
    # of a module whose path continues it (``a.b`` app ``c`` vs module ``a.b.c``).
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (  # noqa: E501
        app_html_root_of,
    )

    owner = app_html_root_of(path)
    return owner is None or owner == link.resource


def mint_app_html_access_token(
    *,
    user_id: str,
    expires_minutes: int | None = None,
    path_prefix: str | None = None,
) -> tuple[str, int]:
    """Return ``(grant, expires_in_seconds)`` for ``/app-html/`` access: a link
    for ``user_id`` that opens ``path_prefix`` (default: every app), at most
    eight hours."""
    minutes = expires_minutes or settings.app_html_access_token_expire_minutes
    resource = links.APP_HTML_ROOT
    if path_prefix:
        resource = path_prefix.strip()
        if not resource.startswith(links.APP_HTML_ROOT):
            raise ValueError("path_prefix must start with /app-html/")
    return links.mint_link(
        user_id=user_id,
        audience=APP_AUDIENCE,
        resource=resource,
        scope=(),
        minutes=minutes,
        description=f"app-html link: {resource}"[:200],
    )


def register_nexus_app_html_jwt_auth() -> None:
    """Wire Nexus JWT validation into the shared ``/app-html/`` middleware."""
    register_app_html_token_validator(validate_app_html_jwt)
