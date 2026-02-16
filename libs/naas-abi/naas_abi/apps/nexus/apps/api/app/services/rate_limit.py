"""
Rate Limiting Middleware
Protects auth endpoints from brute force attacks.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, Request, status
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from sqlalchemy import text


async def check_rate_limit(identifier: str, endpoint: str) -> None:
    """
    Check if the identifier (IP or user) has exceeded the rate limit.

    Args:
        identifier: IP address or user_id
        endpoint: Endpoint being accessed

    Raises:
        HTTPException: If rate limit is exceeded
    """
    if not settings.rate_limit_enabled:
        return

    # Calculate the window start time
    window_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        seconds=settings.rate_limit_window_seconds
    )
    # removed isoformat

    async with async_engine.begin() as conn:
        # Count recent attempts
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

        if count >= settings.rate_limit_login_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Please try again in {settings.rate_limit_window_seconds // 60} minutes.",
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )

        # Record this attempt
        event_id = f"rl-{uuid4().hex[:12]}"
        now = datetime.now(UTC).replace(tzinfo=None)
        await conn.execute(
            text("""
                INSERT INTO rate_limit_events (id, identifier, endpoint, created_at)
                VALUES (:id, :identifier, :endpoint, :created_at)
            """),
            {"id": event_id, "identifier": identifier, "endpoint": endpoint, "created_at": now},
        )


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
