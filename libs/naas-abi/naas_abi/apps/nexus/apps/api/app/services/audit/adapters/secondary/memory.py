"""Security audit events in process memory (tests)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.audit.port import AuditEvent, AuditLogPort


class MemoryAuditLog(AuditLogPort):
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)
