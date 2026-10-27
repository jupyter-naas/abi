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
pipelines of its set they may start there, a start, and the runs they started
there. Its ``/settings`` are the workspace settings page: each workflow and
pipeline of the set, on or off for everyone in the workspace (admins).
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TypeVar

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
from naas_abi.apps.nexus.apps.api.app.services.iam import sets as scope_sets
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
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
from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import (
    get_workflow_visibility,
    get_workflows_service,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import (
    RunOwner,
    WorkflowSwitch,
    WorkflowVisibilityPort,
)
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
from pydantic import BaseModel, Field

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
    """The workflows and pipelines of the workspace's set the caller may start
    there; one turned off there is left out."""
    found = await _call(service.list())
    usable = await authz.filter_scopes(
        await scope_sets.within_set(
            found.workflows,
            workspace=workspace_id,
            scope_of=lambda d: workflow_scope(d.module_id, d.name),
        ),
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


@workspace_router.get("/settings", dependencies=[guard("ListWorkflowSettings", literal="-")])
async def list_workflow_settings(
    workspace_id: str,
    user: User = Depends(get_current_user_required),
    service: WorkflowsService = Depends(get_workflows_service),
    store: WorkflowVisibilityPort = Depends(get_workflow_visibility),
) -> Any:
    """Every workflow and pipeline of the workspace's set (the jobs catalogs', and
    those an engine module's agents run as tools), on or off there."""
    from naas_abi.apps.nexus.apps.api.app.services.modules.scopes import (
        workflows as module_workflows,
    )

    found = {(i.type, i.module, i.name): i for i in await module_workflows(service)}
    listed = await authz.filter_scopes(
        await scope_sets.within_set(
            found.values(), workspace=workspace_id, scope_of=lambda i: _scope(i)
        ),
        user=user,
        workspace=workspace_id,
        scope_of=lambda i: _scope(i),
        include_hidden=True,
    )
    off = {
        (s.type, s.module_id, s.name) for s in await store.list_for(workspace_id) if not s.enabled
    }
    return {
        "workflows": [
            {
                "type": i.type,
                "module_id": i.module,
                "name": i.name,
                "display_name": i.display_name or i.name,
                "description": i.description,
                "enabled": (i.type, i.module, i.name) not in off,
            }
            for i in sorted(listed, key=lambda i: (i.module, i.type, i.name.lower()))
        ]
    }


def _scope(item: Any) -> ModuleScope:
    return ModuleScope(item.type, item.module, item.name)


class WorkflowSwitchBody(BaseModel):
    type: Literal["workflow", "pipeline"]
    module_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    enabled: bool


@workspace_router.put("/settings", dependencies=[guard("UpdateWorkflow", literal="-")])
async def put_workflow_setting(
    workspace_id: str,
    body: WorkflowSwitchBody,
    store: WorkflowVisibilityPort = Depends(get_workflow_visibility),
) -> Any:
    """Turn a workflow or pipeline on or off for everyone in the workspace. Turning
    one on needs it in the workspace's set; off, any."""
    scope = ModuleScope(body.type, body.module_id, body.name)
    if body.enabled and not await scope_sets.within_set(
        [scope], workspace=workspace_id, scope_of=lambda s: s
    ):
        raise HTTPException(
            status_code=403,
            detail=f"This {body.type} is not in the workspace's set: its organization adds "
            "its module on the Modules & features page",
        )
    await store.put(
        WorkflowSwitch(workspace_id, body.type, body.module_id, body.name, body.enabled)
    )
    return {**body.model_dump(), "workspace_id": workspace_id}


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
    # Workflows' runs and pipelines' runs are read with different actions.
    by_action: dict[str, list[RunOwner]] = {}
    for owner in await _call(service.own_runs(user.id, workspace_id)):
        by_action.setdefault(
            runs_action(workflow_scope(owner.module_id, owner.workflow)), []
        ).append(owner)
    readable: list[RunOwner] = []
    for action, owners in by_action.items():
        readable += await authz.filter_scopes(
            owners,
            user=user,
            workspace=workspace_id,
            scope_of=lambda o: workflow_scope(o.module_id, o.workflow),
            action=action,
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
