"""Coding environments FastAPI primary adapter.

Per-user browser coding environments (Coder-backed) exposed to Nexus:
provision / start / stop / delete / status / access, plus template listing.

Scoping: every operation requires membership of the given Nexus ``workspace_id``
(org) via ``require_workspace_access``. Per-environment ownership binding (so a
member can only act on their own environment ids) lands with the Nexus
persistence table — see RFC section 9. Listing is scoped to the caller's own
orchestrator identity (``ensure_user`` -> owner filter), so it needs no such
table and never leaks another member's environments.

The core ``CodingEnvironmentService`` is synchronous, so every call is offloaded
to a worker thread via ``run_in_threadpool`` to avoid blocking the event loop.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
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
from naas_abi_core.services.source_control.SourceControlPorts import SourceControlError
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
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


def _get_source_control_service(request: Request) -> SourceControlService | None:
    """Resolve the source_control service, or None if it isn't configured.

    Returns None (rather than raising) so workspace provisioning degrades to a
    plain empty workspace when no git backend is wired, instead of failing.
    """
    service = getattr(request.app.state, "source_control", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        module = ABIModule.get_instance()
        service = module.engine.services.source_control
    except Exception:
        return None
    request.app.state.source_control = service
    return service


def _forge_username(name: str, email: str) -> str:
    """Map a display name / email to a valid Forgejo username.

    (lowercase alphanumeric + ``-_.``, must not start/end with a separator,
    <=39 chars). Mirrors the Coder username sanitization so the same person
    maps to a stable forge handle.
    """

    def slug(raw: str) -> str:
        return re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower()).strip("-._")[:39].strip("-._")

    return slug(name) or slug(email.split("@", 1)[0]) or "abi-user"


def _prepare_clone(
    sc: SourceControlService,
    *,
    external_id: str,
    email: str,
    display_name: str,
    source_branch: str,
    new_branch: str | None,
) -> tuple[str, str]:
    """Ensure the caller can push to the configured monorepo on the right
    branch, and return ``(authenticated_clone_url, checkout_branch)``.

    Branch model: a workspace is created *on* ``source_branch`` (an existing
    branch); if ``new_branch`` is given it is created from ``source_branch``
    (branch-per-workspace) and becomes the checkout target.
    """
    repo_id = settings.coding_repo_id
    username = _forge_username(display_name, email)
    sc.ensure_user(external_id=external_id, email=email, username=username)
    # Per-user push: the user pushes branch-per-workspace changes to a shared
    # monorepo they don't own, so they need write access.
    sc.add_collaborator(repo_id=repo_id, username=username, permission="write")

    if new_branch:
        existing = {b.name for b in sc.list_branches(repo_id=repo_id)}
        if new_branch not in existing:
            sc.create_branch(repo_id=repo_id, name=new_branch, from_ref=source_branch)
        checkout = new_branch
    else:
        checkout = source_branch

    token = sc.mint_git_token(user_id=username)
    creds = f"{quote(username, safe='')}:{quote(token, safe='')}"
    repo_url = (
        f"{settings.coding_git_clone_scheme}://{creds}"
        f"@{settings.coding_git_clone_host}/{repo_id}.git"
    )
    return repo_url, checkout


class EnvironmentProvisionRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    template_id: str = Field(..., min_length=1, max_length=200)
    # Branch model: open the workspace on `source_branch` (an existing branch);
    # if `branch` is given, create it from `source_branch` and check it out.
    source_branch: str = Field(default="main", max_length=200)
    branch: str | None = Field(default=None, max_length=200)
    params: dict[str, str] | None = None


class EnvironmentResponse(BaseModel):
    id: str
    name: str
    phase: str
    agent_ready: bool


class BranchResponse(BaseModel):
    name: str
    protected: bool = False


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


@router.get("/branches")
async def list_repo_branches(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
) -> list[BranchResponse]:
    """Branches of the monorepo, for picking a source branch when creating a
    workspace. Empty when no repo / git backend is configured."""
    await require_workspace_access(current_user.id, workspace_id)
    if not settings.coding_repo_id or source_control is None:
        return []
    try:
        branches = await run_in_threadpool(
            source_control.list_branches, repo_id=settings.coding_repo_id
        )
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [BranchResponse(name=b.name, protected=b.protected) for b in branches]


@router.get("")
async def list_environments(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> list[EnvironmentResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    try:
        user_id = await run_in_threadpool(
            service.ensure_user,
            external_id=current_user.id,
            email=str(current_user.email),
            username=current_user.name,
        )
        envs = await run_in_threadpool(service.list_environments, user_id=user_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return [_to_env(env) for env in envs]


@router.post("")
async def provision_environment(
    body: EnvironmentProvisionRequest,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
) -> EnvironmentResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    params = dict(body.params or {})
    checkout_branch = body.branch or body.source_branch

    # Auto-clone the monorepo on the chosen branch (when a repo + git backend
    # are configured; otherwise the workspace just opens an empty folder).
    if settings.coding_repo_id and source_control is not None:
        try:
            repo_url, checkout_branch = await run_in_threadpool(
                _prepare_clone,
                source_control,
                external_id=current_user.id,
                email=str(current_user.email),
                display_name=current_user.name or "",
                source_branch=body.source_branch,
                new_branch=body.branch,
            )
            params["repo_url"] = repo_url
            params["git_author_name"] = current_user.name or ""
            params["git_author_email"] = str(current_user.email)
        except SourceControlError as exc:
            raise HTTPException(
                status_code=502, detail=f"Git setup failed: {exc}"
            ) from exc

    params["branch"] = checkout_branch
    if settings.coding_workspace_docker_network:
        params["docker_network"] = settings.coding_workspace_docker_network

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
