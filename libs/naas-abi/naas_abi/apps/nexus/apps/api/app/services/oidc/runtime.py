"""Build the sign-in service, and resolve the session cookie of a request.

``RUNTIME`` reads the engine's identity and IAM services; tests replace it
with ``configure``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    EngineIAMPrincipals,
    EngineIdentityGateway,
    default_iam,
    default_identity,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.postgres import (
    OidcSessionSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.service import (
    ActiveSession,
    OidcSignInService,
    csrf_matches,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import (
    encrypt_secret_value,
    try_decrypt_secret_value,
)
from naas_abi_core import logger
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers
from starlette.types import Scope

CSRF_HEADER = "x-csrf-token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# What a request is for, as the browser states it (``Sec-Fetch-Dest``): a page
# or a frame showing an API response. The cookie never authenticates one: a link
# to ``/api/...`` must not act as the user, whatever it serves.
_DOCUMENT_DESTINATIONS = frozenset(
    {"document", "iframe", "frame", "embed", "object", "fencedframe"}
)


def is_document_request(headers: Headers) -> bool:
    """A navigation, or a frame, embed or object, rather than a ``fetch`` of the web app."""
    return (
        headers.get("sec-fetch-dest", "").strip().lower() in _DOCUMENT_DESTINATIONS
        or headers.get("sec-fetch-mode", "").strip().lower() == "navigate"
    )


def redirect_uri() -> str:
    return settings.oidc_redirect_uri or (
        f"{settings.api_url.rstrip('/')}{settings.api_prefix}/auth/oidc/callback"
    )


class OidcRuntime:
    def __init__(
        self,
        identity: Callable[[], Any | None] = default_identity,
        iam: Callable[[], Any | None] = default_iam,
    ) -> None:
        self.identity = EngineIdentityGateway(identity)
        self.principals = EngineIAMPrincipals(iam)

    def service(self, db: AsyncSession) -> OidcSignInService:
        return OidcSignInService(
            OidcSessionSecondaryAdapterPostgres(db),
            self.identity,
            self.principals,
            redirect_uri=redirect_uri(),
            session_max_age=timedelta(hours=settings.oidc_session_max_age_hours),
            encrypt=encrypt_secret_value,
            decrypt=try_decrypt_secret_value,
        )


RUNTIME = OidcRuntime()


def configure(runtime: OidcRuntime) -> OidcRuntime:
    """Replace the runtime (tests); returns the previous one."""
    global RUNTIME
    previous, RUNTIME = RUNTIME, runtime
    return previous


@dataclass(frozen=True)
class CookieAuth:
    """What a request's session cookie established."""

    session: ActiveSession | None
    # The cookie names a live session, but the request changes state without
    # the session's CSRF token: it is not authenticated.
    csrf_failed: bool = False


def session_secret(headers: Headers) -> str | None:
    from http.cookies import SimpleCookie

    raw = headers.get("cookie")
    if not raw:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:  # noqa: BLE001 - a malformed header names no session
        return None
    morsel = cookie.get(settings.oidc_session_cookie)
    return morsel.value if morsel is not None and morsel.value else None


async def cookie_auth(scope: Scope) -> CookieAuth | None:
    """The session a request's cookie names, None without one. Fails closed:
    a lookup that fails authenticates nobody."""
    headers = Headers(scope=scope)
    secret = session_secret(headers)
    if secret is None:
        return None
    if is_document_request(headers):
        return CookieAuth(session=None)
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            session = await RUNTIME.service(db).resolve(secret)
    except Exception as exc:  # noqa: BLE001 - fail closed
        logger.warning(f"Session lookup failed; the request names no user: {exc}")
        return CookieAuth(session=None)
    if session is None:
        return CookieAuth(session=None)
    method = str(scope.get("method", "GET")).upper()
    if method not in _SAFE_METHODS and not csrf_matches(secret, headers.get(CSRF_HEADER)):
        return CookieAuth(session=None, csrf_failed=True)
    return CookieAuth(session=session)
