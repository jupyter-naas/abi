"""Secondary port: where security audit events are written."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    """One sensitive operation (sign-in, sign-out, ...). ``created_at`` is naive UTC."""

    id: str
    action: str
    created_at: datetime
    user_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] | None = field(default=None)
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True


class AuditLogPort(ABC):
    """Append-only: events are written, never changed."""

    @abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Write one event. Raises when it could not be written; the service decides
        whether that fails the request."""
