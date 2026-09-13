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

import asyncio
import hashlib
import html as html_lib
import json
import logging
import mimetypes
import re
import secrets
import time
from datetime import timedelta
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.config import (
    ABI_SLIDES_TEMPLATE_NAMESPACE,
    settings,
)
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal, get_db
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
    Commit,
    FileWrite,
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

if TYPE_CHECKING:
    # importlib.abc.Traversable is deprecated from 3.12 and the 3.11 home,
    # importlib.resources.abc, does not exist on the 3.10 this subtree still
    # declares. Annotations are postponed here, so neither is imported at run
    # time and the name has to resolve only for a type checker.
    from importlib.abc import Traversable

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user_required)])

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A template id is ``<namespace>/<stem>``, or a bare stem from before the
# namespaces existed. The namespace is not enumerated here: which ones exist
# is configuration, so an unknown one is a lookup miss, not a syntax error.
_TEMPLATE_REF_RE = re.compile(
    r"^(?:(?P<namespace>[a-z0-9]+(?:-[a-z0-9]+)*)/)?"
    r"(?P<stem>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
_BRANCH_PREFIX = "slides/"
_DEFAULT_TEMPLATE = "minimal-light-v1"
_ABI_NAMESPACE = ABI_SLIDES_TEMPLATE_NAMESPACE
_ABI_PACKAGE = "naas_abi.apps.nexus.assets.slides.templates"
_ABI_ORIGIN = _ABI_PACKAGE
_DEFAULT_TEMPLATE_ID = f"{_ABI_NAMESPACE}/{_DEFAULT_TEMPLATE}"
# Room for a namespace and a separator on top of a kebab stem.
_TEMPLATE_ID_MAX_LEN = 96
_SIDECAR_PORT = 8378
# Ordered by preference. "local-directory" is what LocalDirectoryAdapter
# advertises in the no-Docker runtime; without it the probe finds no template
# and the deck view shows a permanent "Coder runtime unavailable" banner.
_SLIDES_TEMPLATE_NAMES = ("abi-slides", "abi-code-server", "local-directory")
# Cold start: agent connect + startup_script before :8378 listens. Ensure must
# wait; a single probe races "running" phase and falsely marks degraded.
_SIDECAR_WAIT_ATTEMPTS = 2
_SIDECAR_WAIT_INTERVAL_S = 0.5
# One provision at a time per deck: create starts this in the
# background, and the editor POSTs /runtime as soon as HTML is up.
_runtime_ensure_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _runtime_ensure_lock(workspace_id: str, slug: str) -> asyncio.Lock:
    key = (workspace_id, slug)
    lock = _runtime_ensure_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _runtime_ensure_locks[key] = lock
    return lock


def _get_source_control(request: Request) -> SourceControlService:
    service = getattr(request.app.state, "source_control", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule

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
        from naas_abi import ABIModule

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


_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|style|refactor|docs|perf)(\([a-z0-9_.-]+\))?!?: .+"
)


def _conventional_message(message: str, *, default_type: str = "chore") -> str:
    """Coerce a commit message into Conventional Commits for a real deck history."""
    text = (message or "").strip() or "update slides deck"
    if _CONVENTIONAL_COMMIT_RE.match(text):
        return text
    return f"{default_type}(slides): {text}"


_CONVENTIONAL_TYPE_RE = re.compile(
    r"^(feat|fix|chore|style|refactor|docs|perf)(\([a-z0-9_.-]+\))?(?P<breaking>!)?: "
)

# Not paginated: the source control port has no total-commit-count API, so
# this reflects at most the most recent 250 commits. A deck with more history
# than that undercounts its earliest bumps.
_VERSION_COMMIT_SCAN_LIMIT = 250


def _versions_from_commits(commits: list[Commit]) -> dict[str, str]:
    """Cumulative 0.x semver as of each commit (newest-first input), by sha.

    A deck never has a "stable public API" milestone the way a library does,
    so it stays on major 0 forever: a breaking (``!``) or ``feat`` commit
    bumps minor, ``fix``/``perf`` bumps patch, everything else (chore, style,
    refactor, docs...) does not bump. Commits predating this convention (no
    recognizable type) carry the running total forward unchanged rather than
    being guessed at, so every commit — including scaffolding commits from
    repo creation — tracks the version as of that point in history.
    """
    minor = patch = 0
    versions: dict[str, str] = {}
    for commit in reversed(commits):  # oldest first
        match = _CONVENTIONAL_TYPE_RE.match(commit.message or "")
        if match:
            commit_type = match.group(1)
            if match.group("breaking") or commit_type == "feat":
                minor += 1
                patch = 0
            elif commit_type in ("fix", "perf"):
                patch += 1
        versions[commit.sha] = f"0.{minor}.{patch}"
    return versions


def _semver_from_commits(commits: list[Commit]) -> str:
    """The deck's current version: the newest commit's cumulative semver."""
    if not commits:
        return "0.0.0"
    return _versions_from_commits(commits)[commits[0].sha]


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
        message=f"chore(slides): claim {slug} for workspace",
        branch=paths["branch"],
        author_name=author_name,
        author_email=author_email,
    )


_ASSETS_README = """# Presentation assets

Images for this deck live here. ``deck.html`` references them as relative
``assets/<file>`` paths.

## Seed

New presentations and Apply template copy the HTML plus any ``assets/``
folder from the template catalog. Preview resolves those paths through the
slides asset route. File, Export HTML inlines them again so the download
is one file.

Tiny URL-encoded SVG data-URLs (no ``;base64,``) may stay in the HTML.
"""

_ASSET_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SKIP_ASSET_NAMES = {".gitkeep", "README.md"}


def _count_embedded_images(html: str) -> int:
    return len(re.findall(r"data:image/[^;]+;base64,", html or ""))


def _assets_note(*, copied: int, embedded: int) -> str | None:
    if copied:
        return f"{copied} template images copied from the catalog into assets/"
    if embedded:
        return "assets/ seeded empty; template images remain as data-URLs in deck.html"
    return None


def _file_bytes(file) -> bytes | None:
    data = getattr(file, "data", None)
    if isinstance(data, (bytes, bytearray)) and data:
        return bytes(data)
    text = getattr(file, "text", None)
    if isinstance(text, str):
        return text.encode("utf-8")
    return None


def _asset_write_content(name: str, payload: bytes) -> str | bytes:
    if name.endswith(".svg"):
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload
    return payload


def _seed_file_writes(
    *,
    paths: dict[str, str],
    seed: str,
    assets: list[tuple[str, bytes]],
    meta: dict,
    include_project: bool = True,
    include_readme: bool = True,
) -> list[FileWrite]:
    writes: list[FileWrite] = []
    if include_project:
        writes.append(
            FileWrite(
                path=paths["project_path"],
                content=json.dumps(meta, indent=2) + "\n",
            )
        )
    writes.append(FileWrite(path=paths["deck_path"], content=seed))
    if assets:
        for name, payload in assets:
            writes.append(
                FileWrite(
                    path=f"{paths['assets_dir']}/{name}",
                    content=_asset_write_content(name, payload),
                )
            )
    else:
        writes.append(FileWrite(path=paths["assets_gitkeep"], content=""))
    if include_readme:
        writes.append(
            FileWrite(path=paths["assets_readme"], content=_ASSETS_README)
        )
    return writes


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


def _parse_template_ref(template_id: str) -> tuple[str | None, str]:
    """Split ``<namespace>/<stem>``, or a legacy bare stem.

    The namespace is not matched against a fixed set here. Which namespaces
    exist is configuration, so an unknown one is a 404 from the lookup rather
    than a 422 from the grammar.
    """
    match = _TEMPLATE_REF_RE.fullmatch((template_id or "").strip())
    if not match:
        raise HTTPException(
            status_code=422,
            detail=(
                "template_id must be lowercase kebab-case (a-z, 0-9, hyphens), "
                "optionally prefixed with a template source namespace, "
                f"e.g. {_DEFAULT_TEMPLATE_ID}."
            ),
        )
    return match.group("namespace"), match.group("stem")


def _qualify_template_id(namespace: str, stem: str) -> str:
    return f"{namespace}/{stem}"


class _TemplateSource(NamedTuple):
    """One namespaced tree of seed decks.

    ``roots`` is ordered by preference and holds anything traversable: an
    ``importlib.resources`` package root, so packaged seeds work inside a
    wheel, and plain directories. Every source reads through the same two
    helpers below, which is what keeps the resolver free of a branch on whose
    templates these are.
    """

    namespace: str
    origin: str
    roots: tuple[Traversable, ...]


def _abi_template_dirs() -> list[Path]:
    """Checkout and container paths, for when the package root is not on disk."""
    here = Path(__file__).resolve()
    dirs = [
        here.parents[7] / "assets" / "slides" / "templates",
        Path("/app/assets/slides/templates"),
        Path("assets/slides/templates"),
    ]
    try:
        root = resources.files(_ABI_PACKAGE)
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


def _abi_template_source() -> _TemplateSource:
    """The seeds ABI ships, as an ordinary source."""
    roots: list[Traversable] = []
    try:
        roots.append(resources.files(_ABI_PACKAGE))
    except Exception:
        pass
    roots.extend(_abi_template_dirs())
    return _TemplateSource(_ABI_NAMESPACE, _ABI_ORIGIN, tuple(roots))


def _template_sources() -> list[_TemplateSource]:
    """ABI's own seeds, then whatever ``slides_template_sources`` adds.

    Additive rather than a default value for the config list: pydantic replaces
    a list, it does not merge one, so expressing ABI's seeds as the default
    would mean any deploy that declares a source of its own silently loses
    them, and finds out from an empty New Presentation menu.
    """
    sources = [_abi_template_source()]
    for entry in getattr(settings, "slides_template_sources", None) or []:
        directory = Path(entry.path).expanduser()
        try:
            usable = directory.is_dir()
        except OSError:
            usable = False
        if not usable:
            # Warn, do not raise: the directory can go missing after boot, and
            # losing one source must not take the whole picker down with it.
            logger.warning(
                "Slides template source '%s' is not a directory: %s",
                entry.namespace,
                directory,
            )
            continue
        sources.append(
            _TemplateSource(entry.namespace, str(directory), (directory,))
        )
    return sources


def _source_named(namespace: str) -> _TemplateSource | None:
    for source in _template_sources():
        if source.namespace == namespace:
            return source
    return None


def _read_from_roots(source: _TemplateSource, name: str) -> str | None:
    """First root holding a non-empty ``name``."""
    for root in source.roots:
        try:
            text = root.joinpath(name).read_text(encoding="utf-8")
        except Exception:
            continue
        if text.strip():
            return text
    return None


def _entry_is_dir(entry: object) -> bool:
    try:
        return bool(entry.is_dir())
    except Exception:
        return False


def _seed_html_names(stem: str) -> tuple[str, ...]:
    return (f"{stem}.html", f"{stem}/{stem}.html", f"{stem}/index.html")


def _stems_in_roots(source: _TemplateSource) -> list[str]:
    """Seed stems from the first root that has any.

    A stem is a kebab ``*.html`` at the source root, or a kebab folder that
    holds ``{stem}.html`` / ``index.html``.
    """
    for root in source.roots:
        try:
            entries = list(root.iterdir())
        except Exception:
            continue
        stems: set[str] = set()
        for entry in entries:
            name = getattr(entry, "name", "") or ""
            if name.endswith(".html") and _SLUG_RE.match(name[:-5]):
                stems.add(name[:-5])
                continue
            if not _SLUG_RE.match(name) or not _entry_is_dir(entry):
                continue
            for inner in (f"{name}.html", "index.html"):
                try:
                    text = entry.joinpath(inner).read_text(encoding="utf-8")
                except Exception:
                    continue
                if text.strip():
                    stems.add(name)
                    break
        if stems:
            return sorted(stems)
    return []


def _parse_catalog(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict) and isinstance(data.get("templates"), list):
        return [t for t in data["templates"] if isinstance(t, dict) and t.get("id")]
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict) and t.get("id")]
    return []


def _catalog_for(source: _TemplateSource) -> list[dict]:
    return _parse_catalog(_read_from_roots(source, "catalog.json"))


def _stems_for(source: _TemplateSource) -> list[str]:
    """Catalog order first, then anything else on disk, alphabetically.

    Order comes from the source's own ``catalog.json``, so the first row in the
    picker is that source's editorial choice and no id is named here.
    """
    found = set(_stems_in_roots(source))
    catalog_ids = [str(t["id"]) for t in _catalog_for(source)]
    ordered: list[str] = []
    for stem in [*catalog_ids, *sorted(found)]:
        if stem in found and stem not in ordered:
            ordered.append(stem)
    return ordered


def _discover_seed_ids() -> list[str]:
    """Qualified ids (``<namespace>/<stem>``) across every source."""
    ids: list[str] = []
    for source in _template_sources():
        for stem in _stems_for(source):
            qualified = _qualify_template_id(source.namespace, stem)
            if qualified not in ids:
                ids.append(qualified)
    return ids


def _seed_template_meta(template_id: str) -> dict[str, str]:
    """Human metadata for a seed id (its source's catalog, else generated)."""
    namespace, stem = _parse_template_ref(template_id)
    source = _source_named(namespace) if namespace else None
    if source is None:
        source = next(
            (s for s in _template_sources() if stem in _stems_for(s)),
            _abi_template_source(),
        )
    qualified = _qualify_template_id(source.namespace, stem)
    for item in _catalog_for(source):
        if str(item.get("id")) == stem:
            preview = item.get("preview") if isinstance(item.get("preview"), dict) else {}
            return {
                "id": qualified,
                "source": source.namespace,
                "origin": source.origin,
                "name": str(item.get("name") or stem),
                "description": str(item.get("description") or ""),
                "preview_bg": str(preview.get("bg") or "#f4f4f4"),
                "preview_panel": str(preview.get("panel") or "#ffffff"),
                "preview_accent": str(preview.get("accent") or "#0072ce"),
                "preview_ink": str(preview.get("ink") or "#2d2d2d"),
            }
    title = stem.replace("-", " ").replace(" v1", "").title()
    return {
        "id": qualified,
        "source": source.namespace,
        "origin": source.origin,
        "name": title,
        "description": f"Deck seed ({stem})",
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
        file_assets = [
            {"name": name, "kind": "file"} for name in _list_seed_asset_names(tid)
        ]
        meta["assets"] = file_assets or (
            _parse_template_assets(seed) if seed else []
        )
        rows.append(meta)
    return rows


def _known_template_ids() -> set[str]:
    """Qualified ids plus bare stems so older project.json values still apply."""
    ids = set(_discover_seed_ids())
    for tid in list(ids):
        _namespace, stem = _parse_template_ref(tid)
        ids.add(stem)
    return ids


def _load_seed_html(template_id: str = _DEFAULT_TEMPLATE_ID) -> str:
    namespace, stem = _parse_template_ref(template_id)
    source = _source_named(namespace) if namespace else None
    if namespace and source is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown slides template '{template_id}'.",
        )
    # A bare stem predates namespaces, so it resolves in declaration order:
    # ABI first, then configured sources.
    candidates = [source] if source else _template_sources()
    for candidate in candidates:
        for name in _seed_html_names(stem):
            text = _read_from_roots(candidate, name)
            if text:
                return text
    raise HTTPException(
        status_code=404,
        detail=f"Unknown slides template '{template_id}'.",
    )


def _iter_seed_asset_entries(template_id: str):
    """Yield catalog ``assets/`` entries for ``template_id``, if any."""
    namespace, stem = _parse_template_ref(template_id)
    source = _source_named(namespace) if namespace else None
    if namespace and source is None:
        return
    candidates = [source] if source else _template_sources()
    rel = f"{stem}/assets"
    for candidate in candidates:
        for root in candidate.roots:
            try:
                folder = root.joinpath(rel)
                entries = list(folder.iterdir())
            except Exception:
                continue
            yielded = False
            for entry in entries:
                name = getattr(entry, "name", "") or ""
                if (
                    not name
                    or name in _SKIP_ASSET_NAMES
                    or not _ASSET_FILENAME_RE.match(name)
                ):
                    continue
                try:
                    if hasattr(entry, "is_file") and not entry.is_file():
                        continue
                except Exception:
                    continue
                yielded = True
                yield entry, name
            if yielded:
                return


def _list_seed_asset_names(template_id: str) -> list[str]:
    return sorted({name for _entry, name in _iter_seed_asset_entries(template_id)})


def _list_seed_asset_files(template_id: str) -> list[tuple[str, bytes]]:
    assets: list[tuple[str, bytes]] = []
    for entry, name in _iter_seed_asset_entries(template_id):
        try:
            payload = entry.read_bytes()
        except Exception:
            continue
        if payload:
            assets.append((name, payload))
    return assets


def _load_seed_bundle(
    template_id: str = _DEFAULT_TEMPLATE_ID,
) -> tuple[str, list[tuple[str, bytes]]]:
    """HTML plus real files from the catalog ``assets/`` folder.

    Does not parse base64 out of the HTML. Leftover data-URLs stay in the
    deck until someone re-imports the template.
    """
    return _load_seed_html(template_id), _list_seed_asset_files(template_id)


class ProjectCreateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    template_id: str = Field(default=_DEFAULT_TEMPLATE_ID, max_length=_TEMPLATE_ID_MAX_LEN)


class ProjectResponse(BaseModel):
    slug: str
    title: str
    branch: str
    deck_path: str
    template_id: str = _DEFAULT_TEMPLATE
    updated_at: str | None = None
    commit_sha: str | None = None
    archived: bool = False


class ProjectUpdateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None


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
    message: str = Field(default="chore(deck): update slides deck", max_length=200)
    template_id: str | None = Field(default=None, max_length=_TEMPLATE_ID_MAX_LEN)


class ApplyTemplateRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    template_id: str = Field(..., min_length=1, max_length=_TEMPLATE_ID_MAX_LEN)


class CommitResponse(BaseModel):
    sha: str
    message: str
    author: str
    date: str | None = None
    # Cumulative 0.x semver as of this commit (see _versions_from_commits).
    version: str


class DeckDiffFileResponse(BaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    old_path: str | None = None


class DeckDiffResponse(BaseModel):
    base: str
    head: str
    files: list[DeckDiffFileResponse]


class DeckVersionResponse(BaseModel):
    version: str
    commit_count: int


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
    except Exception:
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
    except Exception as exc:
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


def _git_clone_url(
    sc: SourceControlService, repo_id: str, *, username: str, token: str
) -> str:
    """Clone URL the slides sidecar should use for this repo.

    The default targets Forgejo over HTTP, which does not exist in the
    no-Docker runtime. When source control keeps repos on disk it advertises a
    ``file://`` clone URL; use that so provisioning does not try to reach
    ``forgejo:3000`` and fail.
    """
    owner, _, name = repo_id.partition("/")
    try:
        repo = sc.ensure_repo(owner=owner, name=name)
        clone_url = str(getattr(repo, "clone_url", "") or "").strip()
    except Exception:
        clone_url = ""
    if clone_url.startswith("file://"):
        return clone_url
    creds = f"{quote(username, safe='')}:{quote(token, safe='')}"
    return (
        f"{settings.coding_git_clone_scheme}://{creds}"
        f"@{settings.coding_git_clone_host}/{repo_id}.git"
    )


def _adapter_get_parameters(coding: CodingEnvironmentService, workspace_id: str) -> dict[str, str]:
    adapter = getattr(coding, "_adapter", None)
    getter = getattr(adapter, "get_parameters", None)
    if not callable(getter):
        return {}
    try:
        result = getter(workspace_id=workspace_id)
    except Exception:
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


def _meta_archived(meta: dict) -> bool:
    return bool(meta.get("archived"))


def _project_from_meta(
    *,
    workspace_id: str,
    slug: str,
    title: str | None = None,
    template_id: str = _DEFAULT_TEMPLATE,
    commit_sha: str | None = None,
    updated_at: str | None = None,
    legacy: bool = False,
    archived: bool = False,
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
        archived=bool(archived),
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
                    archived=_meta_archived(meta),
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_required),
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
    seed, catalog_assets = _load_seed_bundle(body.template_id)
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
        # Do not list_repos: default_branch is main, else any existing ref.
        default = "main"
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
            "archived": False,
            "updated_at": None,
            "embedded_images": embedded,
            "extracted_images": len(catalog_assets),
            "assets_note": _assets_note(
                copied=len(catalog_assets), embedded=embedded
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
        commit = sc.upsert_files(
            repo_id=repo_id,
            files=_seed_file_writes(
                paths=paths,
                seed=seed,
                assets=catalog_assets,
                meta=meta,
            ),
            message=f"feat(slides): create {slug} from {body.template_id}",
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
        seed_started = time.perf_counter()
        project = await run_in_threadpool(_create)
        logger.info(
            "slides create seed %.3fs slug=%s",
            time.perf_counter() - seed_started,
            slug,
        )
    except BranchNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc

    # HTML is already on the branch. Do not hold the create response for
    # Coder: the editor reads Forgejo immediately; sidecar warms behind it.
    _schedule_created_runtime(
        background_tasks,
        request=request,
        workspace_id=body.workspace_id,
        slug=slug,
        current_user=current_user,
    )
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
            archived=_meta_archived(meta),
        )

    try:
        return await run_in_threadpool(_get)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.patch("/projects/{slug}", response_model=ProjectResponse)
async def update_project(
    slug: str,
    body: ProjectUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> ProjectResponse:
    """Rename (title) and/or archive a deck. Slug and git folder stay put."""
    await require_workspace_access(current_user.id, body.workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    if body.title is None and body.archived is None:
        raise HTTPException(status_code=422, detail="Provide title and/or archived")
    sc, repo_id = _slides_sc(request)
    username = _forge_username(current_user.name or "", str(current_user.email))
    author_name = current_user.name or username
    author_email = str(current_user.email)

    def _update() -> ProjectResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=body.workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        meta = _load_project_meta(
            sc, repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if meta is None:
            raise RepoNotFoundError(f"slides project {slug}")
        if body.title is not None:
            meta["title"] = body.title.strip()
        if body.archived is not None:
            meta["archived"] = bool(body.archived)
        from datetime import UTC, datetime

        meta["workspace_id"] = body.workspace_id
        meta["slug"] = meta.get("slug") or slug
        meta["updated_at"] = datetime.now(UTC).isoformat()
        sc.ensure_user(
            external_id=current_user.id,
            email=author_email,
            username=username,
        )
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(meta, indent=2) + "\n",
            message=f"chore(slides): update {slug} project settings",
            branch=paths["branch"],
            author_name=author_name,
            author_email=author_email,
        )
        branches = {b.name: b for b in sc.list_branches(repo_id=repo_id)}
        return _project_from_meta(
            workspace_id=body.workspace_id,
            slug=slug,
            title=str(meta.get("title") or slug.replace("-", " ").title()),
            template_id=str(meta.get("template_id") or _DEFAULT_TEMPLATE),
            commit_sha=branches[paths["branch"]].commit_sha,
            updated_at=meta.get("updated_at"),
            legacy=paths.get("legacy") == "1",
            archived=_meta_archived(meta),
        )

    try:
        return await run_in_threadpool(_update)
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


@router.get("/projects/{slug}/assets/{filename}")
async def get_project_asset(
    slug: str,
    filename: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> Response:
    """Serve a file from the deck ``assets/`` folder (preview / export)."""
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    if not _ASSET_FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(status_code=422, detail="Invalid asset filename")
    sc, repo_id = _slides_sc(request)

    def _get() -> Response:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        file = sc.get_file(
            repo_id=repo_id,
            path=f"{paths['assets_dir']}/{filename}",
            ref=paths["branch"],
        )
        payload = _file_bytes(file)
        if payload is None:
            raise RepoNotFoundError(f"slides asset {filename}")
        media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Response(content=payload, media_type=media)

    try:
        return await run_in_threadpool(_get)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
            message=_conventional_message(body.message),
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
                    message=f"chore(slides): touch metadata for {slug}",
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


def _read_live_deck_html(
    sc: SourceControlService,
    *,
    repo_id: str,
    paths: dict[str, str],
    sidecar_base: str | None,
    sidecar_secret: str | None,
) -> str:
    sidecar_html = _read_deck_via_sidecar(
        sidecar_base, sidecar_secret, deck_path=paths["deck_path"]
    )
    if isinstance(sidecar_html, str) and sidecar_html:
        return sidecar_html
    file = sc.get_file(repo_id=repo_id, path=paths["deck_path"], ref=paths["branch"])
    if file.is_binary or file.text is None:
        raise ValidationError("Deck is not UTF-8 text")
    return file.text


def _save_live_deck_html(
    sc: SourceControlService,
    *,
    repo_id: str,
    paths: dict[str, str],
    html: str,
    message: str,
    workspace_id: str,
    slug: str,
    current_user: User,
    username: str,
    author_name: str,
    author_email: str,
    sidecar_base: str | None,
    sidecar_secret: str | None,
) -> tuple[str | None, str]:
    sc.ensure_user(
        external_id=current_user.id,
        email=author_email,
        username=username,
    )
    sidecar_ok = _write_deck_via_sidecar(
        sidecar_base,
        sidecar_secret,
        deck_path=paths["deck_path"],
        html=html,
    )
    commit = sc.upsert_file(
        repo_id=repo_id,
        path=paths["deck_path"],
        content=html,
        message=message,
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

            data["workspace_id"] = workspace_id
            data["slug"] = data.get("slug") or slug
            data["updated_at"] = datetime.now(UTC).isoformat()
            sc.upsert_file(
                repo_id=repo_id,
                path=paths["project_path"],
                content=json.dumps(data, indent=2) + "\n",
                message=f"chore(slides): touch metadata for {slug}",
                branch=paths["branch"],
                author_name=author_name,
                author_email=author_email,
            )
    except SourceControlError:
        pass
    return commit.sha or None, "sidecar" if sidecar_ok else "forgejo"


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
    seed, catalog_assets = _load_seed_bundle(body.template_id)
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

    def _apply() -> DeckResponse:
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
            html=seed,
        )
        from datetime import UTC, datetime

        meta = _load_project_meta(
            sc, repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        ) or {}
        meta["workspace_id"] = body.workspace_id
        meta["template_id"] = body.template_id
        meta["updated_at"] = datetime.now(UTC).isoformat()
        meta["embedded_images"] = _count_embedded_images(seed)
        meta["extracted_images"] = len(catalog_assets)
        meta["assets_note"] = _assets_note(
            copied=len(catalog_assets),
            embedded=int(meta["embedded_images"]),
        )
        commit = sc.upsert_files(
            repo_id=repo_id,
            files=_seed_file_writes(
                paths=paths,
                seed=seed,
                assets=catalog_assets,
                meta=meta,
            ),
            message=f"feat(slides): apply template {body.template_id}",
            branch=paths["branch"],
            author_name=author_name,
            author_email=author_email,
        )
        return DeckResponse(
            slug=slug,
            path=paths["deck_path"],
            html=seed,
            commit_sha=commit.sha or None,
            source="sidecar" if sidecar_ok else "forgejo",
        )

    try:
        return await run_in_threadpool(_apply)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


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
        # Scan the same depth as /version so every returned commit's version
        # reflects the true running total, not just what's within `limit`.
        scanned = sc.list_commits(
            repo_id=repo_id, ref=paths["branch"], limit=_VERSION_COMMIT_SCAN_LIMIT
        )
        versions = _versions_from_commits(scanned)
        visible = scanned[: max(1, min(limit, 50))]
        return [
            CommitResponse(
                sha=c.sha,
                message=c.message,
                author=c.author,
                date=c.date,
                version=versions[c.sha],
            )
            for c in visible
        ]

    try:
        return await run_in_threadpool(_hist)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.get("/projects/{slug}/history/diff", response_model=DeckDiffResponse)
async def get_history_diff(
    slug: str,
    workspace_id: str,
    base: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    head: str | None = None,
) -> DeckDiffResponse:
    """Files changed between two commits on the deck branch, for the Files panel.

    ``base`` is the commit the caller wants to diff against (its own baseline,
    e.g. the branch head when the chat session opened this deck). ``head``
    defaults to the current branch tip.
    """
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)

    def _diff() -> DeckDiffResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        resolved_head = head
        if not resolved_head:
            commits = sc.list_commits(repo_id=repo_id, ref=paths["branch"], limit=1)
            if not commits:
                raise RepoNotFoundError(f"slides project {slug}")
            resolved_head = commits[0].sha
        if resolved_head == base:
            return DeckDiffResponse(base=base, head=resolved_head, files=[])
        diff = sc.get_diff(repo_id=repo_id, base=base, head=resolved_head)
        return DeckDiffResponse(
            base=base,
            head=resolved_head,
            files=[
                DeckDiffFileResponse(
                    path=f.path,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    old_path=f.old_path,
                )
                for f in diff.files
            ],
        )

    try:
        return await run_in_threadpool(_diff)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.get("/projects/{slug}/version", response_model=DeckVersionResponse)
async def get_deck_version(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> DeckVersionResponse:
    """0.x semver derived from Conventional Commits history; see `_semver_from_commits`."""
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)

    def _version() -> DeckVersionResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        commits = sc.list_commits(
            repo_id=repo_id, ref=paths["branch"], limit=_VERSION_COMMIT_SCAN_LIMIT
        )
        return DeckVersionResponse(
            version=_semver_from_commits(commits), commit_count=len(commits)
        )

    try:
        return await run_in_threadpool(_version)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


def _build_sidecar_base(*, coder_username: str | None, name: str) -> str | None:
    if not coder_username:
        return None
    return f"http://coder-{coder_username}-{name.lower()}:{_SIDECAR_PORT}"


def _adapter_runtime_binding(
    coding: CodingEnvironmentService, environment_id: str
) -> tuple[str, str] | None:
    """Where the adapter actually started the sidecar, if it says.

    Coder resolves the sidecar by container DNS, so ``_build_sidecar_base``
    can name it before it exists. LocalDirectoryAdapter instead picks a
    loopback port and a secret at provision time and reports them here. This
    is the same call the Code path makes in
    ``/coding-environments/sandbox/runtime``; without it Slides probes a
    Coder hostname that does not resolve outside Docker.
    """
    getter = getattr(coding, "get_runtime_binding", None)
    if not callable(getter):
        return None
    try:
        binding = getter(workspace_id=environment_id)
    except Exception:
        return None
    if not binding:
        return None
    base, secret = binding
    if not base or not secret:
        return None
    return str(base), str(secret)


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
                except Exception:
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
                # The adapter is authoritative: a local runtime moves ports
                # across restarts, so a stored base can be stale (or a Coder
                # hostname written before the runtime was known).
                bound = await run_in_threadpool(
                    _adapter_runtime_binding, coding, existing.id
                )
                if bound is not None:
                    existing.sidecar_base, existing.sidecar_secret = bound
                elif expected_base and not existing.sidecar_base:
                    existing.sidecar_base = expected_base
                if db.dirty:
                    try:
                        await db.commit()
                    except Exception:
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
        repo_url = _git_clone_url(sc, repo_id, username=username, token=token)
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
        bound = await run_in_threadpool(_adapter_runtime_binding, coding, status.id)
        if bound is not None:
            ws_base, ws_secret = bound
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
            bound = await run_in_threadpool(
                _adapter_runtime_binding, coding, status.id
            )
            if bound is not None:
                ws_base, ws_secret = bound
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
            # Replace any stale row for this label, then upsert on the id.
            # Re-adopting the same environment keeps status.id, so inserting a
            # fresh row would collide on the primary key and roll the whole
            # binding back; merge updates it in place instead.
            prior = await db.execute(
                select(CodingEnvironmentModel).where(
                    CodingEnvironmentModel.workspace_id == workspace_id,
                    CodingEnvironmentModel.user_id == current_user.id,
                    CodingEnvironmentModel.label == label,
                )
            )
            for old in prior.scalars().all():
                if old.id != status.id:
                    await db.delete(old)
            await db.merge(
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
        except Exception:
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


async def _ensure_runtime_serialized(
    *,
    request: Request,
    workspace_id: str,
    slug: str,
    current_user: User,
    db: AsyncSession | None,
) -> RuntimeResponse:
    async with _runtime_ensure_lock(workspace_id, slug):
        return await _ensure_runtime_impl(
            request=request,
            workspace_id=workspace_id,
            slug=slug,
            current_user=current_user,
            db=db,
        )


async def _ensure_created_runtime(
    request: Request,
    workspace_id: str,
    slug: str,
    current_user: User,
) -> None:
    """Warm the Coder sidecar after create. Must not delay the create response."""
    started = time.perf_counter()
    try:
        async with AsyncSessionLocal() as db:
            runtime = await _ensure_runtime_serialized(
                request=request,
                workspace_id=workspace_id,
                slug=slug,
                current_user=current_user,
                db=db,
            )
            elapsed = time.perf_counter() - started
            if not runtime.ensured:
                logger.warning(
                    "slides runtime not ensured for %s after %.3fs: %s",
                    slug,
                    elapsed,
                    runtime.detail,
                )
            else:
                logger.info(
                    "slides runtime ready in %.3fs slug=%s sidecar_ready=%s",
                    elapsed,
                    slug,
                    runtime.sidecar_ready,
                )
    except Exception:
        logger.exception("slides runtime ensure failed for %s", slug)


def _schedule_created_runtime(
    background_tasks: BackgroundTasks,
    *,
    request: Request,
    workspace_id: str,
    slug: str,
    current_user: User,
) -> None:
    background_tasks.add_task(
        _ensure_created_runtime,
        request,
        workspace_id,
        slug,
        current_user,
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
    return await _ensure_runtime_serialized(
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
            or _assets_note(copied=len(assets), embedded=embedded),
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
    layout: str = ""


class SlideInsertRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    after_index: int = -1
    layout: str = Field(default="content", max_length=32)
    title: str = Field(default="", max_length=200)


class SlideIndexRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    index: int


class SlideReorderRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    from_index: int | None = None
    to_index: int | None = None
    order: list[int] | None = None


class SlideMutationResponse(BaseModel):
    ok: bool = True
    slug: str
    section_index: int
    section_count: int
    ids: list[str | None] = Field(default_factory=list)
    slides: list[SlideOutlineItem] = Field(default_factory=list)
    html: str | None = None
    commit_sha: str | None = None
    source: str | None = None


class SlideCommandItem(BaseModel):
    type: str = Field(..., min_length=1, max_length=64)
    title: str = Field(default="", max_length=500)
    text: str = Field(default="", max_length=500)


class SlideCommandsRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    requests: list[SlideCommandItem] = Field(..., min_length=1)


class SlideCommandsResponse(BaseModel):
    ok: bool = True
    slug: str
    applied: list[str] = Field(default_factory=list)
    section_index: int = 0
    section_count: int = 0
    slides: list[SlideOutlineItem] = Field(default_factory=list)
    html: str | None = None
    commit_sha: str | None = None
    source: str | None = None
    title: str | None = None
    project_renamed: bool = False
    slug_changed: bool = False


class SlidesListResponse(BaseModel):
    ok: bool = True
    slug: str
    section_count: int
    ids: list[str | None] = Field(default_factory=list)
    slides: list[SlideOutlineItem] = Field(default_factory=list)


class TemplateAssetItem(BaseModel):
    name: str
    kind: str = "embedded"


class SeedTemplateResponse(BaseModel):
    id: str
    # Namespace the id is prefixed with, and the tree it was read from.
    source: str = _ABI_NAMESPACE
    origin: str = _ABI_ORIGIN
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


def _mutation_outline(html: str) -> tuple[list[SlideOutlineItem], list[str | None]]:
    from naas_abi.agents.tools.slides_tools import (
        _slide_outline_items,
        _split_sections,
    )

    _prefix, sections, _suffix = _split_sections(html)
    items = _slide_outline_items(sections)
    slides = [
        SlideOutlineItem(
            index=int(item["index"]),
            id=item.get("id"),
            title=str(item.get("title") or ""),
            layout=str(item.get("layout") or ""),
        )
        for item in items
    ]
    return slides, [s.id for s in slides]


def _mutation_http_error(result: dict) -> HTTPException:
    detail = str(result.get("error") or "Slide mutation failed")
    status = 409 if "last slide" in detail.lower() else 422
    return HTTPException(status_code=status, detail=detail)


async def _run_slide_html_mutation(
    *,
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User,
    db: AsyncSession,
    mutate,
    message: str,
) -> SlideMutationResponse:
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)
    username = _forge_username(current_user.name or "", str(current_user.email))
    author_name = current_user.name or username
    author_email = str(current_user.email)
    sidecar_base, sidecar_secret = await lookup_slides_sidecar(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        slug=slug,
    )

    def _run() -> SlideMutationResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        html = _read_live_deck_html(
            sc,
            repo_id=repo_id,
            paths=paths,
            sidecar_base=sidecar_base,
            sidecar_secret=sidecar_secret,
        )
        mutated = mutate(html)
        if mutated.get("error"):
            raise _mutation_http_error(mutated)
        new_html = str(mutated["html"])
        commit_sha, source = _save_live_deck_html(
            sc,
            repo_id=repo_id,
            paths=paths,
            html=new_html,
            message=message,
            workspace_id=workspace_id,
            slug=slug,
            current_user=current_user,
            username=username,
            author_name=author_name,
            author_email=author_email,
            sidecar_base=sidecar_base,
            sidecar_secret=sidecar_secret,
        )
        slides = [
            SlideOutlineItem(
                index=int(item["index"]),
                id=item.get("id"),
                title=str(item.get("title") or ""),
                layout=str(item.get("layout") or ""),
            )
            for item in mutated.get("slides") or []
        ]
        return SlideMutationResponse(
            ok=True,
            slug=slug,
            section_index=int(mutated["section_index"]),
            section_count=int(mutated["section_count"]),
            ids=list(mutated.get("ids") or []),
            slides=slides,
            html=new_html,
            commit_sha=commit_sha,
            source=source,
        )

    try:
        return await run_in_threadpool(_run)
    except HTTPException:
        raise
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.get("/projects/{slug}/slides", response_model=SlidesListResponse)
async def list_slides(
    slug: str,
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlidesListResponse:
    """Outline of ``<section>`` slides. No HTML body."""
    await require_workspace_access(current_user.id, workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")
    sc, repo_id = _slides_sc(request)
    sidecar_base, sidecar_secret = await lookup_slides_sidecar(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        slug=slug,
    )

    def _list() -> SlidesListResponse:
        paths = _resolve_project_paths(
            sc, repo_id=repo_id, workspace_id=workspace_id, slug=slug
        )
        if paths is None:
            raise RepoNotFoundError(f"slides project {slug}")
        html = _read_live_deck_html(
            sc,
            repo_id=repo_id,
            paths=paths,
            sidecar_base=sidecar_base,
            sidecar_secret=sidecar_secret,
        )
        slides, ids = _mutation_outline(html)
        return SlidesListResponse(
            ok=True,
            slug=slug,
            section_count=len(slides),
            ids=ids,
            slides=slides,
        )

    try:
        return await run_in_threadpool(_list)
    except RepoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SourceControlError as exc:
        raise _source_control_http_error(exc) from exc


@router.post("/projects/{slug}/slides/insert", response_model=SlideMutationResponse)
async def insert_slide(
    slug: str,
    body: SlideInsertRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlideMutationResponse:
    """Insert a slide after ``after_index`` (-1 appends). Same mutation as the agent tool."""
    from naas_abi.agents.tools.slides_tools import _insert_slide_html

    await require_workspace_access(current_user.id, body.workspace_id)
    return await _run_slide_html_mutation(
        slug=slug,
        workspace_id=body.workspace_id,
        request=request,
        current_user=current_user,
        db=db,
        mutate=lambda html: _insert_slide_html(
            html,
            after_index=body.after_index,
            layout=body.layout,
            title=body.title,
        ),
        message=f"feat(slides): insert slide in {slug}",
    )


@router.post("/projects/{slug}/slides/delete", response_model=SlideMutationResponse)
async def delete_slide(
    slug: str,
    body: SlideIndexRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlideMutationResponse:
    """Delete the slide at index. Refuses the last slide."""
    from naas_abi.agents.tools.slides_tools import _delete_slide_html

    await require_workspace_access(current_user.id, body.workspace_id)
    return await _run_slide_html_mutation(
        slug=slug,
        workspace_id=body.workspace_id,
        request=request,
        current_user=current_user,
        db=db,
        mutate=lambda html: _delete_slide_html(html, body.index),
        message=f"refactor(slides): delete slide in {slug}",
    )


@router.post("/projects/{slug}/slides/duplicate", response_model=SlideMutationResponse)
async def duplicate_slide(
    slug: str,
    body: SlideIndexRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlideMutationResponse:
    """Duplicate the slide at index and insert the copy after it."""
    from naas_abi.agents.tools.slides_tools import _duplicate_slide_html

    await require_workspace_access(current_user.id, body.workspace_id)
    return await _run_slide_html_mutation(
        slug=slug,
        workspace_id=body.workspace_id,
        request=request,
        current_user=current_user,
        db=db,
        mutate=lambda html: _duplicate_slide_html(html, body.index),
        message=f"feat(slides): duplicate slide in {slug}",
    )


@router.post("/projects/{slug}/slides/reorder", response_model=SlideMutationResponse)
async def reorder_slides(
    slug: str,
    body: SlideReorderRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlideMutationResponse:
    """Move one slide (from_index/to_index) or apply a full ``order`` permutation."""
    from naas_abi.agents.tools.slides_tools import _reorder_slides_html

    await require_workspace_access(current_user.id, body.workspace_id)
    return await _run_slide_html_mutation(
        slug=slug,
        workspace_id=body.workspace_id,
        request=request,
        current_user=current_user,
        db=db,
        mutate=lambda html: _reorder_slides_html(
            html,
            from_index=body.from_index,
            to_index=body.to_index,
            order=body.order,
        ),
        message=f"style(slides): reorder slides in {slug}",
    )


def _write_project_display_title(
    sc: SourceControlService,
    *,
    repo_id: str,
    paths: dict[str, str],
    slug: str,
    workspace_id: str,
    title: str,
    current_user: User,
    username: str,
    author_name: str,
    author_email: str,
) -> dict:
    """Set project.json title. Slug and git folder stay put."""
    meta = _load_project_meta(
        sc, repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
    )
    if meta is None:
        raise RepoNotFoundError(f"slides project {slug}")
    from datetime import UTC, datetime

    meta["title"] = title.strip()
    meta["workspace_id"] = workspace_id
    meta["slug"] = meta.get("slug") or slug
    meta["updated_at"] = datetime.now(UTC).isoformat()
    sc.ensure_user(
        external_id=current_user.id,
        email=author_email,
        username=username,
    )
    sc.upsert_file(
        repo_id=repo_id,
        path=paths["project_path"],
        content=json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        message=f"chore(slides): rename project {slug}",
        branch=paths["branch"],
        author_name=author_name,
        author_email=author_email,
    )
    return meta


@router.post("/projects/{slug}/commands", response_model=SlideCommandsResponse)
async def apply_slide_commands_route(
    slug: str,
    body: SlideCommandsRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SlideCommandsResponse:
    """Batch of named slide verbs. See COMMANDS.md. This pass: rename and title."""
    from naas_abi.agents.tools.slides_commands import apply_slide_commands

    await require_workspace_access(current_user.id, body.workspace_id)
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="Invalid slug")

    payloads = [item.model_dump() for item in body.requests]

    def _mutate(html: str) -> dict:
        return apply_slide_commands(html, payloads)

    mutated = await _run_slide_html_mutation(
        slug=slug,
        workspace_id=body.workspace_id,
        request=request,
        current_user=current_user,
        db=db,
        mutate=_mutate,
        message=f"feat(slides): apply commands in {slug}",
    )
    from naas_abi.agents.tools.slides_commands import last_rename_deck_title

    rename_title = last_rename_deck_title(payloads)
    project_renamed = False
    if rename_title:
        sc, repo_id = _slides_sc(request)
        username = _forge_username(current_user.name or "", str(current_user.email))
        author_name = current_user.name or username
        author_email = str(current_user.email)

        def _rename() -> None:
            paths = _resolve_project_paths(
                sc, repo_id=repo_id, workspace_id=body.workspace_id, slug=slug
            )
            if paths is None:
                raise RepoNotFoundError(f"slides project {slug}")
            _write_project_display_title(
                sc,
                repo_id=repo_id,
                paths=paths,
                slug=slug,
                workspace_id=body.workspace_id,
                title=rename_title,
                current_user=current_user,
                username=username,
                author_name=author_name,
                author_email=author_email,
            )

        try:
            await run_in_threadpool(_rename)
            project_renamed = True
        except RepoNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SourceControlError as exc:
            raise _source_control_http_error(exc) from exc

    return SlideCommandsResponse(
        ok=True,
        slug=slug,
        applied=[item.type for item in body.requests],
        section_index=mutated.section_index,
        section_count=mutated.section_count,
        slides=mutated.slides,
        html=mutated.html,
        commit_sha=mutated.commit_sha,
        source=mutated.source,
        title=rename_title or None,
        project_renamed=project_renamed,
        slug_changed=False,
    )
