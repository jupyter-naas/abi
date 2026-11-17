"""The web app's pass: how the web app's own server routes know a browser is signed in.

The session cookie stays on the API's host, and the web app usually runs on
another one (``PUBLIC_WEB_HOST`` and ``PUBLIC_API_HOST``), so its server routes
never see it. The web app asks for a pass with the session (``POST
/api/auth/oidc/web-pass``, CSRF-checked), keeps it in an httpOnly cookie of its
own host, and its routes ask whether it is still good (``GET
/api/auth/oidc/web-pass``, the pass in ``X-Web-Pass``).

A pass is a link (``services/apps/links.py``): an IAM grant of the user,
audience ``abi:delegated:app``, bound to ``web-pass`` and narrowed to nothing.
It opens no app (the app routes take only ``/app-html/`` and ``app-remote/``
resources), is never a session, lasts eight hours at most and never longer than
the session it was made from, ends with its user (suspension, revocation) and
at sign-out, and is checked again at every request. All it says is who its user is.
"""

from __future__ import annotations

from datetime import UTC, datetime

from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi_core.engine.nats_auth import APP_AUDIENCE, GRANT_KEY_PREFIX

WEB_PASS_HEADER = "X-Web-Pass"
# Longer than any grant IAM makes (``abi_gk_<id>_<secret>``): anything longer names nothing.
MAX_PASS_LENGTH = 512


async def mint_web_pass(user_id: str, *, not_after: datetime | None = None) -> tuple[str, int]:
    """``(pass, seconds it lasts)`` for ``user_id``: eight hours at most, never past
    ``not_after`` (the session's end; naive times are UTC), nor past a view."""
    if not_after is not None and not_after.tzinfo is None:
        not_after = not_after.replace(tzinfo=UTC)
    return await links.amint_link(
        user_id=user_id,
        audience=APP_AUDIENCE,
        resource=links.WEB_PASS,
        scope=(),
        minutes=links.MAX_MINUTES,
        not_after=not_after,
        description="web pass",
    )


async def read_web_pass(value: str | None) -> tuple[str, int] | None:
    """``(user id, seconds left)`` of a live pass, None for anything else: no pass,
    another kind of link, or one IAM refuses (unknown, revoked, expired, its user
    suspended or deleted)."""
    if not value or len(value) > MAX_PASS_LENGTH or not value.startswith(GRANT_KEY_PREFIX):
        return None
    link = await links.aopen_link(value, APP_AUDIENCE)
    if link is None or link.resource != links.WEB_PASS:
        return None
    left = links.MAX_MINUTES * 60
    if link.expires_at is not None:
        expires_at = link.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        left = int((expires_at - datetime.now(UTC)).total_seconds())
        if left <= 0:
            return None
    return link.user_id, left
