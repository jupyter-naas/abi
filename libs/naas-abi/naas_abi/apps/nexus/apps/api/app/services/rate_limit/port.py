"""Secondary port: where rate-limited attempts are counted."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class RateLimitStorePort(ABC):
    """Attempts per (identifier, endpoint), with the time each was made.

    Times are naive UTC, as the service passes them.
    """

    @abstractmethod
    async def count_since(self, identifier: str, endpoint: str, since: datetime) -> int:
        """How many attempts ``identifier`` made against ``endpoint`` at or after ``since``."""

    @abstractmethod
    async def record(self, identifier: str, endpoint: str, at: datetime) -> None:
        """Count one attempt made at ``at``."""

    @abstractmethod
    async def prune(self, before: datetime) -> None:
        """Forget every attempt made before ``before``."""
