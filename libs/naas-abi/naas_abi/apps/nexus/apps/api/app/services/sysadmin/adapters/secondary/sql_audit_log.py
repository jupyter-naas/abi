"""Admin actions in the Nexus ``audit_logs`` table (migration 0002).

Unlike ``services/audit.log_audit_event``, which swallows errors, a failed
insert raises ``AuditUnavailable``: the domain then refuses the change.
Rows: ``action`` = ``sysadmin.<operation>``, ``resource_type`` = the service,
``details`` = ``{"phase": ..., "via": ..., "error": ..., "detail": ...}`` (all but
the phase only when there are any; ``via`` is ``api_key`` for a user who called
with their personal API key), ``success`` false when failed. The IAM admin keeps its own rows
in the same table under ``iam.`` (``prefix``): one fail-closed log, two
histories.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AuditEntry,
    AuditRecord,
    AuditUnavailable,
)
from sqlalchemy import text

ACTION_PREFIX = "sysadmin."
# What history shows as the actor of a record an older release wrote for the
# deployment's ABI_API_KEY, which had no user. Every record now names its user.
API_KEY_ACTOR = "ABI API key"

INSERT = text(
    """
    INSERT INTO audit_logs
    (id, user_id, action, resource_type, resource_id, details, success, created_at)
    VALUES
    (:id, :user_id, :action, :resource_type, :resource_id, :details, :success, :created_at)
    """
)


HISTORY = """
    SELECT a.created_at, a.user_id, COALESCE(u.name, u.email, a.user_id),
           a.resource_type, a.action, a.resource_id, a.details
    FROM audit_logs a LEFT JOIN users u ON u.id = a.user_id
    WHERE a.action LIKE :prefix{filters}
    ORDER BY a.created_at DESC
    LIMIT :limit
"""


def _iso(value: Any) -> str:
    """Rows are written as naive UTC; SQLite hands them back as strings."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    return ""


class SqlAdminAuditLog:
    def __init__(self, engine: Callable[[], Any], *, prefix: str = ACTION_PREFIX) -> None:
        # A callable: the app's AsyncEngine is created lazily at startup.
        self._engine = engine
        self._prefix = prefix

    async def record(self, record: AuditRecord) -> None:
        details: dict[str, str] = {"phase": record.phase}
        if record.action.via != "user":
            details["via"] = record.action.via
        if record.error:
            details["error"] = record.error
        if record.action.detail:
            details["detail"] = record.action.detail
        try:
            async with self._engine().begin() as conn:
                await conn.execute(
                    INSERT,
                    {
                        "id": f"audit-{uuid4().hex[:12]}",
                        "user_id": record.action.actor_id,
                        "action": self._prefix + record.action.operation,
                        "resource_type": record.action.service,
                        "resource_id": record.action.resource_id,
                        "details": json.dumps(details),
                        "success": record.phase != "failed",
                        "created_at": datetime.now(UTC).replace(tzinfo=None),
                    },
                )
        except Exception as exc:  # noqa: BLE001 - any storage failure refuses the change
            raise AuditUnavailable(type(exc).__name__) from exc

    async def history(
        self, *, service: str | None = None, resource_id: str | None = None, limit: int = 50
    ) -> list[AuditEntry]:
        filters = ""
        params: dict[str, Any] = {
            "limit": max(1, min(limit, 500)),
            "prefix": self._prefix + "%",
        }
        if service is not None:
            filters += " AND a.resource_type = :service"
            params["service"] = service
        if resource_id is not None:
            filters += " AND a.resource_id = :resource_id"
            params["resource_id"] = resource_id
        try:
            async with self._engine().connect() as conn:
                rows = (await conn.execute(text(HISTORY.format(filters=filters)), params)).all()
        except Exception as exc:  # noqa: BLE001 - reported as an unavailable source
            raise AuditUnavailable(type(exc).__name__) from exc
        entries = []
        for created_at, user_id, actor, service_name, action, rid, details in rows:
            info = json.loads(details) if details else {}
            entries.append(
                AuditEntry(
                    at=_iso(created_at),
                    actor_id=user_id or "",
                    actor=actor or (API_KEY_ACTOR if info.get("via") == "api_key" else ""),
                    service=service_name or "",
                    operation=action.removeprefix(self._prefix),
                    resource_id=rid or "",
                    phase=info.get("phase", ""),
                    error=info.get("error", ""),
                    detail=info.get("detail", ""),
                )
            )
        return entries
