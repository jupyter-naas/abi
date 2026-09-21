"""App projects HTTP adapter: ``/api/app-projects`` and ``/app-preview/``.

Every route checks workspace membership, like Slides. The preview route is
public by URL but gated by a scoped token in the path (see
``preview_token.py``); it serves the live draft in an opaque origin
(``Content-Security-Policy: sandbox``), so an app's code can never read the
Nexus session.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.factory import (
    AppProjectsUnavailableError,
    build_app_projects_service,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppAuthor,
    AppFileError,
    AppFileNotFoundError,
    AppProjectError,
    AppProjectExistsError,
    AppProjectInfo,
    AppProjectKey,
    AppProjectNotFoundError,
    AppSubmitUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.preview_token import (
    mint_preview_token,
    read_preview_token,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    SourceControlError,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# Opaque origin: scripts, forms, popups and dialogs work; storage, cookies
# and same-origin API calls do not.
PREVIEW_SANDBOX = "sandbox allow-scripts allow-forms allow-popups allow-modals allow-downloads"
PREVIEW_MESSAGE_SOURCE = "nexus-app-preview"
_HEAD_RE = re.compile(r"<head(\s[^>]*)?>", re.IGNORECASE)
# <script ... src="relative"...>: the app's own scripts (not CDNs).
_OWN_SCRIPT_RE = re.compile(
    r"<script\b(?P<attrs>[^>]*?\bsrc\s*=\s*(?P<q>[\"'])(?!https?:|//|data:|blob:)[^\"']*(?P=q)[^>]*)>",
    re.IGNORECASE,
)
# Runs first in every previewed page:
# * in-memory localStorage/sessionStorage: the opaque origin makes the real
#   ones throw, and many apps touch them on load (auth gates, themes);
# * reports runtime errors to the Nexus editor (the Apps agent sees them).
_BRIDGE = (
    "<script>(function(){"
    "function mem(){var d={};return{getItem:function(k){return Object.prototype."
    "hasOwnProperty.call(d,k)?d[k]:null},setItem:function(k,v){d[k]=String(v)},"
    "removeItem:function(k){delete d[k]},clear:function(){d={}},key:function(i){"
    "return Object.keys(d)[i]||null},get length(){return Object.keys(d).length}}}"
    "['localStorage','sessionStorage'].forEach(function(n){try{window[n].length}"
    "catch(e){try{Object.defineProperty(window,n,{configurable:true,value:mem()})}"
    "catch(_){}}});"
    "if(window.parent===window)return;"
    f"var S='{PREVIEW_MESSAGE_SOURCE}';"
    "function send(m){try{window.parent.postMessage({source:S,type:'error',"
    "message:String(m).slice(0,500)},'*')}catch(e){}}"
    "window.addEventListener('error',function(e){send((e.message||'Error')+"
    "(e.filename?' ('+e.filename.split('/').pop()+':'+e.lineno+')':''))});"
    "window.addEventListener('unhandledrejection',function(e){send('Unhandled promise rejection: '+"
    "((e.reason&&e.reason.message)||e.reason))});"
    "var ce=console.error;console.error=function(){send([].slice.call(arguments).join(' '));"
    "return ce.apply(console,arguments)};"
    "window.parent.postMessage({source:S,type:'load'},'*')})();</script>"
)
_TEXT_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".webmanifest": "application/manifest+json",
}


# -- schemas ------------------------------------------------------------------


class FileEntryResponse(BaseModel):
    path: str
    size: int = 0


class ProjectResponse(BaseModel):
    slug: str
    title: str
    description: str = ""
    icon_emoji: str = ""
    workspace_id: str
    repo_id: str
    branch: str
    root: str
    entry: str | None = None
    dirty: bool = False
    commit_sha: str | None = None
    updated_at: str | None = None
    archived: bool = False
    origin: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    files: list[FileEntryResponse] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    icon_emoji: str = Field(default="", max_length=16)


class ProjectImportRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    app_id: str = Field(..., min_length=3, max_length=300)
    title: str | None = Field(default=None, max_length=120)


class ProjectUpdateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=120)
    archived: bool | None = None


class FileContentResponse(BaseModel):
    path: str
    size: int
    content: str | None = None
    binary: bool = False


class FileWriteRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1, max_length=300)
    content: str
    encoding: str = Field(default="utf-8", pattern="^(utf-8|base64)$")


class SaveRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    message: str | None = Field(default=None, max_length=300)


class WorkspaceRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)


class SubmitRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    module: str | None = Field(default=None, max_length=200)


class CommitResponse(BaseModel):
    sha: str
    message: str
    author: str
    date: str | None = None


class SaveResponse(BaseModel):
    saved: bool
    commit: CommitResponse | None = None


class IssueResponse(BaseModel):
    level: str
    message: str
    path: str | None = None


class PreviewTokenResponse(BaseModel):
    path: str
    expires_in: int


class SubmissionResponse(BaseModel):
    branch: str
    url: str | None = None
    commit_sha: str | None = None
    pull_request_url: str | None = None
    target_path: str = ""
    submitted_at: str | None = None


class SubmitConfigResponse(BaseModel):
    configured: bool
    repo: str | None = None
    base_branch: str | None = None
    modules: list[str] = Field(default_factory=list)
    default_module: str | None = None


# -- helpers ------------------------------------------------------------------


def get_app_projects_service() -> AppProjectsService:
    try:
        return build_app_projects_service()
    except AppProjectsUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, (AppProjectNotFoundError, AppFileNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, AppProjectExistsError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, AppFileError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, AppSubmitUnavailableError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, AppProjectsUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, AppProjectError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SourceControlError):
        logger.warning("app projects git error: %s", exc)
        return HTTPException(status_code=502, detail="Git storage error. Retry in a moment.")
    raise exc


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - translated, else re-raised
        raise _http_error(exc) from exc


def _key(workspace_id: str, slug: str) -> AppProjectKey:
    try:
        return AppProjectKey(workspace_id, slug)
    except AppProjectError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _author(user: User) -> AppAuthor:
    email = str(user.email or "")
    return AppAuthor(user_id=str(user.id), name=user.name or email.split("@")[0], email=email)


def _project(info: AppProjectInfo) -> ProjectResponse:
    meta = info.meta
    return ProjectResponse(
        slug=meta.slug,
        title=meta.title,
        description=meta.description,
        icon_emoji=meta.icon_emoji,
        workspace_id=meta.workspace_id,
        repo_id=settings.coding_repo_id or "abi/monorepo",
        branch=info.branch,
        root=info.root,
        entry=info.entry,
        dirty=info.dirty,
        commit_sha=info.commit_sha,
        updated_at=meta.updated_at,
        archived=meta.archived,
        origin=meta.to_json().get("origin"),
        submission=meta.to_json().get("submission"),
        files=[FileEntryResponse(path=f.path, size=f.size) for f in info.files],
    )


def media_type_for(path: str) -> str:
    suffix = ("." + path.rsplit(".", 1)[-1].lower()) if "." in path else ""
    guessed = _TEXT_TYPES.get(suffix) or mimetypes.guess_type(path)[0]
    guessed = guessed or "application/octet-stream"
    if guessed.startswith("text/") or guessed in ("application/json", "image/svg+xml"):
        return f"{guessed}; charset=utf-8"
    return guessed


def _cors_own_scripts(text: str) -> str:
    """From the opaque origin an app's own scripts are cross-origin, so their
    errors reach the bridge as "Script error." unless loaded with CORS (the
    preview answers with ``Access-Control-Allow-Origin: *``). CDN scripts are
    left alone: forcing CORS on a host without the header would break them."""

    def _add(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        if "crossorigin" in attrs.lower():
            return match.group(0)
        return f'<script{attrs} crossorigin="anonymous">'

    return _OWN_SCRIPT_RE.sub(_add, text)


def prepare_preview_html(html: bytes) -> bytes:
    """What the preview serves for an HTML page: bridge first, CORS scripts."""
    return inject_bridge(_cors_own_scripts(html.decode("utf-8", "replace")).encode("utf-8"))


def inject_bridge(html: bytes) -> bytes:
    text = html.decode("utf-8", "replace")
    match = _HEAD_RE.search(text)
    if match:
        at = match.end()
        return (text[:at] + _BRIDGE + text[at:]).encode("utf-8")
    return (_BRIDGE + text).encode("utf-8")


# -- routes -------------------------------------------------------------------


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    workspace_id: str,
    include_archived: bool = False,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> list[ProjectResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    infos = await _run(service.list_projects, workspace_id, include_archived=include_archived)
    return [_project(info) for info in infos]


@router.get("/submit-config", response_model=SubmitConfigResponse)
async def submit_config(
    service: AppProjectsService = Depends(get_app_projects_service),
) -> SubmitConfigResponse:
    return SubmitConfigResponse(**(await _run(service.submit_config)))


@router.post("/", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreateRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    info = await _run(
        service.create_project,
        body.workspace_id,
        title=body.title,
        author=_author(current_user),
        description=body.description,
        icon_emoji=body.icon_emoji or "✨",
    )
    return _project(info)


@router.post("/import", response_model=ProjectResponse)
async def import_module_app(
    body: ProjectImportRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> ProjectResponse:
    """Duplicate a module app into a new project ("Edit" works like create)."""
    await require_workspace_access(current_user.id, body.workspace_id)
    info = await _run(
        service.import_module_app,
        body.workspace_id,
        app_id=body.app_id,
        author=_author(current_user),
        title=body.title,
    )
    return _project(info)


@router.get("/{slug}", response_model=ProjectResponse)
async def get_project(
    slug: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, workspace_id)
    return _project(await _run(service.get_project, _key(workspace_id, slug)))


@router.patch("/{slug}", response_model=ProjectResponse)
async def update_project(
    slug: str,
    body: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    key = _key(body.workspace_id, slug)
    await _run(
        service.update_project,
        key,
        author=_author(current_user),
        title=body.title,
        archived=body.archived,
    )
    return _project(await _run(service.get_project, key))


@router.get("/{slug}/file", response_model=FileContentResponse)
async def read_file(
    slug: str,
    workspace_id: str,
    path: str,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> FileContentResponse:
    await require_workspace_access(current_user.id, workspace_id)
    data: bytes = await _run(service.read_file, _key(workspace_id, slug), path)
    try:
        return FileContentResponse(path=path, size=len(data), content=data.decode("utf-8"))
    except UnicodeDecodeError:
        return FileContentResponse(path=path, size=len(data), binary=True)


@router.put("/{slug}/file", response_model=FileEntryResponse)
async def write_file(
    slug: str,
    body: FileWriteRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> FileEntryResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    if body.encoding == "base64":
        try:
            data: bytes | str = base64.b64decode(body.content, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="content is not valid base64") from exc
    else:
        data = body.content
    written = await _run(service.write_file, _key(body.workspace_id, slug), body.path, data)
    return FileEntryResponse(path=written.path, size=written.size)


@router.delete("/{slug}/file")
async def delete_file(
    slug: str,
    workspace_id: str,
    path: str,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> dict[str, bool]:
    await require_workspace_access(current_user.id, workspace_id)
    await _run(service.delete_file, _key(workspace_id, slug), path)
    return {"deleted": True}


@router.post("/{slug}/save", response_model=SaveResponse)
async def save_project(
    slug: str,
    body: SaveRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> SaveResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    commit = await _run(
        service.save,
        _key(body.workspace_id, slug),
        author=_author(current_user),
        message=body.message,
    )
    if commit is None:
        return SaveResponse(saved=False)
    return SaveResponse(saved=True, commit=CommitResponse(**asdict(commit)))


@router.post("/{slug}/discard", response_model=ProjectResponse)
async def discard_draft(
    slug: str,
    body: WorkspaceRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    key = _key(body.workspace_id, slug)
    await _run(service.discard, key)
    return _project(await _run(service.get_project, key))


@router.get("/{slug}/history", response_model=list[CommitResponse])
async def project_history(
    slug: str,
    workspace_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> list[CommitResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    commits = await _run(service.history, _key(workspace_id, slug), max(1, min(limit, 100)))
    return [CommitResponse(**asdict(c)) for c in commits]


@router.get("/{slug}/check", response_model=list[IssueResponse])
async def check_project(
    slug: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> list[IssueResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    issues = await _run(service.check, _key(workspace_id, slug))
    return [IssueResponse(**asdict(i)) for i in issues]


@router.post("/{slug}/preview-token", response_model=PreviewTokenResponse)
async def preview_token(
    slug: str,
    body: WorkspaceRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> PreviewTokenResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    key = _key(body.workspace_id, slug)
    await _run(service.get_project, key)  # 404 before minting
    minutes = settings.app_preview_token_expire_minutes
    token = mint_preview_token(
        secret=settings.secret_key,
        user_id=str(current_user.id),
        workspace_id=key.workspace_id,
        slug=key.slug,
        minutes=minutes,
    )
    return PreviewTokenResponse(path=f"/app-preview/{token}/", expires_in=minutes * 60)


@router.post("/{slug}/submit", response_model=SubmissionResponse)
async def submit_project(
    slug: str,
    body: SubmitRequest,
    current_user: User = Depends(get_current_user_required),
    service: AppProjectsService = Depends(get_app_projects_service),
) -> SubmissionResponse:
    """Save, then open a review branch in the app's source repository."""
    await require_workspace_access(current_user.id, body.workspace_id)
    submission = await _run(
        service.submit,
        _key(body.workspace_id, slug),
        author=_author(current_user),
        module=body.module,
    )
    return SubmissionResponse(**asdict(submission))


# -- preview (mounted at the app root by main.py) -------------------------------


async def serve_app_preview(
    token: str,
    path: str = "",
    service: AppProjectsService = Depends(get_app_projects_service),
) -> Response:
    grant = read_preview_token(token, secret=settings.secret_key)
    if grant is None:
        raise HTTPException(status_code=401, detail="Preview link expired. Reload the editor.")
    try:
        key = AppProjectKey(grant.workspace_id, grant.slug)
    except AppProjectError as exc:
        raise HTTPException(status_code=401, detail="Invalid preview link.") from exc
    data, served = await _run(service.preview_file, key, path)
    media_type = media_type_for(served)
    if media_type.startswith("text/html"):
        data = prepare_preview_html(data)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Security-Policy": PREVIEW_SANDBOX,
            "Cache-Control": "no-store",
            # Opaque-origin pages load module scripts and fetch() JSON with CORS.
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def redirect_app_preview_root(token: str) -> RedirectResponse:
    """Relative URLs in the app need the trailing slash."""
    return RedirectResponse(url=f"/app-preview/{token}/", status_code=307)
