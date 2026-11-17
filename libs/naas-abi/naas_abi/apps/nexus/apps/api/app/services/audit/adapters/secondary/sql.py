"""Security audit events in the Nexus database's ``audit_logs`` table (migration 0002)."""

from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.services.audit.port import AuditEvent, AuditLogPort
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

INSERT = text(
    """
    INSERT INTO audit_logs
    (id, user_id, action, resource_type, resource_id, details, ip_address, user_agent, success, created_at)
    VALUES
    (:id, :user_id, :action, :resource_type, :resource_id, :details, :ip_address, :user_agent, :success, :created_at)
    """  # noqa: E501
)


class SqlAuditLog(AuditLogPort):
    """``engine`` defaults to the API's, read when called (the database in use,
    not the one at import)."""

    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine

    def _get_engine(self) -> AsyncEngine:
        return self._engine if self._engine is not None else database.async_engine

    async def append(self, event: AuditEvent) -> None:
        async with self._get_engine().begin() as conn:
            await conn.execute(
                INSERT,
                {
                    "id": event.id,
                    "user_id": event.user_id,
                    "action": event.action,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "details": json.dumps(event.details) if event.details else None,
                    "ip_address": event.ip_address,
                    "user_agent": event.user_agent,
                    "success": event.success,
                    "created_at": event.created_at,
                },
            )
