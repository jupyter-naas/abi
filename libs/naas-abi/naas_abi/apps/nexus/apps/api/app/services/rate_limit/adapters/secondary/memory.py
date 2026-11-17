"""Rate-limited attempts in process memory (tests, single-process dev)."""

from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.rate_limit.port import RateLimitStorePort


class MemoryRateLimitStore(RateLimitStorePort):
    def __init__(self) -> None:
        self._attempts: list[tuple[str, str, datetime]] = []

    async def count_since(self, identifier: str, endpoint: str, since: datetime) -> int:
        return sum(
            1
            for who, where, at in self._attempts
            if who == identifier and where == endpoint and at >= since
        )

    async def record(self, identifier: str, endpoint: str, at: datetime) -> None:
        self._attempts.append((identifier, endpoint, at))

    async def prune(self, before: datetime) -> None:
        self._attempts = [attempt for attempt in self._attempts if attempt[2] >= before]
