"""
Rate limiting: the token exchange, and the invitation routes (per inviting user, per
address, per invitation and, for the mail they send, per organization a day),
against abuse.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, Request, status
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from sqlalchemy import text


async def ensure_under_limit(
    identifier: str, endpoint: str, limit: int, window_seconds: int | None = None
) -> None:
    """Raise 429 when ``identifier`` already has ``limit`` recorded attempts in the
    window (``rate_limit_window_seconds`` unless given)."""
    if not settings.rate_limit_enabled:
        return

    window = settings.rate_limit_window_seconds if window_seconds is None else window_seconds
    window_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=window)
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT COUNT(*) as count
                FROM rate_limit_events
                WHERE identifier = :identifier
                  AND endpoint = :endpoint
                  AND created_at >= :window_start
            """),
            {"identifier": identifier, "endpoint": endpoint, "window_start": window_start},
        )
        count = result.fetchone().count

    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please try again in {max(window // 60, 1)} minutes.",
            headers={"Retry-After": str(window)},
        )


async def record_attempt(identifier: str, endpoint: str) -> None:
    """Count one attempt by ``identifier`` against ``endpoint``."""
    if not settings.rate_limit_enabled:
        return

    async with async_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO rate_limit_events (id, identifier, endpoint, created_at)
                VALUES (:id, :identifier, :endpoint, :created_at)
            """),
            {
                "id": f"rl-{uuid4().hex[:12]}",
                "identifier": identifier,
                "endpoint": endpoint,
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            },
        )


async def check_rate_limit(
    identifier: str,
    endpoint: str,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> None:
    """Refuse once ``identifier`` hit ``limit`` attempts, then count this one.

    Counts every call. For sign-in attempts that should only count failures,
    use ``ensure_under_limit`` then ``record_attempt`` on failure.
    """
    await ensure_under_limit(
        identifier,
        endpoint,
        settings.rate_limit_attempts if limit is None else limit,
        window_seconds,
    )
    await record_attempt(identifier, endpoint)


INVITATION_MAIL = "/api/invitations/mail"
_DAY_SECONDS = 24 * 60 * 60


async def check_invitation_mail_quota(
    organization_id: str | None, workspace_id: str | None
) -> None:
    """Count one invitation email against the day's quota of the organization (or of
    the workspace, for one in none): ``invitation_mails_per_day``."""
    scope = f"org:{organization_id}" if organization_id else f"ws:{workspace_id or '-'}"
    await check_rate_limit(scope, INVITATION_MAIL, settings.invitation_mails_per_day, _DAY_SECONDS)


async def cleanup_old_rate_limit_events() -> None:
    """Clean up rate limit events older than 24 hours (background task)."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    # cutoff_str removed

    async with async_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM rate_limit_events WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )


def get_rate_limit_identifier(request: Request, user_id: str | None = None) -> str:
    """Get the identifier for rate limiting (user_id if authenticated, otherwise IP)."""
    if user_id:
        return f"user:{user_id}"
    if request.client:
        return f"ip:{request.client.host}"
    return "unknown"
