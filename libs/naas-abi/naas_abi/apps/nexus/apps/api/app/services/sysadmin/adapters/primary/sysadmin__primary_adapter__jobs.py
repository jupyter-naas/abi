"""Module jobs over HTTP: /api/admin/system/jobs. Super admins only.

Reads: the overview (jobs, schedules, next ticks, recent runs, queue depth), run
pages across jobs, one run with its logs and trace link, and the runs that failed
since a time (the Jobs tab's notification). Actions: trigger a
job and cancel a running run, both audited before they happen. Workflows are jobs
with ``kind``, schemas and, in a run's detail, their steps; a trigger whose
payload does not match a workflow's input schema is a 422.
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
    InvalidInput,
    JobDefinition,
    JobNotFound,
    JobRun,
    JobView,
    RunNotCancellable,
    RunNotFound,
    RunStep,
    RunView,
    TriggerView,
    WorkflowDetail,
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


def invalid_input(exc: InvalidInput) -> HTTPException:
    return HTTPException(
        422,
        detail={
            "source": "jobs",
            "reason": str(exc),
            "errors": [{"path": i.path, "message": i.message} for i in exc.issues],
        },
    )


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except (JobNotFound, RunNotFound) as exc:
        raise _error(404, "jobs", str(exc)) from exc
    except InvalidInput as exc:
        raise invalid_input(exc) from exc
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
        "skip_reason": run.skip_reason,
    }


def step_view(step: RunStep) -> dict[str, Any]:
    return {
        "key": step.key,
        "kind": step.kind,
        "status": step.status,
        "attempt": step.attempt,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
        "duration_ms": step.duration_ms,
        "error": step.error,
        # A call step's child run: ``key`` opens it like any run ("<module>/<run id>").
        "child": (
            {
                "module_id": step.child.module_id,
                "workflow": step.child.workflow,
                "run_id": step.child.run_id,
                "key": step.child.key,
            }
            if step.child
            else None
        ),
        "result_bytes": step.result_bytes,
    }


def workflow_view(detail: WorkflowDetail | None) -> dict[str, Any] | None:
    if detail is None:
        return None
    return {"steps": [step_view(s) for s in detail.steps], "truncated": detail.truncated}


def run_detail(view: RunView) -> dict[str, Any]:
    run = view.run
    return {
        **run_summary(run),
        "payload": run.payload,
        "result": run.result,
        "logs": list(run.logs),
        "trace_url": view.trace_url,
        # Only a workflow's run has one: its steps in start order.
        "workflow": workflow_view(view.workflow),
    }


def definition_view(d: JobDefinition) -> dict[str, Any]:
    """The fields a job and a workflow share, and a workflow's schemas."""
    return {
        "key": d.key,
        "module_id": d.module_id,
        "name": d.name,
        "description": d.description,
        "location": d.location,
        "instances": d.instances,
        "kind": d.kind,
        "input_schema": d.input_schema,
        "output_schema": d.output_schema,
        "max_concurrency": d.max_concurrency,
        "max_attempts": d.max_attempts,
        "timeout_seconds": d.timeout_seconds,
    }


def trigger_view(t: TriggerView) -> dict[str, Any]:
    return {
        "kind": t.trigger.kind,
        "spec": t.trigger.spec,
        "time_zone": t.trigger.time_zone,
        "input": t.trigger.input,
        "summary": t.summary,
        "next_at": t.next_at,
    }


def job_view(view: JobView) -> dict[str, Any]:
    d = view.definition
    return {
        **definition_view(d),
        "triggers": [trigger_view(t) for t in view.triggers],
        "next_at": view.next_at,
        "queued": view.queued,
        "in_flight": view.in_flight,
        "running": view.running,
        "last_run": run_summary(view.last_run) if view.last_run else None,
        "recent": [run_summary(r) for r in view.recent],
        "last_skipped": run_summary(view.last_skipped) if view.last_skipped else None,
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
    include_skipped: bool = Query(
        False, description="Without status: also runs that had nothing to do"
    ),
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
            include_skipped=include_skipped,
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
    return run_detail(await _call(admin.run(module_id, run_id)))


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
