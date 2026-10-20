"""Remote agent runs over HTTP: /api/admin/system/agents. Super admins only.

Reads: run pages across the modules that host agents, and one run with its
events and trace link. Action: cancel a running run, audited before it happens.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import (
    AgentEvent,
    AgentRun,
    AgentRunNotCancellable,
    AgentRunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents_service import AgentsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_agents_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable

T = TypeVar("T")

agents_router = APIRouter(dependencies=[Depends(require_superadmin)])


def _error(status: int, source: str, reason: str) -> HTTPException:
    return HTTPException(status, detail={"source": source, "reason": reason})


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except AgentRunNotFound as exc:
        raise _error(404, "agents", str(exc)) from exc
    except AgentRunNotCancellable as exc:
        raise _error(409, "agents", str(exc)) from exc
    except AuditUnavailable as exc:
        raise _error(503, "audit", f"No change made: {exc.reason}") from exc
    except SourceUnavailable as exc:
        raise _error(503, exc.source, exc.reason) from exc


def run_summary(run: AgentRun) -> dict[str, Any]:
    return {
        "key": run.key,
        "module_id": run.module_id,
        "run_id": run.run_id,
        "agent": run.agent,
        "invocation_id": run.invocation_id,
        "status": run.status,
        "thread_id": run.thread_id,
        "caller": run.caller,
        "owner": run.owner,
        "submitted_at": run.submitted_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "trace_id": run.trace_id,
        "events": run.events,
    }


def _event(event: AgentEvent) -> dict[str, Any]:
    return {
        "sequence": event.sequence,
        "event": event.event,
        "preview": event.preview,
        "truncated": event.truncated,
    }


@agents_router.get("/runs")
async def runs(
    module: str | None = None,
    agent: str | None = None,
    status: str | None = Query(None, description="Comma-separated statuses"),
    before: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    admin: AgentsAdminService = Depends(get_agents_admin),
) -> Any:
    statuses = [s.strip().upper() for s in status.split(",") if s.strip()] if status else None
    page = await _call(
        admin.runs(
            module=module or None,
            agent=agent or None,
            statuses=statuses,
            before=before or None,
            limit=limit,
        )
    )
    return {"runs": [run_summary(r) for r in page.runs], "next": page.next}


@agents_router.get("/runs/{module_id}/{run_id}")
async def run_detail(
    module_id: str, run_id: str, admin: AgentsAdminService = Depends(get_agents_admin)
) -> Any:
    found, events, trace_url = await _call(admin.run(module_id, run_id))
    return {
        **run_summary(found),
        "event_list": [_event(e) for e in events],
        "trace_url": trace_url,
    }


@agents_router.post("/runs/{module_id}/{run_id}/cancel", status_code=202)
async def cancel_run(
    module_id: str,
    run_id: str,
    user: User = Depends(get_current_user_required),
    admin: AgentsAdminService = Depends(get_agents_admin),
) -> Any:
    await _call(admin.cancel(user.id, module_id, run_id))
    return {"ok": True}
