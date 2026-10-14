"""Ending a user's remote app grants before they expire.

A grant is a link: whoever holds it opens the app as its user. Each request it
makes is checked against the user's revocations, rows of ``revoked_tokens``
(the latest ``revoked_at`` of the user):

* ``revoke_remote_app_grants`` writes one at every logout
  (``AuthService.logout_user``), at a password change and on request (``POST
  /api/apps/remote-grant/revoke``): it ends every grant the user got before
  it, on every device;
* the session token a logout revokes is a row of its own.

A grant row lasts as long as the longest grant (LONGEST_GRANT), so no grant it
ended outlives it: the cleanup job removes it after. A credential issued before
the user's latest revocation (``credential_revoked``) mints no grant either, so
a logged-out browser's cookie or token cannot open the app again. Answers are
cached CACHE_SECONDS per user, so a revocation takes effect within that.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from sqlalchemy import text

CACHE_SECONDS = 5.0
MAX_CACHED_USERS = 10_000
# The longest a grant lives (remote_app_grant_expire_minutes is at most a day).
LONGEST_GRANT = timedelta(hours=24)
REASON = "remote_app_grants"

# user id -> (when it was read, the user's latest revocation)
_latest: dict[str, tuple[float, datetime | None]] = {}


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


async def revoke_remote_app_grants(user_id: str) -> None:
    """End every grant the user holds now."""
    now = datetime.now(UTC).replace(tzinfo=None)
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO revoked_tokens "
                "(jti, user_id, revoked_at, revoked_reason, expires_at) "
                "VALUES (:jti, :user_id, :revoked_at, :reason, :expires_at)"
            ),
            {
                "jti": f"app-remote-{uuid4().hex}",
                "user_id": user_id,
                "revoked_at": now,
                "reason": REASON,
                "expires_at": now + LONGEST_GRANT,
            },
        )
    _latest.pop(user_id, None)


async def _latest_revocation(user_id: str) -> datetime | None:
    now = asyncio.get_running_loop().time()
    cached = _latest.get(user_id)
    if cached is not None and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT MAX(revoked_at) FROM revoked_tokens WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        latest = result.scalar_one_or_none()
    if isinstance(latest, str):  # SQLite returns the text it stored
        latest = datetime.fromisoformat(latest)
    if len(_latest) >= MAX_CACHED_USERS:
        _latest.clear()
    _latest[user_id] = (now, latest)
    return latest


async def credential_revoked(user_id: str, claims: dict) -> bool:
    """Whether a Nexus credential (a session or scoped token) may no longer
    mint a grant: its ``jti`` is revoked, or it was issued (``iat``) before
    the user's latest revocation. A token without ``iat`` (minted before it
    was added) is judged by its ``jti`` only."""
    from naas_abi.apps.nexus.apps.api.app.services.refresh_token import (
        is_access_token_revoked,
    )

    jti, issued = claims.get("jti"), claims.get("iat")
    if isinstance(jti, str) and jti and await is_access_token_revoked(jti):
        return True
    if isinstance(issued, bool) or not isinstance(issued, int | float):
        return False
    return await grant_revoked(user_id, datetime.fromtimestamp(issued, UTC))


async def grant_revoked(user_id: str, issued_at: datetime) -> bool:
    """Whether the user logged out, or revoked their grants, since ``issued_at``
    (a grant's ``iat``)."""
    latest = await _latest_revocation(user_id)
    return latest is not None and latest >= _naive_utc(issued_at)
