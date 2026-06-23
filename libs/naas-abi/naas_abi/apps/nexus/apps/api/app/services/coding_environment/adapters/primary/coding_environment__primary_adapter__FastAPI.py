"""Coding environments FastAPI primary adapter.

Per-user browser coding environments (Coder-backed) exposed to Nexus:
provision / start / stop / delete / status / access, plus template listing.

Scoping: every operation requires membership of the given Nexus ``workspace_id``
(org) via ``require_workspace_access``. Per-environment ownership binding (so a
member can only act on their own environment ids) lands with the Nexus
persistence table — see RFC section 9. Listing a user's environments also
requires that table and is intentionally not exposed here yet.

The core ``CodingEnvironmentService`` is synchronous, so every call is offloaded
to a worker thread via ``run_in_threadpool`` to avoid blocking the event loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    AgentNeverConnectedError,
    CodingEnvironmentError,
    ProvisionFailedError,
    ProvisionTimeoutError,
    QuotaExceededError,
    TemplateNotFoundError,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


_HTTP_STATUS_BY_ERROR: dict[type[CodingEnvironmentError], int] = {
    WorkspaceNotFoundError: 404,
    TemplateNotFoundError: 404,
    WorkspaceNameConflictError: 409,
    QuotaExceededError: 429,
    AccessDeniedError: 403,
    ProvisionFailedError: 502,
    ProvisionTimeoutError: 504,
    AgentNeverConnectedError: 504,
}


def _http_error(exc: CodingEnvironmentError) -> HTTPException:
    status_code = _HTTP_STATUS_BY_ERROR.get(type(exc), 502)
    return HTTPException(status_code=status_code, detail=str(exc) or type(exc).__name__)


def _get_coding_environment_service(request: Request) -> CodingEnvironmentService:
    service = getattr(request.app.state, "coding_environment", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        module = ABIModule.get_instance()
        service = module.engine.services.coding_environment
        request.app.state.coding_environment = service
        return service
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Coding environment service is not initialized.",
        ) from exc


class EnvironmentProvisionRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    template_id: str = Field(..., min_length=1, max_length=200)
    branch: str | None = Field(default=None, max_length=200)
    params: dict[str, str] | None = None


class EnvironmentResponse(BaseModel):
    id: str
    name: str
    phase: str
    agent_ready: bool


class EnvironmentAccessResponse(BaseModel):
    url: str
    expires_at: str | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    active_version_id: str


def _to_env(status: WorkspaceStatus) -> EnvironmentResponse:
    return EnvironmentResponse(
        id=status.id,
        name=status.name,
        phase=status.phase,
        agent_ready=status.agent_ready,
    )


def _to_template(template: WorkspaceTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        name=template.name,
        active_version_id=template.active_version_id,
    )


@router.get("/templates")
async def list_templates(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> list[TemplateResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        templates = await run_in_threadpool(service.list_templates)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return [_to_template(template) for template in templates]


@router.post("")
async def provision_environment(
    body: EnvironmentProvisionRequest,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> EnvironmentResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    params = dict(body.params or {})
    if body.branch:
        params["branch"] = body.branch
    try:
        user_id = await run_in_threadpool(
            service.ensure_user,
            external_id=current_user.id,
            email=str(current_user.email),
            username=current_user.name,
        )
        status = await run_in_threadpool(
            service.provision,
            user_id=user_id,
            template_id=body.template_id,
            name=body.name,
            params=params or None,
        )
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.get("/{environment_id}")
async def get_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> EnvironmentResponse:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        status = await run_in_threadpool(service.get_status, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.post("/{environment_id}/start")
async def start_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> EnvironmentResponse:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        status = await run_in_threadpool(service.start, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.post("/{environment_id}/stop")
async def stop_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> EnvironmentResponse:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        status = await run_in_threadpool(service.stop, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.delete("/{environment_id}")
async def delete_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> dict[str, str]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        await run_in_threadpool(service.delete, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return {"status": "deleted"}


@router.get("/{environment_id}/access")
async def get_environment_access(
    environment_id: str,
    workspace_id: str,
    app_slug: str = "code-server",
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> EnvironmentAccessResponse:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        user_id = await run_in_threadpool(
            service.ensure_user,
            external_id=current_user.id,
            email=str(current_user.email),
            username=current_user.name,
        )
        access = await run_in_threadpool(
            service.get_access,
            workspace_id=environment_id,
            user_id=user_id,
            app_slug=app_slug,
        )
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return EnvironmentAccessResponse(url=access.url, expires_at=access.expires_at)
