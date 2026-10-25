"""Workflows over HTTP: /api/workflows. Super admins, or scripts with ``ABI_API_KEY``.

- ``GET ""``: the workflows with their input and output schemas and triggers.
- ``POST /{module_id}/{name}/runs``: the body is the input, checked against the
  input schema (422 with the faults, nothing started). ``?wait=<seconds>`` returns
  the result when the run ends in time (200; else 202 with the run's state);
  ``Idempotency-Key`` makes a repeated start the same run (for two minutes).
- ``GET /{module_id}/runs/{run_id}``: status, result, error and steps.
- ``POST /{module_id}/runs/{run_id}/cancel``: cooperative; cancels its children too.

Every start and cancel is audited before it happens, with how the caller
authenticated; if the audit record cannot be written nothing is started.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    PlatformCaller,
    require_superadmin_or_api_key,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__jobs import (
    definition_view,
    invalid_input,
    run_summary,
    step_view,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    InvalidInput,
    JobNotFound,
    RunNotCancellable,
    RunNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import get_workflows_service
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
from naas_abi.apps.nexus.apps.api.app.services.workflows.workflows import (
    MAX_WAIT_SECONDS,
    Caller,
    InvalidIdempotencyKey,
    WorkflowRunView,
)

T = TypeVar("T")

router = APIRouter(dependencies=[Depends(require_superadmin_or_api_key)])


def _error(status: int, source: str, reason: str) -> HTTPException:
    return HTTPException(status, detail={"source": source, "reason": reason})


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except (JobNotFound, RunNotFound) as exc:
        raise _error(404, "workflows", str(exc)) from exc
    except RunNotCancellable as exc:
        raise _error(409, "workflows", str(exc)) from exc
    except InvalidInput as exc:
        raise invalid_input(exc) from exc
    except InvalidIdempotencyKey as exc:
        raise _error(422, "workflows", str(exc)) from exc
    except AuditUnavailable as exc:
        raise _error(503, "audit", f"Nothing was started or cancelled: {exc.reason}") from exc
    except SourceUnavailable as exc:
        raise _error(503, exc.source, exc.reason) from exc


def _caller(platform: PlatformCaller) -> Caller:
    return Caller(platform.via, platform.user_id)


def run_view(view: WorkflowRunView) -> dict[str, Any]:
    """A run as a client reads it. ``result`` is the whole of what the run returned."""
    run = view.run
    summary = run_summary(run)
    return {
        **{
            k: v
            for k, v in summary.items()
            if k not in ("job", "trigger", "instance", "skip_reason")
        },
        "workflow": run.job,
        "result": run.result,
        "steps": [step_view(s) for s in view.workflow.steps],
        "steps_truncated": view.workflow.truncated,
    }


@router.get("")
async def list_workflows(service: WorkflowsService = Depends(get_workflows_service)) -> Any:
    found = await _call(service.list())
    return {
        "workflows": [
            {**definition_view(d), "triggers": [_spec(t) for t in d.triggers]}
            for d in found.workflows
        ],
        "sources": {
            name: {"available": s.available, "reason": s.reason}
            for name, s in found.sources.items()
        },
    }


def _spec(trigger: Any) -> dict[str, Any]:
    return {
        "kind": trigger.kind,
        "spec": trigger.spec,
        "time_zone": trigger.time_zone,
        "input": trigger.input,
    }


@router.post("/{module_id}/{name}/runs")
async def start_run(
    module_id: str,
    name: str,
    response: Response,
    body: dict[str, Any] = Body(default_factory=dict),
    wait: float | None = Query(
        None,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Seconds to wait for the result; 200 with it if the run ends in time, else 202",
    ),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    caller: PlatformCaller = Depends(require_superadmin_or_api_key),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    started = await _call(
        service.start(
            _caller(caller), module_id, name, body, wait=wait, idempotency_key=idempotency_key
        )
    )
    response.status_code = 200 if started.view.finished else 202
    return run_view(started.view)


@router.get("/{module_id}/runs/{run_id}")
async def get_run(
    module_id: str,
    run_id: str,
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    return run_view(await _call(service.status(module_id, run_id)))


@router.post("/{module_id}/runs/{run_id}/cancel", status_code=202)
async def cancel_run(
    module_id: str,
    run_id: str,
    caller: PlatformCaller = Depends(require_superadmin_or_api_key),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    await _call(service.cancel(_caller(caller), module_id, run_id))
    return {"ok": True}
