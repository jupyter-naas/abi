"""Slides FastAPI primary adapter.

Business-facing slide decks stored in Forgejo under a workspace namespace
(branch ``slides/<workspace_id>/<slug>``, path
``slides/<workspace_id>/<slug>/deck.html``). Legacy ``slides/<slug>`` decks
remain available only when ``project.json.workspace_id`` matches (unscoped
legacy decks require a verified workspace_id owner). A Coder ``abi-slides`` workspace is
provisioned under the hood for agent sidecar access; the Nexus UI never embeds
Coder.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import re
import secrets
import time
from datetime import timedelta
from importlib import resources
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

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
_DEFAULT_TEMPLATE = "minimal-light-v1"
_SIDECAR_PORT = 8378
_SLIDES_TEMPLATE_NAMES = ("abi-slides", "abi-code-server")
# Cold start: agent connect + startup_script before :8378 listens. Ensure must
# wait; a single probe races "running" phase and falsely marks degraded.
_SIDECAR_WAIT_ATTEMPTS = 2
_SIDECAR_WAIT_INTERVAL_S = 0.5


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
            detail="Forgejo is not configured. Slides needs git storage.",
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


_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_FORGEJO_NOT_CONFIGURED = "Forgejo is not configured. Slides needs git storage."
_FORGEJO_UNREACHABLE = "Forgejo is not reachable. Slides needs git storage."


def _is_repo_id_message(text: str) -> bool:
    """True when the exception is just owner/name (InMemory RepoNotFoundError)."""
    return bool(_REPO_ID_RE.fullmatch((text or "").strip()))


def _repo_missing_detail(repo_id: str) -> str:
    return (
        f"Git repo '{repo_id}' is missing. Forgejo is not configured, "
        "or coding-init did not seed it."
    )


def _is_forgejo_unreachable(exc: BaseException | str) -> bool:
    text = str(exc or "").lower()
    return any(
        marker in text
        for marker in (
            "connection refused",
            "failed to establish",
            "name or service not known",
            "nodename nor servname",
            "timed out",
            "timeout",
            "connection reset",
            "max retries",
            "temporarily unavailable",
            "network is unreachable",
            "connectionerror",
            "connecterror",
        )
    )


def _source_control_http_error(exc: BaseException) -> HTTPException:
    """Map forge failures: missing/down git is 503; transient writes stay 502."""
    text = str(exc or "").strip()
    repo_hint = text.split(":", 1)[0].strip() if text else ""
    if isinstance(exc, RepoNotFoundError) and _is_repo_id_message(repo_hint):
        return HTTPException(status_code=503, detail=_repo_missing_detail(repo_hint))
    if _is_repo_id_message(text):
        return HTTPException(status_code=503, detail=_repo_missing_detail(text))
    if _is_forgejo_unreachable(exc):
        return HTTPException(status_code=503, detail=_FORGEJO_UNREACHABLE)
    return HTTPException(status_code=502, detail=_friendly_git_detail(exc))


def _ensure_coding_repo(sc: SourceControlService) -> str:
    """Idempotently seed CODING_REPO_ID (local in_memory starts empty)."""
    repo_id = _repo_id()
    owner, sep, name = repo_id.partition("/")
    if not sep or not owner or not name or "/" in name:
        raise HTTPException(status_code=503, detail=_FORGEJO_NOT_CONFIGURED)
    try:
        sc.ensure_repo(owner=owner, name=name)
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc
    except (OSError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=_FORGEJO_UNREACHABLE) from exc
    return repo_id


def _slides_sc(request: Request) -> tuple[SourceControlService, str]:
    sc = _get_source_control(request)
    return sc, _ensure_coding_repo(sc)


def _forge_username(name: str, email: str) -> str:
    def slug(raw: str) -> str:
        return re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower()).strip("-._")[:39].strip(
            "-._"
        )

    return slug(name) or slug(email.split("@", 1)[0]) or "abi-user"


def _workspace_segment(workspace_id: str) -> str:
    seg = re.sub(r"[^a-zA-Z0-9._-]+", "-", (workspace_id or "").strip()).strip("-._")
    if not seg:
        raise HTTPException(status_code=422, detail="Invalid workspace_id")
    return seg


def _branch_for(workspace_id: str, slug: str) -> str:
    return f"{_BRANCH_PREFIX}{_workspace_segment(workspace_id)}/{slug}"


def _legacy_branch_for(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


def _deck_path(workspace_id: str, slug: str) -> str:
    return f"slides/{_workspace_segment(workspace_id)}/{slug}/deck.html"


def _legacy_deck_path(slug: str) -> str:
    return f"slides/{slug}/deck.html"


def _project_path(workspace_id: str, slug: str) -> str:
    return f"slides/{_workspace_segment(workspace_id)}/{slug}/project.json"


def _legacy_project_path(slug: str) -> str:
    return f"slides/{slug}/project.json"


def _assets_dir(workspace_id: str, slug: str) -> str:
    return f"slides/{_workspace_segment(workspace_id)}/{slug}/assets"


def _legacy_assets_dir(slug: str) -> str:
    return f"slides/{slug}/assets"


def _assets_gitkeep_path(workspace_id: str, slug: str) -> str:
    return f"{_assets_dir(workspace_id, slug)}/.gitkeep"


def _assets_readme_path(workspace_id: str, slug: str) -> str:
    return f"{_assets_dir(workspace_id, slug)}/README.md"


def _paths_for(workspace_id: str, slug: str, *, legacy: bool = False) -> dict[str, str]:
    if legacy:
        assets = _legacy_assets_dir(slug)
        return {
            "branch": _legacy_branch_for(slug),
            "deck_path": _legacy_deck_path(slug),
            "project_path": _legacy_project_path(slug),
            "assets_dir": assets,
            "assets_gitkeep": f"{assets}/.gitkeep",
            "assets_readme": f"{assets}/README.md",
        }
    return {
        "branch": _branch_for(workspace_id, slug),
        "deck_path": _deck_path(workspace_id, slug),
        "project_path": _project_path(workspace_id, slug),
        "assets_dir": _assets_dir(workspace_id, slug),
        "assets_gitkeep": _assets_gitkeep_path(workspace_id, slug),
        "assets_readme": _assets_readme_path(workspace_id, slug),
    }


def _parse_meta(text: str | None) -> dict:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _meta_workspace_id(meta: dict) -> str | None:
    raw = meta.get("workspace_id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _load_project_meta(
    sc: SourceControlService, *, repo_id: str, path: str, ref: str
) -> dict | None:
    """Return parsed project.json, or None when the ownership record is unreadable.

    Distinguishes a successful read of missing/empty metadata (``{}``) from a
    Forgejo/transport failure (``None``). Callers must deny on ``None``.
    """
    try:
        meta = sc.get_file(repo_id=repo_id, path=path, ref=ref)
        return _parse_meta(meta.text)
    except SourceControlError:
        return None


def _resolve_project_paths(
    sc: SourceControlService,
    *,
    repo_id: str,
    workspace_id: str,
    slug: str,
    branch_names: set[str] | None = None,
) -> dict[str, str] | None:
    """Namespaced or legacy paths when the deck belongs to workspace_id."""
    names = branch_names if branch_names is not None else {
        b.name for b in sc.list_branches(repo_id=repo_id)
    }
    ns = _paths_for(workspace_id, slug, legacy=False)
    if ns["branch"] in names:
        meta = _load_project_meta(
            sc, repo_id=repo_id, path=ns["project_path"], ref=ns["branch"]
        )
        if meta is None:
            return None
        owner = _meta_workspace_id(meta)
        if owner is not None and owner != workspace_id:
            return None
        return {**ns, "legacy": "0"}
    legacy = _paths_for(workspace_id, slug, legacy=True)
    if legacy["branch"] in names:
        meta = _load_project_meta(
            sc, repo_id=repo_id, path=legacy["project_path"], ref=legacy["branch"]
        )
        # Fail closed: legacy decks require a verified matching owner.
        if meta is None:
            return None
        owner = _meta_workspace_id(meta)
        if owner != workspace_id:
            return None
        return {**legacy, "legacy": "1"}
    return None


def _claim_workspace_in_meta(
    sc: SourceControlService,
    *,
    repo_id: str,
    paths: dict[str, str],
    workspace_id: str,
    slug: str,
    author_name: str,
    author_email: str,
) -> None:
    """Persist workspace_id on legacy/unscoped project.json when missing."""
    meta = _load_project_meta(
        sc, repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
    )
    if meta is None or _meta_workspace_id(meta) is not None:
        return
    meta = {
        **meta,
        "slug": meta.get("slug") or slug,
        "workspace_id": workspace_id,
    }
    sc.upsert_file(
        repo_id=repo_id,
        path=paths["project_path"],
        content=json.dumps(meta, indent=2) + "\n",
        message=f"Claim slides project {slug} for workspace",
        branch=paths["branch"],
        author_name=author_name,
        author_email=author_email,
    )


_ASSETS_README = """# Presentation assets

Drop images and other media for this deck here.

## Seed note

The default template ships decorative bands as neutral ``data:`` URLs inside
``deck.html``. Binary extraction into this folder is deferred: Forgejo
``upsert_file`` is text-only today, and rewriting the deck to relative
``assets/`` paths would break the in-browser Preview until an asset-serving
route exists.

Manual files you add here appear in the Slides sidebar tree.
"""


def _count_embedded_images(html: str) -> int:
    return len(re.findall(r"data:image/[^;]+;base64,", html))


_SECTION_SLIDE_RE = re.compile(
    r"<section\b([^>]*)>(.*?)</section>",
    re.IGNORECASE | re.DOTALL,
)
_SLIDE_CLASS_RE = re.compile(r"""\bclass\s*=\s*["'][^"']*\bslide\b""", re.IGNORECASE)
_SECTION_ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_EYEBROW_RE = re.compile(
    r"""<div\b[^>]*class=["'][^"']*\b(?:eyebrow|divider-eyebrow)\b[^"']*["'][^>]*>(.*?)</div>""",
    re.IGNORECASE | re.DOTALL,
)
_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_DIVIDER_TITLE_RE = re.compile(
    r"""<div\b[^>]*class=["'][^"']*\bdivider-title\b[^"']*["'][^>]*>(.*?)</div>""",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_IMG_CONST_RE = re.compile(r"const IMG\s*=\s*\{(.*?)\n\s*\};", re.DOTALL)
_IMG_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", re.MULTILINE)


def _strip_html_text(raw: str) -> str:
    return html_lib.unescape(_TAG_RE.sub("", raw or "")).strip()


def _parse_slide_outline(html: str) -> list[dict]:
    """h1 / eyebrow (or divider title) per ``<section class="slide">``."""
    slides: list[dict] = []
    index = 0
    for match in _SECTION_SLIDE_RE.finditer(html or ""):
        attrs = match.group(1) or ""
        if not _SLIDE_CLASS_RE.search(attrs):
            continue
        body = match.group(2) or ""
        id_m = _SECTION_ID_RE.search(attrs)
        eyebrow_m = _EYEBROW_RE.search(body)
        h1_m = _H1_RE.search(body)
        divider_m = _DIVIDER_TITLE_RE.search(body)
        title = (
            _strip_html_text(h1_m.group(1))
            if h1_m
            else (_strip_html_text(divider_m.group(1)) if divider_m else "")
        )
        slides.append(
            {
                "index": index,
                "id": id_m.group(1) if id_m else None,
                "eyebrow": _strip_html_text(eyebrow_m.group(1)) if eyebrow_m else "",
                "title": title,
            }
        )
        index += 1
    return slides


def _parse_template_assets(html: str) -> list[dict[str, str]]:
    """Embedded seed assets (``const IMG`` keys, else numbered data-URLs)."""
    block = _IMG_CONST_RE.search(html or "")
    if block:
        keys = _IMG_KEY_RE.findall(block.group(1))
        return [{"name": key, "kind": "embedded"} for key in keys]
    count = _count_embedded_images(html or "")
    return [{"name": f"embedded-{i + 1}", "kind": "embedded"} for i in range(count)]


def _slugify(title: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return raw[:48] or "deck"


def _template_dirs() -> list[Path]:
    """Ordered filesystem candidate dirs for seed HTML + catalog.json."""
    here = Path(__file__).resolve()
    dirs = [
        here.parents[7] / "assets" / "slides" / "templates",
        Path("/app/assets/slides/templates"),
        Path("assets/slides/templates"),
    ]
    try:
        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        # Prefer real filesystem path when the package is editable / on disk.
        as_path = Path(str(root))
        if as_path.is_dir():
            dirs.insert(0, as_path)
    except Exception:
        pass
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key in seen:
            continue
        seen.add(key)
        try:
            if d.is_dir():
                out.append(d)
        except OSError:
            continue
    return out


def _read_bytes_from_templates_pkg(name: str) -> str | None:
    try:
        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        text = (root / name).read_text(encoding="utf-8")
        return text if text.strip() else None
    except Exception:
        return None


def _read_template_catalog() -> list[dict]:
    """Load catalog.json metadata when present (first hit wins)."""
    raw = _read_bytes_from_templates_pkg("catalog.json")
    if raw is None:
        for d in _template_dirs():
            path = d / "catalog.json"
            try:
                if path.is_file():
                    raw = path.read_text(encoding="utf-8")
                    break
            except OSError:
                continue
    if not raw:
        return []
    try:
        data = json.loads(raw)
        items = data.get("templates") if isinstance(data, dict) else None
        if isinstance(items, list):
            return [t for t in items if isinstance(t, dict) and t.get("id")]
    except (json.JSONDecodeError, TypeError):
        return []
    return []


def _discover_seed_ids() -> list[str]:
    """HTML filenames (stem) from packaged assets or filesystem fallbacks."""
    found: list[str] = []
    try:
        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        names = sorted(
            p.name[:-5]
            for p in root.iterdir()
            if getattr(p, "name", "").endswith(".html") and _SLUG_RE.match(p.name[:-5])
        )
        if names:
            found = names
    except Exception:
        pass
    if not found:
        for d in _template_dirs():
            try:
                names = sorted(
                    p.stem
                    for p in d.glob("*.html")
                    if p.is_file() and _SLUG_RE.match(p.stem)
                )
            except OSError:
                continue
            if names:
                found = names
                break
    if _DEFAULT_TEMPLATE not in found:
        found.insert(0, _DEFAULT_TEMPLATE)
    # Stable order: default first, then catalog order, then remaining alpha.
    catalog_ids = [str(t["id"]) for t in _read_template_catalog()]
    ordered: list[str] = []
    for tid in [_DEFAULT_TEMPLATE, *catalog_ids, *sorted(found)]:
        if tid in found and tid not in ordered:
            ordered.append(tid)
    return ordered


def _seed_template_meta(template_id: str) -> dict[str, str]:
    """Human metadata for a seed id (catalog override or generated)."""
    for item in _read_template_catalog():
        if str(item.get("id")) == template_id:
            preview = item.get("preview") if isinstance(item.get("preview"), dict) else {}
            return {
                "id": template_id,
                "name": str(item.get("name") or template_id),
                "description": str(item.get("description") or ""),
                "preview_bg": str(preview.get("bg") or "#f4f4f4"),
                "preview_panel": str(preview.get("panel") or "#ffffff"),
                "preview_accent": str(preview.get("accent") or "#0072ce"),
                "preview_ink": str(preview.get("ink") or "#2d2d2d"),
            }
    title = template_id.replace("-", " ").replace(" v1", "").title()
    return {
        "id": template_id,
        "name": title,
        "description": f"Deck seed ({template_id})",
        "preview_bg": "#f4f4f4",
        "preview_panel": "#ffffff",
        "preview_accent": "#0072ce",
        "preview_ink": "#2d2d2d",
    }


def _list_seed_template_records() -> list[dict]:
    rows: list[dict] = []
    for tid in _discover_seed_ids():
        meta = _seed_template_meta(tid)
        try:
            seed = _load_seed_html(tid)
        except HTTPException:
            seed = ""
        meta["slides"] = _parse_slide_outline(seed) if seed else []
        meta["assets"] = _parse_template_assets(seed) if seed else []
        rows.append(meta)
    return rows


def _known_template_ids() -> set[str]:
    return set(_discover_seed_ids())


def _load_seed_html(template_id: str = _DEFAULT_TEMPLATE) -> str:
    if not _SLUG_RE.match(template_id):
        raise HTTPException(
            status_code=422,
            detail="template_id must be lowercase kebab-case (a-z, 0-9, hyphens).",
        )
    name = f"{template_id}.html"
    # Preferred: packaged Nexus assets (importlib.resources).
    try:
        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        text = (root / name).read_text(encoding="utf-8")
        if text.strip():
            return text
    except Exception:
        pass

    for directory in _template_dirs():
        path = directory / name
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8")
        except OSError:
            continue
    raise HTTPException(
        status_code=404,
        detail=f"Unknown slides template '{template_id}'.",
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
    # Live editing SoT when runtime is ready: "sidecar". Forgejo is fallback /
    # Save versioning snapshot when sidecar is down: "forgejo".
    source: str | None = None


class DeckUpdateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    html: str = Field(..., min_length=1)
    message: str = Field(default="Update slides deck", max_length=200)
    template_id: str | None = Field(default=None, max_length=64)


class ApplyTemplateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    template_id: str = Field(..., min_length=1, max_length=64)


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
    coder_workspace: str | None = None
    branch: str | None = None
    # Coder dashboard URL (https://coder…/@owner/slides-<slug>) when bound.
    coder_ui_url: str | None = None


def _runtime_label(workspace_id: str, slug: str) -> str:
    return f"slides/{_workspace_segment(workspace_id)}/{slug}"


def _legacy_runtime_label(slug: str) -> str:
    return f"slides/{slug}"


def _runtime_labels(workspace_id: str, slug: str) -> list[str]:
    return [_runtime_label(workspace_id, slug), _legacy_runtime_label(slug)]


def _coder_workspace_name(workspace_id: str, slug: str) -> str:
    digest = hashlib.sha1(workspace_id.encode("utf-8")).hexdigest()[:6]
    return f"s-{digest}-{slug}"[:32].rstrip("-")


def _legacy_coder_workspace_name(slug: str) -> str:
    return f"slides-{slug}"[:32].rstrip("-")


def _coder_workspace_names(workspace_id: str, slug: str) -> list[str]:
    return [
        _coder_workspace_name(workspace_id, slug),
        _legacy_coder_workspace_name(slug),
    ]


def _coder_ui_url(
    coding: CodingEnvironmentService | None,
    *,
    environment_id: str | None = None,
    owner: str | None = None,
    name: str | None = None,
) -> str | None:
    """Prefer live Coder owner/name; fall back to access_url + owner/name."""
    if coding is None:
        return None
    if environment_id:
        url = coding.get_workspace_ui_url(workspace_id=environment_id)
        if url:
            return url
    if not name:
        return None
    adapter = getattr(coding, "_adapter", None)
    access = getattr(adapter, "_access_url", None)
    build = getattr(adapter, "build_workspace_ui_url", None)
    if not access or not callable(build):
        return None
    try:
        return build(access_url=access, owner=owner or "me", name=name)
    except Exception:  # noqa: BLE001
        return None


def _probe_sidecar(base: str | None, secret: str | None, *, timeout_s: float = 2.0) -> bool:
    """Return True when the Coder sidecar /health responds OK on the docker network."""
    if not base or not secret:
        return False
    url = f"{base.rstrip('/')}/health"
    try:
        req = UrlRequest(url, method="GET")
        req.add_header("Authorization", f"Bearer {secret}")
        with urlopen(req, timeout=timeout_s) as resp:  # nosec B310 - internal docker DNS only
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def _wait_for_sidecar(
    base: str | None,
    secret: str | None,
    *,
    attempts: int = _SIDECAR_WAIT_ATTEMPTS,
    interval_s: float = _SIDECAR_WAIT_INTERVAL_S,
) -> bool:
    """Poll sidecar /health until ready or attempts exhausted.

    Coder can report phase=running while the agent startup script (and sidecar)
    are still coming up. Callers must not treat a single failed probe as final.
    """
    if not base or not secret:
        return False
    tries = max(1, int(attempts))
    delay = max(0.0, float(interval_s))
    for i in range(tries):
        if _probe_sidecar(base, secret):
            return True
        if i < tries - 1 and delay:
            time.sleep(delay)
    return False


def _sidecar_start_params(sidecar_secret: str | None) -> dict[str, str] | None:
    """Params to reinject on Coder start (secret + docker network for DNS)."""
    params: dict[str, str] = {}
    if sidecar_secret:
        params["sidecar_secret"] = sidecar_secret
    if settings.coding_workspace_docker_network:
        params["docker_network"] = settings.coding_workspace_docker_network
    return params or None


def _sidecar_tool_call(
    base: str | None,
    secret: str | None,
    tool_name: str,
    payload: dict,
    *,
    timeout_s: float = 15.0,
) -> dict:
    """Call a Coder workspace sidecar tool over the docker network."""
    if not base or not secret:
        return {"error": "sidecar not bound"}
    if not base.startswith(("http://", "https://")):
        return {"error": f"invalid sidecar base url: {base}"}
    url = f"{base.rstrip('/')}/tools/{tool_name}"
    try:
        body = json.dumps(payload).encode("utf-8")
        req = UrlRequest(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {secret}",
            },
        )
        with urlopen(req, timeout=timeout_s) as resp:  # nosec B310 - internal docker DNS only
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"sidecar {tool_name} failed: {exc}"}


def _read_deck_via_sidecar(
    base: str | None, secret: str | None, *, deck_path: str
) -> str | None:
    """Return deck HTML from the Coder sidecar, or None when unavailable."""
    if not _probe_sidecar(base, secret):
        return None
    result = _sidecar_tool_call(
        base, secret, "read_file", {"path": deck_path}, timeout_s=10.0
    )
    if result.get("error") or result.get("binary"):
        return None
    content = result.get("content")
    return content if isinstance(content, str) else None


def _write_deck_via_sidecar(
    base: str | None, secret: str | None, *, deck_path: str, html: str
) -> bool:
    """Best-effort write of deck HTML into the Coder workspace via sidecar."""
    if not base or not secret:
        return False
    if not _probe_sidecar(base, secret):
        return False
    result = _sidecar_tool_call(
        base,
        secret,
        "write_file",
        {"path": deck_path, "content": html},
        timeout_s=20.0,
    )
    return bool(result.get("ok")) and not result.get("error")


def _is_git_write_race(exc: BaseException | str) -> bool:
    text = str(exc or "").lower()
    return any(
        marker in text
        for marker in (
            "pushrejected",
            "cannot lock ref",
            "but expected",
            "sha does not match",
        )
    )


def _friendly_git_detail(exc: BaseException) -> str:
    """Human detail for Forgejo failures; never dump raw forge JSON."""
    if _is_git_write_race(exc):
        return "Git write raced on the deck branch; retrying is safe"
    if _is_forgejo_unreachable(exc):
        return _FORGEJO_UNREACHABLE
    text = str(exc or "").strip()
    repo_hint = text.split(":", 1)[0].strip() if text else ""
    if _is_repo_id_message(text) or (
        isinstance(exc, RepoNotFoundError) and _is_repo_id_message(repo_hint)
    ):
        return _repo_missing_detail(repo_hint or _repo_id())
    if (
        len(text) > 180
        or text.startswith("{")
        or "forgejo api request failed" in text.lower()
    ):
        return "Git setup temporarily unavailable"
    return text or "Git setup temporarily unavailable"


def _friendly_coding_detail(exc: BaseException) -> str:
    """Human detail for UX; never dump raw Coder JSON as the primary message."""
    if _is_git_write_race(exc):
        return _friendly_git_detail(exc)
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
    workspace_id: str,
    slug: str,
    title: str | None = None,
    template_id: str = _DEFAULT_TEMPLATE,
    commit_sha: str | None = None,
    updated_at: str | None = None,
    legacy: bool = False,
) -> ProjectResponse:
    paths = _paths_for(workspace_id, slug, legacy=legacy)
    return ProjectResponse(
        slug=slug,
        title=title or slug.replace("-", " ").title(),
        branch=paths["branch"],
        deck_path=paths["deck_path"],
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
    sc, repo_id = _slides_sc(request)
    ws_seg = _workspace_segment(workspace_id)
    ns_prefix = f"{_BRANCH_PREFIX}{ws_seg}/"

    def _list() -> list[ProjectResponse]:
        branches = sc.list_branches(repo_id=repo_id)
        out: list[ProjectResponse] = []
        for branch in branches:
            name = branch.name
            legacy = False
            slug = ""
            if name.startswith(ns_prefix):
                slug = name[len(ns_prefix) :]
            elif name.startswith(_BRANCH_PREFIX) and "/" not in name[len(_BRANCH_PREFIX) :]:
                slug = name[len(_BRANCH_PREFIX) :]
                legacy = True
            else:
                continue
            if not slug or not _SLUG_RE.match(slug):
                continue
            paths = _paths_for(workspace_id, slug, legacy=legacy)
            meta = _load_project_meta(
                sc, repo_id=repo_id, path=paths["project_path"], ref=branch.name
            )
            if meta is None:
                continue
            owner = _meta_workspace_id(meta)
            if owner is not None and owner != workspace_id:
                continue
            if legacy and owner != workspace_id:
                # Unowned/unscoped legacy decks are not listed or claimable here.
                continue
            title = str(meta.get("title") or slug.replace("-", " ").title())
            template_id = str(meta.get("template_id") or _DEFAULT_TEMPLATE)
            out.append(
                _project_from_meta(
                    workspace_id=workspace_id,
                    slug=slug,
                    title=title,
                    template_id=template_id,
                    commit_sha=branch.commit_sha,
                    updated_at=meta.get("updated_at"),
                    legacy=legacy,
                )
            )
        out.sort(key=lambda p: (p.updated_at or "", p.slug), reverse=True)
        return out

    try:
        return await run_in_threadpool(_list)
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


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
    if body.template_id not in _known_template_ids():
        raise HTTPException(
            status_code=422,
            detail=f"Unknown template_id '{body.template_id}'.",
        )
    sc, repo_id = _slides_sc(request)
    paths = _paths_for(body.workspace_id, slug, legacy=False)
    branch = paths["branch"]
    username = _forge_username(current_user.name or "", str(current_user.email))
    seed = _load_seed_html(body.template_id)
    author_name = current_user.name or username
    author_email = str(current_user.email)

    def _create() -> ProjectResponse:
        # Authorship only: Nexus writes via the service token. Do not grant the
        # Forgejo user repo-wide write as a stand-in for per-deck authorization.
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        existing = {b.name for b in sc.list_branches(repo_id=repo_id)}
        # Only the namespaced branch reserves this slug for this workspace.
        # Legacy slides/<slug> is ownership-gated separately and must not block
        # other tenants from creating slides/<workspace_id>/<slug>.
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
        adopted_branch = branch in existing
        if not adopted_branch:
            try:
                sc.create_branch(repo_id=repo_id, name=branch, from_ref=default)
            except BranchNameConflictError:
                # Concurrent create won the branch; adopt and finish seeding.
                adopted_branch = True
                current = {b.name for b in sc.list_branches(repo_id=repo_id)}
                if branch not in current:
                    raise
        embedded = _count_embedded_images(seed)
        meta = {
            "slug": slug,
            "workspace_id": body.workspace_id,
            "title": body.title,
            "template_id": body.template_id,
            "updated_at": None,
            "embedded_images": embedded,
            "assets_note": (
                "assets/ seeded empty; template images remain as data-URLs in deck.html"
            ),
        }
        # Concurrent/prior create already finished: keep 409. If seed is
        # incomplete (branch exists, deck.html missing), finish seeding.
        if adopted_branch:
            try:
                existing_deck = sc.get_file(
                    repo_id=repo_id, path=paths["deck_path"], ref=branch
                )
                if existing_deck.text:
                    raise BranchNameConflictError(
                        f"Slides project '{slug}' already exists"
                    )
            except RepoNotFoundError:
                pass
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(meta, indent=2) + "\n",
            message=f"Create slides project {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        commit = sc.upsert_file(
            repo_id=repo_id,
            path=paths["deck_path"],
            content=seed,
            message=f"Seed deck from {body.template_id}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["assets_gitkeep"],
            content="",
            message=f"Seed assets folder for {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["assets_readme"],
            content=_ASSETS_README,
            message=f"Document assets folder for {slug}",
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )
        return _project_from_meta(
            workspace_id=body.workspace_id,
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
        raise _source_control_http_error(exc) from exc

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
    sc, repo_id = _slides_sc(request)

    def _get() -> ProjectResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        branches = {b.name: b for b in sc.list_branches(repo_id=repo_id)}
        meta = _load_project_meta(
            sc, repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if meta is None:
            raise RepoNotFoundError(f"slides project {slug}")
        return _project_from_meta(
            workspace_id=workspace_id,
            slug=slug,
            title=str(meta.get("title") or slug.replace("-", " ").title()),
            template_id=str(meta.get("template_id") or _DEFAULT_TEMPLATE),
            commit_sha=branches[paths["branch"]].commit_sha,
            updated_at=meta.get("updated_at"),
            legacy=paths.get("legacy") == "1",
        )

    try:
        return await run_in_threadpool(_get)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.get("/projects/{slug}/deck", response_model=DeckResponse)
async def get_deck(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> DeckResponse:
    """Load deck HTML for Preview/Code.

    Prefer the Coder sidecar (live editing SoT) when the slides runtime is
    bound and healthy. Fall back to Forgejo (version snapshot) otherwise.
    """
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)

    def _resolve() -> dict[str, str]:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        # Do not claim here: get_project already claims on open, and parallel
        # claim+claim was racing Forgejo Contents API (PushRejected / ref lock).
        return paths

    try:
        paths = await run_in_threadpool(_resolve)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc

    sidecar_base, sidecar_secret = await lookup_slides_sidecar(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        slug=slug,
    )

    def _get_sidecar() -> str | None:
        return _read_deck_via_sidecar(
            sidecar_base, sidecar_secret, deck_path=paths["deck_path"]
        )

    try:
        sidecar_html = await run_in_threadpool(_get_sidecar)
        if isinstance(sidecar_html, str) and sidecar_html:
            return DeckResponse(
                slug=slug,
                path=paths["deck_path"],
                html=sidecar_html,
                commit_sha=None,
                source="sidecar",
            )

        def _get_forgejo() -> DeckResponse:
            file = sc.get_file(
                repo_id=repo_id, path=paths["deck_path"], ref=paths["branch"]
            )
            if file.is_binary or file.text is None:
                raise ValidationError("Deck is not UTF-8 text")
            return DeckResponse(
                slug=slug,
                path=paths["deck_path"],
                html=file.text,
                commit_sha=None,
                source="forgejo",
            )

        return await run_in_threadpool(_get_forgejo)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.put("/projects/{slug}/deck", response_model=DeckResponse)
async def put_deck(
    slug: str,
    body: DeckUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> DeckResponse:
    """Save deck: commit Forgejo snapshot and dual-write Coder sidecar when ready."""
    await require_workspace_access(current_user.id, body.workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)
    username = _forge_username(current_user.name or "", str(current_user.email))
    author_name = current_user.name or username
    author_email = str(current_user.email)

    sidecar_base, sidecar_secret = await lookup_slides_sidecar(
        db,
        workspace_id=body.workspace_id,
        user_id=current_user.id,
        slug=slug,
    )

    def _put() -> DeckResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=body.workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        sidecar_ok = _write_deck_via_sidecar(
            sidecar_base,
            sidecar_secret,
            deck_path=paths["deck_path"],
            html=body.html,
        )
        commit = sc.upsert_file(
            repo_id=repo_id,
            path=paths["deck_path"],
            content=body.html,
            message=body.message or "Update slides deck",
            branch=paths["branch"],
            author_name=author_name,
            author_email=author_email,
        )
        try:
            meta_file = sc.get_file(
                repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
            )
            if meta_file.text:
                data = _parse_meta(meta_file.text)
                from datetime import UTC, datetime

                data["workspace_id"] = body.workspace_id
                data["updated_at"] = datetime.now(UTC).isoformat()
                if body.template_id:
                    data["template_id"] = body.template_id
                sc.upsert_file(
                    repo_id=repo_id,
                    path=paths["project_path"],
                    content=json.dumps(data, indent=2) + "\n",
                    message=f"Touch project metadata for {slug}",
                    branch=paths["branch"],
                    author_name=author_name,
                    author_email=author_email,
                )
        except SourceControlError:
            pass
        return DeckResponse(
            slug=slug,
            path=paths["deck_path"],
            html=body.html,
            commit_sha=commit.sha or None,
            source="sidecar" if sidecar_ok else "forgejo",
        )

    try:
        return await run_in_threadpool(_put)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.post("/projects/{slug}/apply-template", response_model=DeckResponse)
async def apply_template(
    slug: str,
    body: ApplyTemplateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> DeckResponse:
    """Rewrite the open deck from a seed template (HTML source of truth)."""
    if body.template_id not in _known_template_ids():
        raise HTTPException(
            status_code=422,
            detail=f"Unknown template_id '{body.template_id}'.",
        )
    seed = _load_seed_html(body.template_id)
    return await put_deck(
        slug,
        DeckUpdateRequest(
            workspace_id=body.workspace_id,
            html=seed,
            message=f"Apply template {body.template_id}",
            template_id=body.template_id,
        ),
        request,
        current_user,
        db,
    )


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
    sc, repo_id = _slides_sc(request)

    def _hist() -> list[CommitResponse]:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        commits = sc.list_commits(
            repo_id=repo_id, ref=paths["branch"], limit=max(1, min(limit, 50))
        )
        return [
            CommitResponse(
                sha=c.sha, message=c.message, author=c.author, date=c.date
            )
            for c in commits
        ]

    try:
        return await run_in_threadpool(_hist)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


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
    if db is None or not workspace_id or not user_id or not slug or not _SLUG_RE.match(slug):
        return None, None
    labels = _runtime_labels(workspace_id, slug)
    result = await db.execute(
        select(CodingEnvironmentModel).where(
            CodingEnvironmentModel.workspace_id == workspace_id,
            CodingEnvironmentModel.user_id == user_id,
            CodingEnvironmentModel.label.in_(labels),
        )
    )
    rows = list(result.scalars().all())
    # Prefer namespaced label over legacy.
    preferred = _runtime_label(workspace_id, slug)
    rows.sort(key=lambda row: 0 if row.label == preferred else 1)
    for row in rows:
        if row.sidecar_base and row.sidecar_secret:
            return str(row.sidecar_base), str(row.sidecar_secret)
    return None, None


async def _ensure_runtime_impl(
    *,
    request: Request,
    workspace_id: str,
    slug: str,
    current_user: User,
    db: AsyncSession | None,
) -> RuntimeResponse:
    # Ownership gate before provisioning compute.
    sc_gate, repo_gate = _slides_sc(request)

    def _owned() -> dict[str, str] | None:
        return _resolve_project_paths(
            sc_gate, repo_id=repo_gate, workspace_id=workspace_id, slug=slug
        )

    try:
        owned_paths = await run_in_threadpool(_owned)
    except SourceControlError as exc:
        # Ownership lookup is read-only; if Forgejo blips, do not masquerade
        # as a Coder outage with a raw PushRejected dump.
        return RuntimeResponse(
            ensured=False,
            detail=_friendly_git_detail(exc),
            label=_runtime_label(workspace_id, slug),
            coder_workspace=_coder_workspace_name(workspace_id, slug),
            branch=_branch_for(workspace_id, slug),
        )
    if owned_paths is None:
        return RuntimeResponse(
            ensured=False,
            detail=f"slides project {slug} not found in this workspace",
            label=_runtime_label(workspace_id, slug),
            coder_workspace=_coder_workspace_name(workspace_id, slug),
            branch=_branch_for(workspace_id, slug),
        )

    label = _runtime_label(workspace_id, slug)
    branch = owned_paths["branch"]
    name = _coder_workspace_name(workspace_id, slug)
    coder_names = _coder_workspace_names(workspace_id, slug)
    coding = _get_coding_environment(request)
    if coding is None:
        return RuntimeResponse(
            ensured=False,
            detail="Coding environment service unavailable (Coder down?)",
            label=label,
            coder_workspace=name,
            branch=branch,
        )
    sc = sc_gate
    repo_id = repo_gate

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
            coder_workspace=name,
            branch=branch,
        )
    template_id, template_name = picked

    author_email = str(current_user.email)
    coder_username = _sanitize_coder_username(
        current_user.name or ""
    ) or _sanitize_coder_username(author_email.split("@", 1)[0])
    expected_base = _build_sidecar_base(coder_username=coder_username, name=name)

    # Reuse the dedicated env for this slides/<slug> when already bound.
    if db is not None:
        labels = _runtime_labels(workspace_id, slug)
        result = await db.execute(
            select(CodingEnvironmentModel).where(
                CodingEnvironmentModel.workspace_id == workspace_id,
                CodingEnvironmentModel.user_id == current_user.id,
                CodingEnvironmentModel.label.in_(labels),
            )
        )
        rows = list(result.scalars().all())
        rows.sort(key=lambda row: 0 if row.label == label else 1)
        existing = rows[0] if rows else None
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
                start_params = _sidecar_start_params(existing.sidecar_secret)
                if status.phase in ("stopped", "stopping"):
                    status = await run_in_threadpool(
                        coding.start,
                        workspace_id=existing.id,
                        params=start_params,
                    )
                if expected_base and not existing.sidecar_base:
                    existing.sidecar_base = expected_base
                    try:
                        await db.commit()
                    except Exception:  # noqa: BLE001
                        await db.rollback()
                has_creds = bool(existing.sidecar_base and existing.sidecar_secret)
                sidecar_ready = False
                detail: str | None = "Sidecar credentials incomplete"
                if has_creds:
                    sidecar_ready = await run_in_threadpool(
                        _wait_for_sidecar,
                        existing.sidecar_base,
                        existing.sidecar_secret,
                    )
                    # Running but still dark: bounce once with secret reinject
                    # (adopt without ABI_SIDECAR_* or crashed sidecar process).
                    if not sidecar_ready and status.phase == "running":
                        logger.warning(
                            "slides sidecar unhealthy for %s; restarting workspace %s",
                            slug,
                            existing.id,
                        )
                        try:
                            await run_in_threadpool(
                                coding.stop, workspace_id=existing.id
                            )
                        except CodingEnvironmentError:
                            pass
                        status = await run_in_threadpool(
                            coding.start,
                            workspace_id=existing.id,
                            params=start_params,
                        )
                        sidecar_ready = await run_in_threadpool(
                            _wait_for_sidecar,
                            existing.sidecar_base,
                            existing.sidecar_secret,
                        )
                    detail = (
                        None
                        if sidecar_ready
                        else "Coder sidecar not reachable; Abi falls back to Forgejo"
                    )
                return RuntimeResponse(
                    ensured=True,
                    phase=status.phase,
                    environment_id=status.id,
                    template_name=template_name,
                    detail=detail,
                    sidecar_ready=sidecar_ready,
                    label=label,
                    coder_workspace=name,
                    branch=branch,
                    coder_ui_url=_coder_ui_url(
                        coding,
                        environment_id=status.id,
                        owner=coder_username,
                        name=name,
                    ),
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
        prior_ws = next(
            (env for env in existing_envs if env.name in coder_names),
            None,
        )
        if prior_ws is not None:
            name = prior_ws.name
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
                    coder_workspace=name,
                    branch=branch,
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
                coder_workspace=name,
                branch=branch,
            )
    except CodingEnvironmentError as exc:
        return RuntimeResponse(
            ensured=False,
            detail=_friendly_coding_detail(exc),
            template_name=template_name,
            label=label,
            coder_workspace=name,
            branch=branch,
        )
    except SourceControlError as exc:
        # Mint/token prep failure or a recoverable Contents race must not
        # surface as "Coder runtime unavailable" with a Forgejo dump.
        return RuntimeResponse(
            ensured=False,
            detail=_friendly_git_detail(exc),
            template_name=template_name,
            label=label,
            coder_workspace=name,
            branch=branch,
        )

    has_creds = bool(ws_base and ws_secret)
    sidecar_ready = False
    if has_creds:
        sidecar_ready = await run_in_threadpool(_wait_for_sidecar, ws_base, ws_secret)
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
    if not has_creds:
        detail = "Sidecar base URL could not be derived"
    elif not sidecar_ready:
        detail = "Coder sidecar not reachable; Abi falls back to Forgejo"
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
        coder_workspace=name,
        branch=branch,
        coder_ui_url=_coder_ui_url(
            coding,
            environment_id=status.id,
            owner=coder_username,
            name=name,
        ),
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
    sc, repo_id = _slides_sc(request)

    def _tree() -> ProjectTreeResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        branch = paths["branch"]
        root = (
            f"slides/{slug}"
            if paths.get("legacy") == "1"
            else f"slides/{_workspace_segment(workspace_id)}/{slug}"
        )
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
        names = {e.name for e in entries}
        if "deck.html" not in names:
            entries.append(
                TreeEntryResponse(
                    name="deck.html", path=paths["deck_path"], type="file"
                )
            )
        if "assets" not in names:
            entries.append(
                TreeEntryResponse(
                    name="assets", path=paths["assets_dir"], type="dir"
                )
            )
        entries.sort(key=lambda e: (0 if e.type == "dir" else 1, e.name))

        assets: list[TreeEntryResponse] = []
        try:
            assets_raw = sc.list_contents(
                repo_id=repo_id, path=paths["assets_dir"], ref=branch
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
        meta = _load_project_meta(
            sc, repo_id=repo_id, path=paths["project_path"], ref=branch
        ) or {}
        try:
            embedded = int(meta.get("embedded_images") or 0)
        except (TypeError, ValueError):
            embedded = 0
        assets_note = meta.get("assets_note")
        if not embedded:
            try:
                deck = sc.get_file(
                    repo_id=repo_id, path=paths["deck_path"], ref=branch
                )
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
        raise _source_control_http_error(exc) from exc


class SlideOutlineItem(BaseModel):
    index: int
    id: str | None = None
    eyebrow: str = ""
    title: str = ""


class TemplateAssetItem(BaseModel):
    name: str
    kind: str = "embedded"


class SeedTemplateResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    preview_bg: str = "#f4f4f4"
    preview_panel: str = "#ffffff"
    preview_accent: str = "#0072ce"
    preview_ink: str = "#2d2d2d"
    slides: list[SlideOutlineItem] = Field(default_factory=list)
    assets: list[TemplateAssetItem] = Field(default_factory=list)


@router.get("/templates", response_model=list[SeedTemplateResponse])
async def list_seed_templates(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
) -> list[SeedTemplateResponse]:
    """List seed templates with slide outlines for the Slides sidebar."""
    await require_workspace_access(current_user.id, workspace_id)
    return [SeedTemplateResponse(**row) for row in _list_seed_template_records()]
