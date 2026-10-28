"""Fakes for the IAM admin tests: an audit log that remembers (and can break),
and a fixed directory of organizations and workspaces."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import (
    OrganizationScopes,
    ScopeDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AuditEntry,
    AuditRecord,
    AuditUnavailable,
)


class MemoryAudit:
    """``AdminAuditLog`` in memory, the records oldest first in ``records``."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.broken = False
        self.broken_after: int | None = None

    async def record(self, record: AuditRecord) -> None:
        if self.broken or (
            self.broken_after is not None and len(self.records) >= self.broken_after
        ):
            raise AuditUnavailable("OperationalError")
        self.records.append(record)

    async def history(
        self, *, service: str | None = None, resource_id: str | None = None, limit: int = 50
    ) -> list[AuditEntry]:
        entries = [
            AuditEntry(
                at="2026-10-20T10:00:00+00:00",
                actor_id=r.action.actor_id,
                actor=r.action.actor_id,
                service=r.action.service,
                operation=r.action.operation,
                resource_id=r.action.resource_id,
                phase=r.phase,
                error=r.error,
                detail=r.action.detail,
            )
            for r in reversed(self.records)
            if (service is None or r.action.service == service)
            and (resource_id is None or r.action.resource_id == resource_id)
        ]
        return entries[:limit]

    def phases(self, operation: str) -> list[str]:
        return [r.phase for r in self.records if r.action.operation == operation]


class MemoryDirectory(ScopeDirectory):
    """``ScopeDirectory`` over a fixed list of organizations."""

    def __init__(self, organizations: list[OrganizationScopes]) -> None:
        self.found = organizations

    async def organizations(self, org_id: str | None = None) -> list[OrganizationScopes]:
        return [o for o in self.found if org_id is None or o.id == org_id]
