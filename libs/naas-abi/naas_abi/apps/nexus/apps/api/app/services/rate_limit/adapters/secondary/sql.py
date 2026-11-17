"""Rate-limited attempts in the Nexus database's ``rate_limit_events`` table."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.services.rate_limit.port import RateLimitStorePort
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class SqlRateLimitStore(RateLimitStorePort):
    """One row per attempt. ``engine`` defaults to the API's, read when called
    (the database in use, not the one at import)."""

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine

    def _get_engine(self) -> AsyncEngine:
        return self._engine if self._engine is not None else database.async_engine

    async def count_since(self, identifier: str, endpoint: str, since: datetime) -> int:
        async with self._get_engine().begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM rate_limit_events
                    WHERE identifier = :identifier
                      AND endpoint = :endpoint
                      AND created_at >= :window_start
                """),
                {"identifier": identifier, "endpoint": endpoint, "window_start": since},
            )
            row = result.fetchone()
        return int(row.count) if row is not None else 0

    async def record(self, identifier: str, endpoint: str, at: datetime) -> None:
        async with self._get_engine().begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO rate_limit_events (id, identifier, endpoint, created_at)
                    VALUES (:id, :identifier, :endpoint, :created_at)
                """),
                {
                    "id": f"rl-{uuid4().hex[:12]}",
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "created_at": at,
                },
            )

    async def prune(self, before: datetime) -> None:
        async with self._get_engine().begin() as conn:
            await conn.execute(
                text("DELETE FROM rate_limit_events WHERE created_at < :cutoff"),
                {"cutoff": before},
            )
