"""Workflows over HTTP: /api/workflows. Platform admins, signed in or with their
personal API key (``abi_pk_``).

- ``GET ""``: the workflows with their input and output schemas and triggers.
- ``POST /{module_id}/{name}/runs``: the body is the input, checked against the
  input schema (422 with the faults, nothing started). ``?wait=<seconds>`` returns
  the result when the run ends in time (200; else 202 with the run's state);
  ``Idempotency-Key`` makes a repeated start the same run (for two minutes).
- ``GET /{module_id}/runs/{run_id}``: status, result, error and steps.
- ``POST /{module_id}/runs/{run_id}/cancel``: cooperative; cancels its children too.

Every start and cancel is audited before it happens, with the user and how they
signed in; if the audit record cannot be written nothing is started.

``workspace_router`` (/api/workspaces/{workspace_id}/workflows) is the same for
any user of the workspace, by module scope (``scopes.py``): the workflows and
pipelines they may start there, a start, and the runs they started there.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import API_KEY
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
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
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import RunOwner
from naas_abi.apps.nexus.apps.api.app.services.workflows.scopes import (
    runs_action,
    workflow_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
from naas_abi.apps.nexus.apps.api.app.services.workflows.workflows import (
    MAX_WAIT_SECONDS,
    Caller,
    InvalidIdempotencyKey,
    WorkflowRunView,
)

T = TypeVar("T")

router = APIRouter(dependencies=[Depends(require_superadmin)])


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
        raise invalid_input(exc, "workflows") from exc
    except InvalidIdempotencyKey as exc:
        raise _error(422, "workflows", str(exc)) from exc
    except AuditUnavailable as exc:
        raise _error(503, "audit", f"Nothing was started or cancelled: {exc.reason}") from exc
    except SourceUnavailable as exc:
        raise _error(503, exc.source, exc.reason) from exc


def _caller(request: Request, user: User) -> Caller:
    credential = getattr(request.state, "nexus_credential", None)
    via = "api_key" if getattr(credential, "kind", None) == API_KEY else "user"
    return Caller(via, user.id)


# What a client reads of the run record (an allow-list: a field added to the Jobs tab's
# run summary does not reach this API unless it is named here).
RUN_FIELDS = (
    "key",
    "module_id",
    "run_id",
    "status",
    "attempt",
    "max_attempts",
    "fired_at",
    "started_at",
    "finished_at",
    "duration_ms",
    "error",
    "trace_id",
)


def run_view(view: WorkflowRunView) -> dict[str, Any]:
    """A run as a client reads it. ``result`` is the whole of what the run returned."""
    run = view.run
    summary = run_summary(run)
    return {
        **{k: summary[k] for k in RUN_FIELDS},
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
    request: Request,
    response: Response,
    body: dict[str, Any] = Body(default_factory=dict),
    wait: float | None = Query(
        None,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description="Seconds to wait for the result; 200 with it if the run ends in time, else 202",
    ),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_superadmin),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    started = await _call(
        service.start(
            _caller(request, user),
            module_id,
            name,
            body,
            wait=wait,
            idempotency_key=idempotency_key,
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
    request: Request,
    user: User = Depends(require_superadmin),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    await _call(service.cancel(_caller(request, user), module_id, run_id))
    return {"ok": True}


# -- in a workspace, by module scope --------------------------------------------------

workspace_router = APIRouter(
    dependencies=[Depends(get_current_user_required), guard("GetWorkspace")]
)


@workspace_router.get(
    "", dependencies=[declares("module:RunWorkflow"), declares("module:RunPipeline")]
)
async def list_workspace_workflows(
    workspace_id: str,
    user: User = Depends(get_current_user_required),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    """The workflows and pipelines the caller may start in the workspace."""
    found = await _call(service.list())
    usable = await authz.filter_scopes(
        found.workflows,
        user=user,
        workspace=workspace_id,
        scope_of=lambda d: workflow_scope(d.module_id, d.name),
    )
    return {
        "workflows": [
            {
                **definition_view(d),
                "type": workflow_scope(d.module_id, d.name).type,
                "triggers": [_spec(t) for t in d.triggers],
            }
            for d in usable
        ],
        "sources": {
            name: {"available": s.available, "reason": s.reason}
            for name, s in found.sources.items()
        },
    }


@workspace_router.post(
    "/{module_id}/{name}/runs",
    dependencies=[declares("module:RunWorkflow"), declares("module:RunPipeline")],
)
async def start_workspace_run(
    workspace_id: str,
    module_id: str,
    name: str,
    request: Request,
    response: Response,
    body: dict[str, Any] = Body(default_factory=dict),
    wait: float | None = Query(None, ge=0, le=MAX_WAIT_SECONDS),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user_required),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    """Start a run in the workspace, for the caller (``module:RunWorkflow`` or
    ``RunPipeline`` there). The run is the caller's: they read it here."""
    await authz.require_scope(workflow_scope(module_id, name), user=user, workspace=workspace_id)
    started = await _call(
        service.start_in(
            _caller(request, user),
            workspace_id,
            module_id,
            name,
            body,
            wait=wait,
            idempotency_key=idempotency_key,
        )
    )
    response.status_code = 200 if started.view.finished else 202
    return run_view(started.view)


def _own_run_view(owner: RunOwner) -> dict[str, Any]:
    return {
        "module_id": owner.module_id,
        "workflow": owner.workflow,
        "type": workflow_scope(owner.module_id, owner.workflow).type,
        "run_id": owner.run_id,
        "started_at": owner.started_at.isoformat(),
    }


@workspace_router.get(
    "/runs",
    dependencies=[declares("module:ReadWorkflowRuns"), declares("module:ReadPipelineRuns")],
)
async def list_own_runs(
    workspace_id: str,
    user: User = Depends(get_current_user_required),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    """The runs the caller started in the workspace, of the workflows and
    pipelines whose runs they may still read there."""
    owners = await _call(service.own_runs(user.id, workspace_id))
    readable: list[RunOwner] = []
    for kind_scope_action in {runs_action(workflow_scope(o.module_id, o.workflow)) for o in owners}:
        readable += await authz.filter_scopes(
            [
                o
                for o in owners
                if runs_action(workflow_scope(o.module_id, o.workflow)) == kind_scope_action
            ],
            user=user,
            workspace=workspace_id,
            scope_of=lambda o: workflow_scope(o.module_id, o.workflow),
            action=kind_scope_action,
        )
    readable.sort(key=lambda o: o.started_at, reverse=True)
    return {"runs": [_own_run_view(o) for o in readable]}


@workspace_router.get(
    "/{module_id}/runs/{run_id}",
    dependencies=[declares("module:ReadWorkflowRuns"), declares("module:ReadPipelineRuns")],
)
async def get_own_run(
    workspace_id: str,
    module_id: str,
    run_id: str,
    user: User = Depends(get_current_user_required),
    service: WorkflowsService = Depends(get_workflows_service),
) -> Any:
    """A run the caller started in the workspace: status, result, error, steps."""
    owner, view = await _call(service.own_run(user.id, workspace_id, module_id, run_id))
    scope = workflow_scope(owner.module_id, owner.workflow)
    await authz.require_scope(scope, user=user, workspace=workspace_id, action=runs_action(scope))
    return run_view(view)
