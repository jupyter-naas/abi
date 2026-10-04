"""Module jobs over HTTP: /api/admin/system/jobs. Super admins only.

Reads: the overview (jobs, schedules, next ticks, recent runs, queue depth), run
pages across jobs, one run with its logs and trace link, and the runs that failed
since a time (the Jobs tab's notification). Actions: trigger a
job and cancel a running run, both audited before they happen.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_jobs_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    JobNotFound,
    JobRun,
    JobView,
    RunNotCancellable,
    RunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from pydantic import BaseModel, Field

T = TypeVar("T")

jobs_router = APIRouter(dependencies=[Depends(require_superadmin)])


class TriggerRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


def _error(status: int, source: str, reason: str) -> HTTPException:
    return HTTPException(status, detail={"source": source, "reason": reason})


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except (JobNotFound, RunNotFound) as exc:
        raise _error(404, "jobs", str(exc)) from exc
    except RunNotCancellable as exc:
        raise _error(409, "jobs", str(exc)) from exc
    except AuditUnavailable as exc:
        raise _error(503, "audit", f"No change made: {exc.reason}") from exc
    except SourceUnavailable as exc:
        raise _error(503, exc.source, exc.reason) from exc


def run_summary(run: JobRun) -> dict[str, Any]:
    return {
        "key": run.key,
        "module_id": run.module_id,
        "job": run.job,
        "run_id": run.run_id,
        "status": run.status,
        "attempt": run.attempt,
        "max_attempts": run.max_attempts,
        "trigger": {"kind": run.trigger.kind, "scheduler": run.trigger.scheduler},
        "fired_at": run.fired_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "instance": run.instance,
        "error": run.error,
        "trace_id": run.trace_id,
    }


def run_detail(run: JobRun, trace_url: str | None) -> dict[str, Any]:
    return {
        **run_summary(run),
        "payload": run.payload,
        "result": run.result,
        "logs": list(run.logs),
        "trace_url": trace_url,
    }


def job_view(view: JobView) -> dict[str, Any]:
    d = view.definition
    return {
        "key": d.key,
        "module_id": d.module_id,
        "name": d.name,
        "description": d.description,
        "location": d.location,
        "instances": d.instances,
        "triggers": [
            {
                "kind": t.trigger.kind,
                "spec": t.trigger.spec,
                "time_zone": t.trigger.time_zone,
                "summary": t.summary,
                "next_at": t.next_at,
            }
            for t in view.triggers
        ],
        "next_at": view.next_at,
        "max_concurrency": d.max_concurrency,
        "max_attempts": d.max_attempts,
        "timeout_seconds": d.timeout_seconds,
        "queued": view.queued,
        "in_flight": view.in_flight,
        "running": view.running,
        "last_run": run_summary(view.last_run) if view.last_run else None,
        "recent": [run_summary(r) for r in view.recent],
    }


@jobs_router.get("")
async def overview(admin: JobsAdminService = Depends(get_jobs_admin)) -> Any:
    found = await _call(admin.overview())
    return {
        "project": found.project,
        "jobs": [job_view(v) for v in found.jobs],
        "sources": {
            name: {"available": s.available, "reason": s.reason}
            for name, s in found.sources.items()
        },
    }


@jobs_router.get("/runs")
async def runs(
    module: str | None = None,
    job: str | None = None,
    status: str | None = Query(None, description="Comma-separated statuses"),
    trigger: str | None = None,
    before: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    admin: JobsAdminService = Depends(get_jobs_admin),
) -> Any:
    statuses = [s.strip().upper() for s in status.split(",") if s.strip()] if status else None
    page = await _call(
        admin.runs(
            module=module or None,
            job=job or None,
            statuses=statuses,
            trigger_kind=trigger or None,
            before=before or None,
            limit=limit,
        )
    )
    return {"runs": [run_summary(r) for r in page.runs], "next": page.next}


@jobs_router.get("/failures")
async def failures(
    since: str | None = Query(None, description="ISO time; default: the last day"),
    admin: JobsAdminService = Depends(get_jobs_admin),
) -> Any:
    """Runs that failed or timed out since ``since``: the Jobs tab's notification."""
    found = await _call(admin.failures(since=since or None))
    return {
        "since": found.since,
        "count": found.count,
        "more": found.more,
        "runs": [run_summary(r) for r in found.runs],
    }


@jobs_router.get("/runs/{module_id}/{run_id}")
async def run_detail_route(
    module_id: str, run_id: str, admin: JobsAdminService = Depends(get_jobs_admin)
) -> Any:
    found, trace_url = await _call(admin.run(module_id, run_id))
    return run_detail(found, trace_url)


@jobs_router.post("/runs/{module_id}/{run_id}/cancel", status_code=202)
async def cancel_run(
    module_id: str,
    run_id: str,
    user: User = Depends(get_current_user_required),
    admin: JobsAdminService = Depends(get_jobs_admin),
) -> Any:
    await _call(admin.cancel(user.id, module_id, run_id))
    return {"ok": True}


@jobs_router.post("/{module_id}/{job}/trigger", status_code=202)
async def trigger_job(
    module_id: str,
    job: str,
    body: TriggerRequest = Body(default_factory=TriggerRequest),
    user: User = Depends(get_current_user_required),
    admin: JobsAdminService = Depends(get_jobs_admin),
) -> Any:
    run_id = await _call(admin.trigger(user.id, module_id, job, body.payload))
    return {"run_id": run_id, "key": f"{module_id}/{run_id}"}
