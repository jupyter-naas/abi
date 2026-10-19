"""Coding environments FastAPI primary adapter.

Per-user browser coding environments (Coder-backed) exposed to Nexus:
provision / start / stop / delete / status / access, plus template listing.

Authorization: every route is behind the ``code`` feature of the request's
``workspace_id`` (``ReadCode`` to read, ``WriteCode`` to change anything; the
default repository is ``SetDefaultRepo``, an admin action). Repositories and
environments are kernel resources, decided by the kernel with the user's role
once placed in the workspace: a repository named by a request must belong to
that workspace (``repo_access``), write access on it is granted only after IAM
let the user write it, and an environment is personal to its owner
(``environment/<owner>/<id>``) and to the workspace it was provisioned for.

The core ``CodingEnvironmentService`` is synchronous, so every call is offloaded
to a worker thread via ``run_in_threadpool`` to avoid blocking the event loop.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import replace
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    CodingEnvironmentModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment import agent_credentials
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.primary.coding_environment__primary_adapter__guard import (  # noqa: E501
    KernelRoute,
    authorize_environment,
    authorize_repo,
    get_iam,
    source_control_error,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.repo_access import (
    RepoNameTaken,
    belongs_to_workspace,
    grant_write,
    place_created_repo,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi_core.engine.call_context import current_call_context, use_call_context
from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
    _sanitize_coder_username,
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
from naas_abi_core.services.iam.IAMPorts import IIAMService, ResourceNotFoundError
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    Repo,
    RepoExistsError,
    RepoNotFoundError,
    SourceControlError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
    repo_key,
)
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)], route_class=KernelRoute)


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


def _default_repo_id(provided: str | None) -> str:
    """The repo to act on: an explicit one, else the configured default."""
    return provided or settings.coding_repo_id


def _repo_owner() -> str:
    """Owner under which new repos are created (from the default repo id)."""
    return settings.coding_repo_id.split("/", 1)[0] if settings.coding_repo_id else ""


def _public_clone_url(repo_id: str) -> str:
    """Externally-reachable HTTPS clone URL a developer pushes to from a laptop."""
    return f"{settings.coding_git_public_base.rstrip('/')}/{repo_id}.git"


def _to_repo_item(repo: Repo) -> RepoListItem:
    repo_id = f"{repo.owner}/{repo.name}"
    clone_url = repo.clone_url if repo.clone_url.startswith("file:") else _public_clone_url(repo_id)
    return RepoListItem(
        repo_id=repo_id,
        name=repo.name,
        default_branch=repo.default_branch,
        clone_url=clone_url,
        description=repo.description,
        private=repo.private,
        empty=repo.empty,
        updated_at=repo.updated_at,
    )


# Port the in-workspace exec sidecar listens on (must match the workspace
# template's sidecar launch in .deploy/docker/coder_prototype/template/main.tf).
_SIDECAR_PORT = 8378


async def _mint_agent_token(
    user_id: str,
    workspace_id: str | None,
    ws_base: str | None,
    label: str = "",
) -> str:
    """The key the in-workspace agent (the Continue extension) authenticates to
    the OpenAI gateway with, as the user: a personal key made for this
    environment, bound to its sidecar (``ws_base``, which the gateway resolves
    to the sidecar's secret server-side) and narrowed to its workspace
    (``agent_credentials``). Never a session token."""
    return await run_in_threadpool(
        agent_credentials.mint_agent_key,
        user_id=user_id,
        workspace_id=workspace_id,
        sidecar_base=ws_base,
        label=label,
    )


def _coder_username(name: str | None, email: str) -> str:
    """The Coder username for this user — same derivation the Coder adapter uses
    for ``ensure_user``, so it matches the workspace owner in the container name
    ``coder-<owner>-<workspace>``."""
    return _sanitize_coder_username(name or "") or _sanitize_coder_username(email.split("@", 1)[0])


def _continue_agent_ids() -> list[str]:
    """Agent ids to surface in Continue's model picker: every agent the OpenAI
    gateway exposes (minus internal ``_``-prefixed ones), with the configured
    default first so it is Continue's default selection."""
    default = settings.coding_default_agent
    try:
        # Reuse the gateway's own enumeration so the IDE list mirrors /v1/models.
        from naas_abi.apps.nexus.apps.api.app.services.openai_gateway.adapters.primary.openai_gateway__primary_adapter__FastAPI import (  # noqa: E501
            _list_agent_model_ids,
        )

        ids = [a for a in _list_agent_model_ids() if not a.startswith("_")]
    except Exception:
        ids = []
    ordered = ([default] if default and default in ids else []) + [a for a in ids if a != default]
    return ordered or ([default] if default else ["AbiAgent"])


def _prepare_clone(
    sc: SourceControlService,
    *,
    repo_id: str,
    external_id: str,
    email: str,
    display_name: str,
    source_branch: str,
    new_branch: str | None,
) -> tuple[str, str]:
    """Ensure the caller can push to ``repo_id`` on the right branch, and return
    ``(authenticated_clone_url, checkout_branch)``.

    Branch model: a workspace is created *on* ``source_branch`` (an existing
    branch); if ``new_branch`` is given it is created from ``source_branch``
    (branch-per-workspace) and becomes the checkout target.
    """
    username = _forge_username(display_name, email)
    sc.ensure_user(external_id=external_id, email=email, username=username)
    # Per-user push: the user pushes branch-per-workspace changes to a shared
    # monorepo they don't own, so they need write access. The caller checked
    # ``_authorize_repo(..., write=True)`` first.
    grant_write(sc, repo_id, username)

    if new_branch:
        existing = {b.name for b in sc.list_branches(repo_id=repo_id)}
        if new_branch not in existing:
            sc.create_branch(repo_id=repo_id, name=new_branch, from_ref=source_branch)
        checkout = new_branch
    else:
        checkout = source_branch

    repos = sc.list_repos()
    repo = next((item for item in repos if f"{item.owner}/{item.name}" == repo_id), None)
    if repo and repo.clone_url.startswith("file:"):
        return repo.clone_url, checkout

    token = sc.mint_git_token()
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
    # Which repo to clone (defaults to the configured repo when omitted).
    repo_id: str | None = Field(default=None, max_length=200)
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
    # The repo this workspace was cloned from ("owner/name"), when known.
    repo_id: str | None = None
    # Coder dashboard URL (https://coder…/@owner/name) when resolvable.
    ui_url: str | None = None


class BranchResponse(BaseModel):
    name: str
    protected: bool = False


class LogsResponse(BaseModel):
    lines: list[str]


class BranchCreateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    source_branch: str = Field(default="main", max_length=200)
    repo_id: str | None = Field(default=None, max_length=200)


class RepoListItem(BaseModel):
    repo_id: str
    name: str
    default_branch: str = ""
    clone_url: str = ""
    description: str = ""
    private: bool = True
    empty: bool = False
    updated_at: str | None = None


class ContentEntryResponse(BaseModel):
    name: str
    path: str
    type: str
    size: int = 0


class FileContentResponse(BaseModel):
    path: str
    name: str
    size: int
    text: str | None = None
    is_binary: bool = False


class CommitResponse(BaseModel):
    sha: str
    message: str
    author: str
    date: str | None = None


class RepoCreateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    private: bool = True
    # Initialize with a README (vs. a truly empty repo you push existing code to).
    auto_init: bool = False


class GitTokenRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str | None = Field(default=None, max_length=200)


class GitTokenResponse(BaseModel):
    username: str
    token: str


class DefaultRepoResponse(BaseModel):
    repo_id: str


class DefaultRepoRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    repo_id: str = Field(..., min_length=1, max_length=200)


class RepoResponse(BaseModel):
    repo_id: str


class EnvironmentAccessResponse(BaseModel):
    url: str
    expires_at: str | None = None
    # Coder dashboard URL for the workspace (https://coder…/@owner/name).
    ui_url: str | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    active_version_id: str


def _to_env(
    status: WorkspaceStatus,
    repo_id: str | None = None,
    ui_url: str | None = None,
) -> EnvironmentResponse:
    return EnvironmentResponse(
        id=status.id,
        name=status.name,
        phase=status.phase,
        agent_ready=status.agent_ready,
        repo_id=repo_id,
        ui_url=ui_url,
    )


def _to_template(template: WorkspaceTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        name=template.name,
        active_version_id=template.active_version_id,
    )


async def _orchestrator_user(service: CodingEnvironmentService, user: User) -> str:
    """The caller's orchestrator user, ensured: the service names an environment
    by its owner, which it finds again (after a restart) only once the owner's
    orchestrator user is ensured."""
    return await run_in_threadpool(
        service.ensure_user,
        external_id=user.id,
        email=str(user.email),
        username=user.name,
    )


@router.get(
    "/templates",
    dependencies=[guard("ReadCode"), declares("coding_environment:ListTemplates")],
)
async def list_templates(
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
) -> list[TemplateResponse]:
    try:
        templates = await run_in_threadpool(service.list_templates)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return [_to_template(template) for template in templates]


@router.get(
    "/repos",
    dependencies=[guard("ReadCode"), declares("source_control:ListRepos")],
)
async def list_repos(
    workspace_id: str,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> list[RepoListItem]:
    """Repositories the user can work in (for the repo selector): this
    workspace's and the shared deployment repository, surfaced first."""
    if source_control is None or iam is None:
        return []
    try:
        repos = await run_in_threadpool(source_control.list_repos)
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [
        _to_repo_item(r)
        for r in repos
        if await run_in_threadpool(belongs_to_workspace, iam, f"{r.owner}/{r.name}", workspace_id)
    ]
    default = settings.coding_repo_id
    items.sort(key=lambda i: (i.repo_id != default, i.repo_id.lower()))
    return items


@router.post(
    "/repos",
    dependencies=[declares("WriteCode"), declares("source_control:EnsureRepo")],
)
async def create_repo(
    body: RepoCreateRequest,
    current_user: User = Depends(get_current_user_required),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
    db: AsyncSession = Depends(get_db),
) -> RepoListItem:
    """Create a repository for this workspace, placed in it, and make the
    creator a writer."""
    await authz.require("WriteCode", user=current_user, workspace=body.workspace_id)
    if source_control is None or not _repo_owner():
        raise HTTPException(status_code=503, detail="No git backend configured.")
    if iam is None:
        raise HTTPException(status_code=503, detail="Authorization is unavailable.")
    username = _forge_username(current_user.name or "", str(current_user.email))
    repo_id = f"{_repo_owner()}/{body.name}"
    row = (
        await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == body.workspace_id))
    ).scalar_one_or_none()
    taken = HTTPException(status_code=409, detail="That repository name is taken.")

    def create() -> Repo:
        # Created in the workspace's own call context, so the kernel places the
        # new repository there (the create rule, RFC §4.4) and checks the user's
        # role on it: a workspace role reaches it, the platform's ``EnsureRepo``
        # is not needed. ``create_repo`` never returns a repository that existed,
        # in any letter case, so nothing that existed is ever placed here or
        # granted.
        context = current_call_context()
        with use_call_context(replace(context, workspace_id=body.workspace_id)):
            return source_control.create_repo(
                owner=_repo_owner(),
                name=body.name,
                private=body.private,
                # auto_init=False -> a truly empty repo, so an existing local
                # history can be pushed to it (the "create new repo, then push"
                # onboarding flow).
                auto_init=body.auto_init,
            )

    try:
        repo = await run_in_threadpool(create)
    except (RepoExistsError, RepoNotFoundError, ResourceNotFoundError):
        # Not found, for a create, is a name another workspace or the platform
        # holds. A refusal of the caller's own (``PermissionDeniedError``) is a 403.
        raise taken from None
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if repo_key(f"{repo.owner}/{repo.name}") != repo_key(repo_id):
        raise taken
    try:
        await run_in_threadpool(
            place_created_repo,
            iam,
            repo,
            body.workspace_id,
            getattr(row, "organization_id", None),
        )
        await authorize_repo(iam, repo_id, body.workspace_id, write=True)
        # Repos are owned by the platform account, so grant the creator write
        # access — otherwise their push is rejected as "repository not found".
        await run_in_threadpool(
            source_control.ensure_user,
            external_id=current_user.id,
            email=str(current_user.email),
            username=username,
        )
        await run_in_threadpool(grant_write, source_control, repo_id, username)
    except RepoNameTaken:
        raise taken from None
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_repo_item(repo)


@router.get(
    "/repo-contents",
    dependencies=[guard("ReadCode"), declares("source_control:ListContents")],
)
async def repo_contents(
    workspace_id: str,
    repo_id: str | None = None,
    path: str = "",
    ref: str | None = None,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> list[ContentEntryResponse]:
    """Directory listing at ``path`` on ``ref`` — powers the repo file browser."""
    repo = _default_repo_id(repo_id)
    if not repo or source_control is None:
        return []
    await authorize_repo(iam, repo, workspace_id, write=False)
    try:
        entries = await run_in_threadpool(
            source_control.list_contents, repo_id=repo, path=path, ref=ref
        )
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return [
        ContentEntryResponse(name=e.name, path=e.path, type=e.type, size=e.size) for e in entries
    ]


@router.get(
    "/repo-file",
    dependencies=[guard("ReadCode"), declares("source_control:GetFile")],
)
async def repo_file(
    workspace_id: str,
    path: str,
    repo_id: str | None = None,
    ref: str | None = None,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> FileContentResponse:
    repo = _default_repo_id(repo_id)
    if not repo or source_control is None:
        raise HTTPException(status_code=503, detail="No git backend configured.")
    await authorize_repo(iam, repo, workspace_id, write=False)
    try:
        f = await run_in_threadpool(source_control.get_file, repo_id=repo, path=path, ref=ref)
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return FileContentResponse(
        path=f.path, name=f.name, size=f.size, text=f.text, is_binary=f.is_binary
    )


@router.get(
    "/repo-commits",
    dependencies=[guard("ReadCode"), declares("source_control:ListCommits")],
)
async def repo_commits(
    workspace_id: str,
    repo_id: str | None = None,
    ref: str | None = None,
    limit: int = 20,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> list[CommitResponse]:
    repo = _default_repo_id(repo_id)
    if not repo or source_control is None:
        return []
    await authorize_repo(iam, repo, workspace_id, write=False)
    try:
        commits = await run_in_threadpool(
            source_control.list_commits, repo_id=repo, ref=ref, limit=limit
        )
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return [
        CommitResponse(sha=c.sha, message=c.message, author=c.author, date=c.date) for c in commits
    ]


@router.post(
    "/git-token",
    dependencies=[declares("WriteCode"), declares("source_control:MintGitToken")],
)
async def generate_git_token(
    body: GitTokenRequest,
    current_user: User = Depends(get_current_user_required),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> GitTokenResponse:
    """Mint a personal git access token for the caller (shown once) and grant
    write access on ``repo_id``, when the caller may write it, so they can push
    to it from outside."""
    await authz.require("WriteCode", user=current_user, workspace=body.workspace_id)
    if source_control is None:
        raise HTTPException(status_code=503, detail="No git backend configured.")
    username = _forge_username(current_user.name or "", str(current_user.email))
    repo_id = _default_repo_id(body.repo_id)
    if repo_id:
        await authorize_repo(iam, repo_id, body.workspace_id, write=True)
    try:
        await run_in_threadpool(
            source_control.ensure_user,
            external_id=current_user.id,
            email=str(current_user.email),
            username=username,
        )
        if repo_id:
            await run_in_threadpool(grant_write, source_control, repo_id, username)
        # The token is the caller's: the service mints for the call's user.
        token = await run_in_threadpool(source_control.mint_git_token)
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return GitTokenResponse(username=username, token=token)


@router.get("/default-repo", dependencies=[guard("ReadCode")])
async def get_default_repo(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
) -> DefaultRepoResponse:
    """The team-shared default repo for new workspaces in this Nexus workspace."""
    row = (
        await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
    ).scalar_one_or_none()
    repo_id = (row.coding_default_repo_id if row else None) or settings.coding_repo_id
    return DefaultRepoResponse(repo_id=repo_id)


@router.put("/default-repo", dependencies=[declares("SetDefaultRepo")])
async def set_default_repo(
    body: DefaultRepoRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    iam: IIAMService | None = Depends(get_iam),
) -> DefaultRepoResponse:
    await authz.require(
        "SetDefaultRepo",
        user=current_user,
        workspace=body.workspace_id,
        denied="Only a workspace owner/admin can set the default repo.",
    )
    await authorize_repo(iam, body.repo_id, body.workspace_id, write=False)
    row = (
        await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == body.workspace_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    row.coding_default_repo_id = body.repo_id
    await db.commit()
    return DefaultRepoResponse(repo_id=body.repo_id)


@router.get(
    "/branches",
    dependencies=[guard("ReadCode"), declares("source_control:ListBranches")],
)
async def list_repo_branches(
    workspace_id: str,
    repo_id: str | None = None,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> list[BranchResponse]:
    """Branches of a repo (defaults to the configured one), for picking a source
    branch. Empty when no repo / git backend is configured."""
    repo = _default_repo_id(repo_id)
    if not repo or source_control is None:
        return []
    await authorize_repo(iam, repo, workspace_id, write=False)
    try:
        branches = await run_in_threadpool(source_control.list_branches, repo_id=repo)
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return [BranchResponse(name=b.name, protected=b.protected) for b in branches]


@router.post(
    "/branches",
    dependencies=[declares("WriteCode"), declares("source_control:CreateBranch")],
)
async def create_repo_branch(
    body: BranchCreateRequest,
    current_user: User = Depends(get_current_user_required),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> BranchResponse:
    await authz.require("WriteCode", user=current_user, workspace=body.workspace_id)
    repo = _default_repo_id(body.repo_id)
    if not repo or source_control is None:
        raise HTTPException(status_code=503, detail="No git backend configured.")
    await authorize_repo(iam, repo, body.workspace_id, write=True)
    try:
        branch = await run_in_threadpool(
            source_control.create_branch,
            repo_id=repo,
            name=body.name,
            from_ref=body.source_branch,
        )
    except BranchNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return BranchResponse(name=branch.name, protected=branch.protected)


@router.delete(
    "/branches",
    dependencies=[guard("WriteCode"), declares("source_control:DeleteBranch")],
)
async def delete_repo_branch(
    workspace_id: str,
    name: str,
    repo_id: str | None = None,
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    iam: IIAMService | None = Depends(get_iam),
) -> dict[str, bool]:
    """Delete a branch. ``name`` may contain slashes (url-encoded)."""
    repo = _default_repo_id(repo_id)
    if not repo or source_control is None:
        raise HTTPException(status_code=503, detail="No git backend configured.")
    await authorize_repo(iam, repo, workspace_id, write=True)
    try:
        await run_in_threadpool(source_control.delete_branch, repo_id=repo, name=name)
    except SourceControlError as exc:
        raise source_control_error(exc) from exc
    return {"ok": True}


@router.get("/repo", dependencies=[guard("ReadCode")])
async def get_repo() -> RepoResponse:
    """The default repo id (back-compat for callers without a selector)."""
    return RepoResponse(repo_id=settings.coding_repo_id)


@router.get(
    "",
    dependencies=[guard("ReadCode"), declares("coding_environment:ListEnvironments")],
)
async def list_environments(
    workspace_id: str,
    repo_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    db: AsyncSession = Depends(get_db),
) -> list[EnvironmentResponse]:
    try:
        user_id = await _orchestrator_user(service, current_user)
        envs = await run_in_threadpool(service.list_environments, user_id=user_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    # Attach each workspace's source repo (recorded at provision) and, when a
    # repo filter is given, show only that repo's workspaces. Workspaces with no
    # recorded binding (e.g. provisioned before this was tracked) are excluded
    # from a filtered view rather than leaking into every repo.
    repo_by_env = await _repo_by_env(db, workspace_id, [e.id for e in envs])
    if repo_id:
        envs = [e for e in envs if repo_by_env.get(e.id) == repo_id]
    return [_to_env(env, repo_by_env.get(env.id)) for env in envs]


async def _repo_by_env(
    db: AsyncSession, workspace_id: str, env_ids: list[str]
) -> dict[str, str | None]:
    """Map Coder workspace id -> its recorded source repo for this workspace."""
    if not env_ids:
        return {}
    rows = (
        await db.execute(
            select(CodingEnvironmentModel.id, CodingEnvironmentModel.repo_id).where(
                CodingEnvironmentModel.workspace_id == workspace_id,
                CodingEnvironmentModel.id.in_(env_ids),
            )
        )
    ).all()
    return dict(rows)


@router.post(
    "",
    dependencies=[
        declares("WriteCode"),
        declares("coding_environment:Provision"),
        declares("source_control:UpsertFile"),
    ],
)
async def provision_environment(
    body: EnvironmentProvisionRequest,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    db: AsyncSession = Depends(get_db),
    iam: IIAMService | None = Depends(get_iam),
) -> EnvironmentResponse:
    await authz.require("WriteCode", user=current_user, workspace=body.workspace_id)
    params = dict(body.params or {})
    checkout_branch = body.branch or body.source_branch
    repo_id = _default_repo_id(body.repo_id)
    if repo_id and source_control is not None:
        # Cloning grants the caller write on the repository: only when they may.
        await authorize_repo(iam, repo_id, body.workspace_id, write=True)

    # Auto-clone the chosen repo on the chosen branch (when a repo + git backend
    # are configured; otherwise the workspace just opens an empty folder).
    if repo_id and source_control is not None:
        try:
            repo_url, checkout_branch = await run_in_threadpool(
                _prepare_clone,
                source_control,
                repo_id=repo_id,
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
            raise HTTPException(status_code=502, detail=f"Git setup failed: {exc}") from exc

    params["branch"] = checkout_branch
    if settings.coding_workspace_docker_network:
        params["docker_network"] = settings.coding_workspace_docker_network

    # Workspace exec-sidecar bridge: the server-side agent tools reach this
    # workspace's ~/project via a sidecar at coder-<owner>-<name>:PORT over the
    # docker network. Mint a per-workspace secret, inject it into the sidecar
    # (template param), and embed (base, secret) in the token so the shim can
    # bind the tools to this exact container. owner/name derived server-side.
    ws_secret = secrets.token_hex(16)
    coder_username = _coder_username(current_user.name, str(current_user.email))
    ws_base = (
        f"http://coder-{coder_username}-{body.name.lower()}:{_SIDECAR_PORT}"
        if coder_username
        else None
    )
    params["sidecar_secret"] = ws_secret

    # In-IDE agent bridge: give the baked-in Continue extension a long-lived
    # token + the workspace-reachable Nexus API base so it can talk to abi
    # agents through the OpenAI shim. The agent list is enumerated server-side so
    # Continue's model picker lists every agent the gateway exposes.
    params["abi_token"] = await _mint_agent_token(
        current_user.id, body.workspace_id, ws_base, label=body.name
    )
    params["abi_api_base"] = settings.coding_agent_api_base
    params["abi_agents"] = ",".join(await run_in_threadpool(_continue_agent_ids))

    def provision() -> WorkspaceStatus:
        # In the workspace's own call context (it is carried by the body, which
        # the identity middleware does not read), so the kernel places the new
        # environment in this workspace.
        with use_call_context(replace(current_call_context(), workspace_id=body.workspace_id)):
            return service.provision(
                user_id=user_id,
                template_id=body.template_id,
                name=body.name,
                params=params or None,
            )

    try:
        user_id = await _orchestrator_user(service, current_user)
        status = await run_in_threadpool(provision)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc

    sidecar_base = ws_base
    sidecar_secret = ws_secret
    binding = await run_in_threadpool(service.get_runtime_binding, workspace_id=status.id)
    if binding:
        sidecar_base, sidecar_secret = binding
        if sidecar_base != ws_base:
            # The runtime is reached elsewhere than where the key was bound.
            await run_in_threadpool(agent_credentials.revoke_agent_keys, current_user.id, ws_base)
            params["abi_token"] = await _mint_agent_token(
                current_user.id, body.workspace_id, sidecar_base, label=body.name
            )

    # Record which repo this workspace was cloned from so the workspaces list can
    # be scoped per-repo. Best-effort: the workspace already exists in Coder, so a
    # bookkeeping failure must not fail the request.
    try:
        db.add(
            CodingEnvironmentModel(
                id=status.id,
                workspace_id=body.workspace_id,
                user_id=current_user.id,
                repo_id=repo_id or None,
                sidecar_base=sidecar_base,
                sidecar_secret=sidecar_secret,
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
    return _to_env(status, repo_id or None)


class SandboxRuntimeResponse(BaseModel):
    ensured: bool
    sidecar_ready: bool = False
    harness_ready: bool = False
    environment_id: str | None = None
    label: str
    branch: str
    detail: str | None = None


def _code_runtime_label(*, workspace_id: str, repo_id: str, branch: str) -> str:
    ws = re.sub(r"[^a-zA-Z0-9._-]+", "-", workspace_id.strip()).strip("-._")
    branch_slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", branch.strip()).strip("-._")
    return f"code/{ws}/{repo_id}/{branch_slug}"


def _sandbox_workspace_name(*, workspace_id: str, repo_id: str, branch: str) -> str:
    digest = hashlib.sha1(f"{workspace_id}:{repo_id}:{branch}".encode()).hexdigest()[:10]
    return f"sbox-{digest}"


def _wait_for_sidecar(base: str, secret: str, *, timeout_s: float = 15.0) -> bool:
    req = urllib.request.Request(
        f"{base.rstrip('/')}/health",
        headers={"Authorization": f"Bearer {secret}"},
        method="GET",
    )
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(req, timeout=1.0) as resp:  # nosec B310
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("ok"):
                    return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.25)
    return False


def _wait_for_harness(base: str, *, timeout_s: float = 15.0) -> bool:
    from naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient import (  # noqa: PLC0415
        wait_for_healthy,
    )

    return wait_for_healthy(base, timeout_s=timeout_s)


async def lookup_code_bindings(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    repo_id: str,
    branch: str,
    service: CodingEnvironmentService | None = None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return sidecar_base, sidecar_secret, harness_base, environment_id."""
    label = _code_runtime_label(workspace_id=workspace_id, repo_id=repo_id, branch=branch)
    result = await db.execute(
        select(CodingEnvironmentModel).where(
            CodingEnvironmentModel.workspace_id == workspace_id,
            CodingEnvironmentModel.user_id == user_id,
            CodingEnvironmentModel.label == label,
        )
    )
    row = result.scalars().first()
    if not row or not row.sidecar_base or not row.sidecar_secret:
        return None, None, None, None
    harness_base = None
    if service is not None and row.id:
        harness_base = await run_in_threadpool(service.get_harness_binding, workspace_id=row.id)
    return (
        str(row.sidecar_base),
        str(row.sidecar_secret),
        harness_base,
        str(row.id),
    )


async def lookup_code_sidecar(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    repo_id: str,
    branch: str,
) -> tuple[str | None, str | None]:
    sidecar_base, sidecar_secret, _, _ = await lookup_code_bindings(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        repo_id=repo_id,
        branch=branch,
    )
    return sidecar_base, sidecar_secret


@router.post(
    "/sandbox/runtime",
    response_model=SandboxRuntimeResponse,
    dependencies=[
        guard("WriteCode"),
        declares("coding_environment:Provision"),
        declares("source_control:UpsertFile"),
    ],
)
async def ensure_sandbox_runtime(
    workspace_id: str,
    repo_id: str,
    branch: str = "main",
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    source_control: SourceControlService | None = Depends(_get_source_control_service),
    db: AsyncSession = Depends(get_db),
    iam: IIAMService | None = Depends(get_iam),
) -> SandboxRuntimeResponse:
    """Ensure a local sandbox + sidecar for the open repo (Slides-parity)."""
    if source_control is not None:
        await authorize_repo(iam, repo_id, workspace_id, write=True)
    label = _code_runtime_label(workspace_id=workspace_id, repo_id=repo_id, branch=branch)
    name = _sandbox_workspace_name(workspace_id=workspace_id, repo_id=repo_id, branch=branch)

    existing = await db.execute(
        select(CodingEnvironmentModel).where(
            CodingEnvironmentModel.workspace_id == workspace_id,
            CodingEnvironmentModel.user_id == current_user.id,
            CodingEnvironmentModel.label == label,
        )
    )
    row = existing.scalars().first()
    if row and row.sidecar_base and row.sidecar_secret:
        ready = await run_in_threadpool(
            _wait_for_sidecar, str(row.sidecar_base), str(row.sidecar_secret)
        )
        harness_ready = False
        if not ready:
            await run_in_threadpool(service.start, workspace_id=row.id)
            ready = await run_in_threadpool(
                _wait_for_sidecar, str(row.sidecar_base), str(row.sidecar_secret)
            )
        harness_base = await run_in_threadpool(service.get_harness_binding, workspace_id=row.id)
        if harness_base:
            harness_ready = await run_in_threadpool(_wait_for_harness, harness_base)
            if not harness_ready:
                await run_in_threadpool(service.start, workspace_id=row.id)
                harness_base = await run_in_threadpool(
                    service.get_harness_binding, workspace_id=row.id
                )
                if harness_base:
                    harness_ready = await run_in_threadpool(_wait_for_harness, harness_base)
        detail = None
        if not ready and not harness_ready:
            detail = "Sidecar and harness not reachable"
        elif not ready:
            detail = "Sidecar not reachable"
        elif harness_base and not harness_ready:
            detail = "OpenCode harness not reachable"
        return SandboxRuntimeResponse(
            ensured=True,
            sidecar_ready=ready,
            harness_ready=harness_ready,
            environment_id=row.id,
            label=label,
            branch=branch,
            detail=detail,
        )

    templates = await run_in_threadpool(service.list_templates)
    template = next((item for item in templates if item.name == "local-directory"), None)
    if template is None:
        template = templates[0] if templates else None
    if template is None:
        return SandboxRuntimeResponse(
            ensured=False,
            label=label,
            branch=branch,
            detail="No coding environment template available",
        )

    ws_secret = secrets.token_hex(16)
    params: dict[str, str] = {"branch": branch, "sidecar_secret": ws_secret}
    if source_control is not None:
        try:
            repo_url, checkout_branch = await run_in_threadpool(
                _prepare_clone,
                source_control,
                repo_id=repo_id,
                external_id=current_user.id,
                email=str(current_user.email),
                display_name=current_user.name or "",
                source_branch=branch,
                new_branch=None,
            )
            params["repo_url"] = repo_url
            params["branch"] = checkout_branch
        except SourceControlError as exc:
            return SandboxRuntimeResponse(
                ensured=False,
                label=label,
                branch=branch,
                detail=str(exc),
            )

    user_id = await _orchestrator_user(service, current_user)
    try:
        status = await run_in_threadpool(
            service.provision,
            user_id=user_id,
            template_id=template.id,
            name=name,
            params=params,
        )
    except CodingEnvironmentError as exc:
        return SandboxRuntimeResponse(
            ensured=False,
            label=label,
            branch=branch,
            detail=str(exc),
        )

    sidecar_base = None
    sidecar_secret = ws_secret
    binding = await run_in_threadpool(service.get_runtime_binding, workspace_id=status.id)
    if binding:
        sidecar_base, sidecar_secret = binding

    ready = bool(
        sidecar_base and await run_in_threadpool(_wait_for_sidecar, sidecar_base, sidecar_secret)
    )
    harness_base = await run_in_threadpool(service.get_harness_binding, workspace_id=status.id)
    harness_ready = bool(harness_base and await run_in_threadpool(_wait_for_harness, harness_base))
    try:
        db.add(
            CodingEnvironmentModel(
                id=status.id,
                workspace_id=workspace_id,
                user_id=current_user.id,
                repo_id=repo_id,
                label=label,
                sidecar_base=sidecar_base,
                sidecar_secret=sidecar_secret,
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()

    detail = None
    if not ready and not harness_ready:
        detail = "Sidecar and harness not reachable"
    elif not ready:
        detail = "Sidecar not reachable"
    elif harness_base and not harness_ready:
        detail = "OpenCode harness not reachable"

    return SandboxRuntimeResponse(
        ensured=True,
        sidecar_ready=ready,
        harness_ready=harness_ready,
        environment_id=status.id,
        label=label,
        branch=params.get("branch", branch),
        detail=detail,
    )


@router.get(
    "/{environment_id}",
    dependencies=[guard("ReadCode"), declares("coding_environment:GetStatus")],
)
async def get_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    iam: IIAMService | None = Depends(get_iam),
) -> EnvironmentResponse:
    await authorize_environment(iam, environment_id, workspace_id)
    try:
        await _orchestrator_user(service, current_user)
        status = await run_in_threadpool(service.get_status, workspace_id=environment_id)
        ui_url = await run_in_threadpool(service.get_workspace_ui_url, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status, ui_url=ui_url)


@router.get(
    "/{environment_id}/logs",
    dependencies=[guard("ReadCode"), declares("coding_environment:GetLogs")],
)
async def get_environment_logs(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    iam: IIAMService | None = Depends(get_iam),
) -> LogsResponse:
    """Recent provisioning + startup log lines, polled by the IDE to show live
    progress while a workspace is being prepared."""
    await authorize_environment(iam, environment_id, workspace_id)
    try:
        await _orchestrator_user(service, current_user)
        lines = await run_in_threadpool(service.get_logs, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return LogsResponse(lines=lines)


@router.post(
    "/{environment_id}/start",
    dependencies=[guard("WriteCode"), declares("coding_environment:Start")],
)
async def start_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    iam: IIAMService | None = Depends(get_iam),
) -> EnvironmentResponse:
    await authorize_environment(iam, environment_id, workspace_id)
    try:
        await _orchestrator_user(service, current_user)
        status = await run_in_threadpool(service.start, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.post(
    "/{environment_id}/stop",
    dependencies=[guard("WriteCode"), declares("coding_environment:Stop")],
)
async def stop_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    iam: IIAMService | None = Depends(get_iam),
) -> EnvironmentResponse:
    await authorize_environment(iam, environment_id, workspace_id)
    try:
        await _orchestrator_user(service, current_user)
        status = await run_in_threadpool(service.stop, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return _to_env(status)


@router.delete(
    "/{environment_id}",
    dependencies=[guard("WriteCode"), declares("coding_environment:Delete")],
)
async def delete_environment(
    environment_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    db: AsyncSession = Depends(get_db),
    iam: IIAMService | None = Depends(get_iam),
) -> dict[str, str]:
    await authorize_environment(iam, environment_id, workspace_id)
    bound = await db.get(CodingEnvironmentModel, environment_id)
    try:
        await _orchestrator_user(service, current_user)
        await run_in_threadpool(service.delete, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    try:
        await db.execute(
            delete(CodingEnvironmentModel).where(CodingEnvironmentModel.id == environment_id)
        )
        await db.commit()
    except Exception:
        await db.rollback()
    if bound is not None:
        # The agent's key goes with its environment.
        await agent_credentials.arevoke_agent_keys(str(bound.user_id), bound.sidecar_base)
    return {"status": "deleted"}


@router.get(
    "/{environment_id}/access",
    dependencies=[guard("WriteCode"), declares("coding_environment:GetAccess")],
)
async def get_environment_access(
    environment_id: str,
    workspace_id: str,
    app_slug: str = "code-server",
    current_user: User = Depends(get_current_user_required),
    service: CodingEnvironmentService = Depends(_get_coding_environment_service),
    iam: IIAMService | None = Depends(get_iam),
) -> EnvironmentAccessResponse:
    await authorize_environment(iam, environment_id, workspace_id)
    try:
        user_id = await _orchestrator_user(service, current_user)
        access = await run_in_threadpool(
            service.get_access,
            workspace_id=environment_id,
            user_id=user_id,
            app_slug=app_slug,
        )
        ui_url = await run_in_threadpool(service.get_workspace_ui_url, workspace_id=environment_id)
    except CodingEnvironmentError as exc:
        raise _http_error(exc) from exc
    return EnvironmentAccessResponse(url=access.url, expires_at=access.expires_at, ui_url=ui_url)
