"""Slides FastAPI primary adapter.

Business-facing slide decks stored in Forgejo (branch ``slides/<slug>``, path
``slides/<slug>/deck.html``). A Coder ``abi-slides`` workspace is provisioned
under the hood for agent sidecar access; the Nexus UI never embeds Coder.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import timedelta
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel
from naas_abi.apps.nexus.apps.api.app.services.auth.service import create_access_token
from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
    _sanitize_coder_username,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    CodingEnvironmentError,
    WorkspaceNameConflictError,
    WorkspaceStatus,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    RepoNotFoundError,
    SourceControlError,
    ValidationError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_required)])

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BRANCH_PREFIX = "slides/"
_DEFAULT_TEMPLATE = "bob-fmz-v1"
_SIDECAR_PORT = 8378
_SLIDES_TEMPLATE_NAMES = ("abi-slides", "abi-code-server")


def _get_source_control(request: Request) -> SourceControlService:
    service = getattr(request.app.state, "source_control", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        service = ABIModule.get_instance().engine.services.source_control
        request.app.state.source_control = service
        return service
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Source control (Forgejo) is not configured. Slides requires git storage.",
        ) from exc


def _get_coding_environment(request: Request) -> CodingEnvironmentService | None:
    service = getattr(request.app.state, "coding_environment", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        service = ABIModule.get_instance().engine.services.coding_environment
        request.app.state.coding_environment = service
        return service
    except Exception:
        return None


def _repo_id() -> str:
    return settings.coding_repo_id or "abi/monorepo"


def _forge_username(name: str, email: str) -> str:
    def slug(raw: str) -> str:
        return re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower()).strip("-._")[:39].strip(
            "-._"
        )

    return slug(name) or slug(email.split("@", 1)[0]) or "abi-user"


def _branch_for(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


def _deck_path(slug: str) -> str:
    return f"slides/{slug}/deck.html"


def _project_path(slug: str) -> str:
    return f"slides/{slug}/project.json"


def _assets_dir(slug: str) -> str:
    return f"slides/{slug}/assets"


def _assets_gitkeep_path(slug: str) -> str:
    return f"{_assets_dir(slug)}/.gitkeep"


def _assets_readme_path(slug: str) -> str:
    return f"{_assets_dir(slug)}/README.md"


_ASSETS_README = """# Presentation assets

Drop images and other media for this deck here.

## Seed note

The BOB / Forvis Mazars template ships images as ``data:`` URLs inside
``deck.html``. Binary extraction into this folder is deferred: Forgejo
``upsert_file`` is text-only today, and rewriting the deck to relative
``assets/`` paths would break the in-browser Preview until an asset-serving
route exists.

Manual files you add here appear in the Slides sidebar tree.
"""


def _count_embedded_images(html: str) -> int:
    return len(re.findall(r"data:image/[^;]+;base64,", html))


def _slugify(title: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return raw[:48] or "deck"


def _load_seed_html(template_id: str = _DEFAULT_TEMPLATE) -> str:
    name = f"{template_id}.html"
    # Preferred: packaged Nexus assets.
    try:
        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        text = (root / name).read_text(encoding="utf-8")
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback: walk up from this file into assets/, then Zen mirror.
    here = Path(__file__).resolve()
    candidates = [
        here.parents[7] / "assets" / "slides" / "templates" / name,
        Path("/app/src/zen/assets/slides/templates") / name,
        Path("src/zen/assets/slides/templates") / name,
    ]
    for path in candidates:
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8")
        except OSError:
            continue
    raise HTTPException(
        status_code=500,
        detail=f"Slides seed template '{template_id}' is missing from assets.",
    )


class ProjectCreateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    template_id: str = Field(default=_DEFAULT_TEMPLATE, max_length=64)


class ProjectResponse(BaseModel):
    slug: str
    title: str
    branch: str
    deck_path: str
    template_id: str = _DEFAULT_TEMPLATE
    updated_at: str | None = None
    commit_sha: str | None = None


class DeckResponse(BaseModel):
    slug: str
    path: str
    html: str
    commit_sha: str | None = None


class DeckUpdateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    html: str = Field(..., min_length=1)
    message: str = Field(default="Update slides deck", max_length=200)


class CommitResponse(BaseModel):
    sha: str
    message: str
    author: str
    date: str | None = None


class RuntimeResponse(BaseModel):
    ensured: bool
    phase: str | None = None
    environment_id: str | None = None
    template_name: str | None = None
    detail: str | None = None
    sidecar_ready: bool = False
    label: str | None = None


def _runtime_label(slug: str) -> str:
    return f"slides/{slug}"


def _coder_workspace_name(slug: str) -> str:
    return f"slides-{slug}"[:32].rstrip("-")


def _friendly_coding_detail(exc: BaseException) -> str:
    """Human detail for UX; never dump raw Coder JSON as the primary message."""
    text = str(exc or "").strip()
    lowered = text.lower()
    if (
        isinstance(exc, WorkspaceNameConflictError)
        or "already exists" in lowered
        or ("already in use" in lowered and "unique" in lowered)
    ):
        return "Reconnecting to existing runtime…"
    if "coder api request failed" in lowered and "{" in text:
        return "Coder runtime temporarily unavailable"
    if len(text) > 180 or text.startswith("{") or '"validations"' in text:
        return "Coder runtime temporarily unavailable"
    return text or "Coder runtime temporarily unavailable"


def _adapter_get_parameters(coding: CodingEnvironmentService, workspace_id: str) -> dict[str, str]:
    adapter = getattr(coding, "_adapter", None)
    getter = getattr(adapter, "get_parameters", None)
    if not callable(getter):
        return {}
    try:
        result = getter(workspace_id=workspace_id)
    except Exception:  # noqa: BLE001
        return {}
    return result if isinstance(result, dict) else {}


class TreeEntryResponse(BaseModel):
    name: str
    path: str
    type: str  # file | dir
    size: int = 0


class ProjectTreeResponse(BaseModel):
    slug: str
    root: str
    entries: list[TreeEntryResponse]
    assets: list[TreeEntryResponse] = Field(default_factory=list)
    embedded_images: int = 0
    assets_note: str | None = None


def _project_from_meta(
    *,
    slug: str,
    title: str | None = None,
    template_id: str = _DEFAULT_TEMPLATE,
    commit_sha: str | None = None,
    updated_at: str | None = None,
) -> ProjectResponse:
    return ProjectResponse(
        slug=slug,
        title=title or slug.replace("-", " ").title(),
        branch=_branch_for(slug),
        deck_path=_deck_path(slug),
        template_id=template_id,
        commit_sha=commit_sha,
        updated_at=updated_at,
    )


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> list[ProjectResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    sc = _get_source_control(request)
    repo_id = _repo_id()

    def _list() -> list[ProjectResponse]:
        branches = sc.list_branches(repo_id=repo_id)
        out: list[ProjectResponse] = []
        for branch in branches:
            if not branch.name.startswith(_BRANCH_PREFIX):
                continue
            slug = branch.name[len(_BRANCH_PREFIX) :]
            if not slug or not _SLUG_RE.match(slug):
                continue
            title = slug.replace("-", " ").title()
            template_id = _DEFAULT_TEMPLATE
            updated_at = None
            try:
                meta = sc.get_file(
                    repo_id=repo_id, path=_project_path(slug), ref=branch.name
                )
                if meta.text:
                    data = json.loads(meta.text)
                    title = str(data.get("title") or title)
                    template_id = str(data.get("template_id") or template_id)
                    updated_at = data.get("updated_at")
            except (SourceControlError, json.JSONDecodeError):
                pass
            out.append(
                _project_from_meta(
                    slug=slug,
                    title=title,
                    template_id=template_id,
                    commit_sha=branch.commit_sha,
                    updated_at=updated_at,
                )
            )
        out.sort(key=lambda p: (p.updated_at or "", p.slug), reverse=True)
        return out

    try:
        return await run_in_threadpool(_list)
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    slug = body.slug or _slugify(body.title)
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=422,
            detail="Slug must be lowercase kebab-case (a-z, 0-9, hyphens).",
        )
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)
    username = _forge_username(current_user.name or "", str(current_user.email))
    seed = _load_seed_html(body.template_id)
    author_name = current_user.name or username
    author_email = str(current_user.email)

    def _create() -> ProjectResponse:
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        sc.add_collaborator(repo_id=repo_id, username=username, permission="write")
        existing = {b.name for b in sc.list_branches(repo_id=repo_id)}
        if branch in existing:
            raise BranchNameConflictError(f"Slides project '{slug}' already exists")
        default = "main"
        try:
            repos = sc.list_repos()
            for repo in repos:
                if f"{repo.owner}/{repo.name}" == repo_id and repo.default_branch:
                    default = repo.default_branch
                    break
        except SourceControlError:
            pass
        if default not in existing and existing:
            default = next(iter(existing))
        sc.create_branch(repo_id=repo_id, name=branch, from_ref=default)
        meta = {
            "slug": slug,
            "title": body.title,
            "template_id": body.template_id,
            "updated_at": None,
        }
        embedded = _count_embedded_images(seed)
        meta = {
            **meta,
            "embedded_images": embedded,
            "assets_note": (
                "assets/ seeded empty; template images remain as data-URLs in deck.html"
            ),
        }
        sc.upsert_file(
            repo_id=repo_id,
            path=_project_path(slug),
            content=json.dumps(meta, indent=2) + "\n",
            message=f"Create slides project {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        commit = sc.upsert_file(
            repo_id=repo_id,
            path=_deck_path(slug),
            content=seed,
            message=f"Seed deck from {body.template_id}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        # Always seed assets/ so the sidebar tree matches classic deck layout.
        # Binary extract of data-URL images is deferred (text-only upsert).
        sc.upsert_file(
            repo_id=repo_id,
            path=_assets_gitkeep_path(slug),
            content="",
            message=f"Seed assets folder for {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        sc.upsert_file(
            repo_id=repo_id,
            path=_assets_readme_path(slug),
            content=_ASSETS_README,
            message=f"Document assets folder for {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        return _project_from_meta(
            slug=slug,
            title=body.title,
            template_id=body.template_id,
            commit_sha=commit.sha or None,
        )

    try:
        project = await run_in_threadpool(_create)
    except BranchNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Ensure dedicated Coder runtime (required for Abi sidecar tools). Do not
    # fail create if Coder is down; the editor will hard-retry on open.
    try:
        runtime = await _ensure_runtime_impl(
            request=request,
            workspace_id=body.workspace_id,
            slug=slug,
            current_user=current_user,
            db=db,
        )
        if not runtime.ensured:
            logger.warning(
                "slides runtime not ensured for %s: %s", slug, runtime.detail
            )
    except Exception:  # noqa: BLE001
        logger.exception("slides runtime ensure failed for %s", slug)

    return project


@router.get("/projects/{slug}", response_model=ProjectResponse)
async def get_project(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> ProjectResponse:
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)

    def _get() -> ProjectResponse:
        branches = {b.name: b for b in sc.list_branches(repo_id=repo_id)}
        if branch not in branches:
            raise RepoNotFoundError(f"slides project {slug}")
        title = slug.replace("-", " ").title()
        template_id = _DEFAULT_TEMPLATE
        updated_at = None
        try:
            meta = sc.get_file(repo_id=repo_id, path=_project_path(slug), ref=branch)
            if meta.text:
                data = json.loads(meta.text)
                title = str(data.get("title") or title)
                template_id = str(data.get("template_id") or template_id)
                updated_at = data.get("updated_at")
        except (SourceControlError, json.JSONDecodeError):
            pass
        return _project_from_meta(
            slug=slug,
            title=title,
            template_id=template_id,
            commit_sha=branches[branch].commit_sha,
            updated_at=updated_at,
        )

    try:
        return await run_in_threadpool(_get)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/projects/{slug}/deck", response_model=DeckResponse)
async def get_deck(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> DeckResponse:
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)

    def _get() -> DeckResponse:
        file = sc.get_file(repo_id=repo_id, path=_deck_path(slug), ref=branch)
        if file.is_binary or file.text is None:
            raise ValidationError("Deck is not UTF-8 text")
        return DeckResponse(
            slug=slug,
            path=_deck_path(slug),
            html=file.text,
            commit_sha=None,
        )

    try:
        return await run_in_threadpool(_get)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put("/projects/{slug}/deck", response_model=DeckResponse)
async def put_deck(
    slug: str,
    body: DeckUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> DeckResponse:
    await require_workspace_access(current_user.id, body.workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)
    username = _forge_username(current_user.name or "", str(current_user.email))
    author_name = current_user.name or username
    author_email = str(current_user.email)

    def _put() -> DeckResponse:
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        sc.add_collaborator(repo_id=repo_id, username=username, permission="write")
        commit = sc.upsert_file(
            repo_id=repo_id,
            path=_deck_path(slug),
            content=body.html,
            message=body.message or "Update slides deck",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        # Touch project.json updated_at when present.
        try:
            meta_file = sc.get_file(repo_id=repo_id, path=_project_path(slug), ref=branch)
            if meta_file.text:
                data = json.loads(meta_file.text)
                from datetime import datetime, timezone

                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                sc.upsert_file(
                    repo_id=repo_id,
                    path=_project_path(slug),
                    content=json.dumps(data, indent=2) + "\n",
                    message=f"Touch project metadata for {slug}",
                    branch=branch,
                    author_name=author_name,
                    author_email=author_email,
                )
        except (SourceControlError, json.JSONDecodeError):
            pass
        return DeckResponse(
            slug=slug,
            path=_deck_path(slug),
            html=body.html,
            commit_sha=commit.sha or None,
        )

    try:
        return await run_in_threadpool(_put)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/projects/{slug}/history", response_model=list[CommitResponse])
async def list_history(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    limit: int = 20,
) -> list[CommitResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)

    def _hist() -> list[CommitResponse]:
        commits = sc.list_commits(repo_id=repo_id, ref=branch, limit=max(1, min(limit, 50)))
        return [
            CommitResponse(
                sha=c.sha, message=c.message, author=c.author, date=c.date
            )
            for c in commits
        ]

    try:
        return await run_in_threadpool(_hist)
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _build_sidecar_base(*, coder_username: str | None, name: str) -> str | None:
    if not coder_username:
        return None
    return f"http://coder-{coder_username}-{name.lower()}:{_SIDECAR_PORT}"


async def lookup_slides_sidecar(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    slug: str,
) -> tuple[str | None, str | None]:
    """Return (sidecar_base, sidecar_secret) for an open Slides deck, if bound."""
    if not workspace_id or not user_id or not slug or not _SLUG_RE.match(slug):
        return None, None
    result = await db.execute(
        select(CodingEnvironmentModel).where(
            CodingEnvironmentModel.workspace_id == workspace_id,
            CodingEnvironmentModel.user_id == user_id,
            CodingEnvironmentModel.label == _runtime_label(slug),
        )
    )
    row = result.scalars().first()
    if row is None or not row.sidecar_base or not row.sidecar_secret:
        return None, None
    return str(row.sidecar_base), str(row.sidecar_secret)


async def _ensure_runtime_impl(
    *,
    request: Request,
    workspace_id: str,
    slug: str,
    current_user: User,
    db: AsyncSession | None,
) -> RuntimeResponse:
    label = _runtime_label(slug)
    coding = _get_coding_environment(request)
    if coding is None:
        return RuntimeResponse(
            ensured=False,
            detail="Coding environment service unavailable (Coder down?)",
            label=label,
        )
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)
    name = _coder_workspace_name(slug)

    def _pick_template() -> tuple[str, str] | None:
        templates = coding.list_templates()
        by_name = {t.name: t for t in templates}
        for wanted in _SLIDES_TEMPLATE_NAMES:
            if wanted in by_name:
                return by_name[wanted].id, wanted
        return None

    picked = await run_in_threadpool(_pick_template)
    if not picked:
        return RuntimeResponse(
            ensured=False,
            detail="No Coder template available (push abi-slides)",
            label=label,
        )
    template_id, template_name = picked

    author_email = str(current_user.email)
    coder_username = _sanitize_coder_username(
        current_user.name or ""
    ) or _sanitize_coder_username(author_email.split("@", 1)[0])
    expected_base = _build_sidecar_base(coder_username=coder_username, name=name)

    # Reuse the dedicated env for this slides/<slug> when already bound.
    if db is not None:
        result = await db.execute(
            select(CodingEnvironmentModel).where(
                CodingEnvironmentModel.workspace_id == workspace_id,
                CodingEnvironmentModel.user_id == current_user.id,
                CodingEnvironmentModel.label == label,
            )
        )
        existing = result.scalars().first()
        if existing is not None:
            # Without the original sidecar secret we cannot talk to the running
            # sidecar; fall through to reprovision so Abi gets a fresh binding.
            if not existing.sidecar_secret:
                try:
                    await db.delete(existing)
                    await db.commit()
                except Exception:  # noqa: BLE001
                    await db.rollback()
                existing = None
        if existing is not None:
            try:
                status: WorkspaceStatus = await run_in_threadpool(
                    coding.get_status, workspace_id=existing.id
                )
                if status.phase in ("stopped", "stopping"):
                    status = await run_in_threadpool(
                        coding.start, workspace_id=existing.id
                    )
                if expected_base and not existing.sidecar_base:
                    existing.sidecar_base = expected_base
                    try:
                        await db.commit()
                    except Exception:  # noqa: BLE001
                        await db.rollback()
                sidecar_ready = bool(existing.sidecar_base and existing.sidecar_secret)
                return RuntimeResponse(
                    ensured=True,
                    phase=status.phase,
                    environment_id=status.id,
                    template_name=template_name,
                    detail=None if sidecar_ready else "Sidecar credentials incomplete",
                    sidecar_ready=sidecar_ready,
                    label=label,
                )
            except CodingEnvironmentError as exc:
                logger.warning(
                    "slides runtime reuse failed for %s (%s); reprovisioning",
                    slug,
                    exc,
                )

    username = _forge_username(current_user.name or "", author_email)

    def _prepare() -> tuple[str, str | None, dict[str, str]]:
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        sc.add_collaborator(repo_id=repo_id, username=username, permission="write")
        token = sc.mint_git_token(user_id=username)
        creds = f"{quote(username, safe='')}:{quote(token, safe='')}"
        repo_url = (
            f"{settings.coding_git_clone_scheme}://{creds}"
            f"@{settings.coding_git_clone_host}/{repo_id}.git"
        )
        ws_secret = secrets.token_hex(16)
        ws_base = expected_base
        claims: dict[str, str] = {"sub": current_user.id}
        if ws_base:
            claims["ws_base"] = ws_base
            claims["ws_secret"] = ws_secret
        agent_token, _ = create_access_token(
            data=claims,
            expires_delta=timedelta(days=settings.coding_agent_token_days),
        )
        params: dict[str, str] = {
            "repo_url": repo_url,
            "branch": branch,
            "git_author_name": current_user.name or "",
            "git_author_email": author_email,
            "sidecar_secret": ws_secret,
            "abi_token": agent_token,
            "abi_api_base": settings.coding_agent_api_base,
            "abi_agents": settings.coding_default_agent or "AbiAgent",
        }
        if settings.coding_workspace_docker_network:
            params["docker_network"] = settings.coding_workspace_docker_network
        return ws_secret, ws_base, params

    adopted = False
    try:
        ws_secret, ws_base, params = await run_in_threadpool(_prepare)
        user_id = await run_in_threadpool(
            coding.ensure_user,
            external_id=current_user.id,
            email=author_email,
            username=current_user.name,
        )
        # Prefer looking up an existing Coder workspace before create, so a
        # missing Nexus binding does not race into a name-conflict error.
        existing_envs = await run_in_threadpool(
            coding.list_environments, user_id=user_id
        )
        prior_ws = next((env for env in existing_envs if env.name == name), None)
        if prior_ws is not None:
            adopted = True
            if prior_ws.phase in ("stopped", "stopping"):
                status = await run_in_threadpool(
                    coding.start, workspace_id=prior_ws.id, params=params
                )
            else:
                status = await run_in_threadpool(
                    coding.get_status, workspace_id=prior_ws.id
                )
                # Prefer the secret already baked into the running sidecar.
                on_ws = await run_in_threadpool(
                    _adapter_get_parameters, coding, prior_ws.id
                )
                baked = (on_ws or {}).get("sidecar_secret") or ""
                if baked:
                    ws_secret = baked
                else:
                    # No sidecar secret on the build: stop+start once to inject.
                    try:
                        await run_in_threadpool(
                            coding.stop, workspace_id=prior_ws.id
                        )
                    except CodingEnvironmentError:
                        pass
                    status = await run_in_threadpool(
                        coding.start, workspace_id=prior_ws.id, params=params
                    )
        else:
            status = await run_in_threadpool(
                coding.provision,
                user_id=user_id,
                template_id=template_id,
                name=name,
                params=params,
            )
            # Service-level adopt (race / 400 unique): sync sidecar secret.
            on_ws = await run_in_threadpool(
                _adapter_get_parameters, coding, status.id
            )
            baked = (on_ws or {}).get("sidecar_secret") or ""
            if baked and baked != ws_secret:
                adopted = True
                ws_secret = baked
    except WorkspaceNameConflictError as exc:
        # Belt-and-suspenders if list missed the workspace.
        try:
            user_id = await run_in_threadpool(
                coding.ensure_user,
                external_id=current_user.id,
                email=author_email,
                username=current_user.name,
            )
            envs = await run_in_threadpool(coding.list_environments, user_id=user_id)
            match = next((env for env in envs if env.name == name), None)
            if match is None:
                return RuntimeResponse(
                    ensured=False,
                    detail=_friendly_coding_detail(exc),
                    template_name=template_name,
                    label=label,
                )
            adopted = True
            if match.phase in ("stopped", "stopping"):
                status = await run_in_threadpool(
                    coding.start, workspace_id=match.id, params=params
                )
            else:
                status = await run_in_threadpool(
                    coding.get_status, workspace_id=match.id
                )
                on_ws = await run_in_threadpool(
                    _adapter_get_parameters, coding, match.id
                )
                baked = (on_ws or {}).get("sidecar_secret") or ""
                if baked:
                    ws_secret = baked
        except CodingEnvironmentError as adopt_exc:
            return RuntimeResponse(
                ensured=False,
                detail=_friendly_coding_detail(adopt_exc),
                template_name=template_name,
                label=label,
            )
    except CodingEnvironmentError as exc:
        return RuntimeResponse(
            ensured=False,
            detail=_friendly_coding_detail(exc),
            template_name=template_name,
            label=label,
        )
    except SourceControlError as exc:
        return RuntimeResponse(
            ensured=False,
            detail=f"Git setup failed: {exc}",
            template_name=template_name,
            label=label,
        )

    sidecar_ready = bool(ws_base and ws_secret)
    if db is not None:
        try:
            # Upsert-style: replace any stale row for this label.
            prior = await db.execute(
                select(CodingEnvironmentModel).where(
                    CodingEnvironmentModel.workspace_id == workspace_id,
                    CodingEnvironmentModel.user_id == current_user.id,
                    CodingEnvironmentModel.label == label,
                )
            )
            old = prior.scalars().first()
            if old is not None and old.id != status.id:
                await db.delete(old)
            db.add(
                CodingEnvironmentModel(
                    id=status.id,
                    workspace_id=workspace_id,
                    user_id=current_user.id,
                    repo_id=repo_id,
                    label=label,
                    sidecar_base=ws_base,
                    sidecar_secret=ws_secret,
                )
            )
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
            logger.exception("Failed to persist slides runtime binding for %s", slug)

    detail: str | None
    if not sidecar_ready:
        detail = "Sidecar base URL could not be derived"
    elif adopted:
        detail = "Reconnecting to existing runtime…"
    else:
        detail = None

    return RuntimeResponse(
        ensured=True,
        phase=status.phase,
        environment_id=status.id,
        template_name=template_name,
        sidecar_ready=sidecar_ready,
        label=label,
        detail=detail,
    )


@router.post("/projects/{slug}/runtime", response_model=RuntimeResponse)
async def ensure_runtime(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> RuntimeResponse:
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    return await _ensure_runtime_impl(
        request=request,
        workspace_id=workspace_id,
        slug=slug,
        current_user=current_user,
        db=db,
    )


@router.get("/projects/{slug}/tree", response_model=ProjectTreeResponse)
async def get_project_tree(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> ProjectTreeResponse:
    """List the presentation folder (deck.html, assets/, …) for the sidebar tree."""
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc = _get_source_control(request)
    repo_id = _repo_id()
    branch = _branch_for(slug)
    root = f"slides/{slug}"

    def _tree() -> ProjectTreeResponse:
        branches = {b.name for b in sc.list_branches(repo_id=repo_id)}
        if branch not in branches:
            raise RepoNotFoundError(f"slides project {slug}")
        try:
            entries_raw = sc.list_contents(repo_id=repo_id, path=root, ref=branch)
        except SourceControlError:
            entries_raw = []
        entries = [
            TreeEntryResponse(
                name=e.name, path=e.path, type=e.type, size=getattr(e, "size", 0) or 0
            )
            for e in entries_raw
        ]
        # Ensure classic shape even if forge listing lags after create.
        names = {e.name for e in entries}
        if "deck.html" not in names:
            entries.append(
                TreeEntryResponse(
                    name="deck.html", path=_deck_path(slug), type="file"
                )
            )
        if "assets" not in names:
            entries.append(
                TreeEntryResponse(name="assets", path=_assets_dir(slug), type="dir")
            )
        entries.sort(key=lambda e: (0 if e.type == "dir" else 1, e.name))

        assets: list[TreeEntryResponse] = []
        try:
            assets_raw = sc.list_contents(
                repo_id=repo_id, path=_assets_dir(slug), ref=branch
            )
            assets = [
                TreeEntryResponse(
                    name=e.name,
                    path=e.path,
                    type=e.type,
                    size=getattr(e, "size", 0) or 0,
                )
                for e in assets_raw
                if e.name not in {".gitkeep", "README.md"}
            ]
            assets.sort(key=lambda e: e.name)
        except SourceControlError:
            pass

        embedded = 0
        assets_note = None
        try:
            meta_file = sc.get_file(
                repo_id=repo_id, path=_project_path(slug), ref=branch
            )
            if meta_file.text:
                data = json.loads(meta_file.text)
                embedded = int(data.get("embedded_images") or 0)
                assets_note = data.get("assets_note")
        except (SourceControlError, json.JSONDecodeError, TypeError, ValueError):
            pass
        if not embedded:
            try:
                deck = sc.get_file(repo_id=repo_id, path=_deck_path(slug), ref=branch)
                if deck.text:
                    embedded = _count_embedded_images(deck.text)
            except SourceControlError:
                pass

        return ProjectTreeResponse(
            slug=slug,
            root=root,
            entries=entries,
            assets=assets,
            embedded_images=embedded,
            assets_note=assets_note
            or (
                "assets/ seeded empty; template images remain as data-URLs in deck.html"
                if embedded
                else None
            ),
        )

    try:
        return await run_in_threadpool(_tree)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/templates")
async def list_seed_templates(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> list[dict[str, str]]:
    await require_workspace_access(current_user.id, workspace_id)
    return [
        {
            "id": _DEFAULT_TEMPLATE,
            "name": "BOB / Forvis Mazars",
            "description": "Canonical cold-start deck with buildPptx() export",
        }
    ]
