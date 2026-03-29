"""
Lab host-filesystem API.

Serves the ~/aia directory (mounted at /app/aia-host inside Docker) as a
read/write filesystem for the Nexus Lab code editor.  Paths are always
relative to AIA_HOST_ROOT and no path-traversal is permitted.
"""

import mimetypes
import os
from datetime import datetime
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# Public router – no auth – used only for serving static assets (images, fonts)
# so that <img src> and <link rel="stylesheet"> inside srcdoc iframes can load them.
public_router = APIRouter()

# The host ~/aia is bind-mounted here inside the Docker container.
# Falls back to the current working directory for local (non-Docker) dev.
AIA_HOST_ROOT = Path(os.environ.get("AIA_HOST_ROOT", "/app/aia-host")).resolve()

# Directories to skip entirely in listings (too large or irrelevant for Lab)
SKIP_DIRS = {
    ".git", ".next", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build",
    ".turbo", "coverage", ".coverage", "aia-model",
    "archive", "obsidian", "openai", "iphone-jrv", "qonto", "assets",
}

# File extensions to show (code / config / docs only)
SHOW_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".md", ".txt", ".toml", ".cfg", ".ini", ".env", ".sh", ".bash",
    ".zsh", ".html", ".css", ".scss", ".sql", ".graphql", ".proto",
    ".tf", ".hcl", ".dockerfile", "", # no-extension files (Makefile etc.)
}


class LabFileInfo(BaseModel):
    name: str
    path: str           # Always relative to AIA_HOST_ROOT, e.g. "src/aia/__init__.py"
    type: str           # 'file' | 'folder'
    size: int | None = None
    modified: datetime | None = None
    content_type: str | None = None


class LabFileContent(BaseModel):
    path: str
    content: str
    content_type: str


class WriteFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1000)
    content: str = Field(default="", max_length=10_000_000)


class LabFileListResponse(BaseModel):
    files: list[LabFileInfo]
    path: str


def _resolve(rel: str) -> Path:
    """Resolve a relative path under AIA_HOST_ROOT, blocking traversal."""
    rel = rel.strip("/")
    resolved = (AIA_HOST_ROOT / rel).resolve() if rel else AIA_HOST_ROOT.resolve()
    if not str(resolved).startswith(str(AIA_HOST_ROOT)):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


def _rel(p: Path) -> str:
    """Return path relative to AIA_HOST_ROOT as a forward-slash string."""
    return str(p.relative_to(AIA_HOST_ROOT)).replace("\\", "/")


def _content_type(p: Path) -> str:
    ext = p.suffix.lower()
    mapping = {
        ".py": "text/x-python", ".ts": "text/typescript",
        ".tsx": "text/typescript", ".js": "text/javascript",
        ".jsx": "text/javascript", ".json": "application/json",
        ".md": "text/markdown", ".yaml": "text/yaml", ".yml": "text/yaml",
        ".toml": "text/x-toml", ".sh": "text/x-sh", ".bash": "text/x-sh",
        ".html": "text/html", ".css": "text/css", ".txt": "text/plain",
        ".sql": "text/x-sql", ".tf": "text/x-terraform",
    }
    if ext in mapping:
        return mapping[ext]
    guessed, _ = mimetypes.guess_type(str(p))
    return guessed or "text/plain"


def _list_dir(directory: Path) -> list[LabFileInfo]:
    if not directory.exists() or not directory.is_dir():
        return []

    items: list[LabFileInfo] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return []

    for entry in entries:
        name = entry.name
        if name.startswith(".") and name not in (".env",):
            continue

        if entry.is_dir():
            if name in SKIP_DIRS:
                continue
            items.append(LabFileInfo(
                name=name,
                path=_rel(entry),
                type="folder",
                modified=datetime.fromtimestamp(entry.stat().st_mtime),
            ))
        else:
            ext = entry.suffix.lower()
            # No-extension files (Makefile, Dockerfile, etc.)
            if ext not in SHOW_EXTS and ext != "":
                continue
            try:
                stat = entry.stat()
                items.append(LabFileInfo(
                    name=name,
                    path=_rel(entry),
                    type="file",
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    content_type=_content_type(entry),
                ))
            except (PermissionError, OSError):
                continue

    return items


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=LabFileListResponse)
async def list_lab_files(path: str = Query("", description="Relative path to list")):
    """List files/folders under the given path (relative to ~/aia)."""
    target = _resolve(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path!r}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    files = _list_dir(target)
    return LabFileListResponse(files=files, path=path)


@router.get("/read/{path:path}", response_model=LabFileContent)
async def read_lab_file(path: str):
    """Read a text file from the host filesystem."""
    target = _resolve(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except (PermissionError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LabFileContent(path=path, content=content, content_type=_content_type(target))


@router.get("/search", response_model=list[LabFileInfo])
async def search_lab_files(
    q: str = Query("", description="Search query — matched against file paths"),
    limit: int = Query(50, ge=1, le=200),
):
    """Fuzzy-search all files under ~/aia.  Returns up to `limit` matches sorted by relevance."""
    query = q.strip().lower()
    results: list[tuple[int, LabFileInfo]] = []

    for root, dirs, files in os.walk(AIA_HOST_ROOT):
        root_path = Path(root)
        rel_root = _rel(root_path) if root_path != AIA_HOST_ROOT else ""

        # Prune skipped directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in SHOW_EXTS and ext != "":
                continue
            if fname.startswith(".") and fname != ".env":
                continue

            rel_path = f"{rel_root}/{fname}" if rel_root else fname
            rel_lower = rel_path.lower()
            fname_lower = fname.lower()

            # Score: exact filename prefix > filename contains > path contains
            if not query or query in rel_lower:
                if fname_lower.startswith(query):
                    score = 0
                elif query in fname_lower:
                    score = 1
                else:
                    score = 2
                try:
                    fpath = root_path / fname
                    stat = fpath.stat()
                    results.append((score, LabFileInfo(
                        name=fname,
                        path=rel_path,
                        type="file",
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type=_content_type(fpath),
                    )))
                except (PermissionError, OSError):
                    continue

    results.sort(key=lambda x: (x[0], x[1].path))
    return [info for _, info in results[:limit]]


@router.put("/write/{path:path}", response_model=LabFileInfo)
async def write_lab_file(path: str, payload: WriteFileRequest):
    """Write (create or overwrite) a text file on the host filesystem."""
    target = _resolve(path)
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload.content, encoding="utf-8")
        stat = target.stat()
    except (PermissionError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return LabFileInfo(
        name=target.name,
        path=path,
        type="file",
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime),
        content_type=_content_type(target),
    )


# =============================================================================
# Public (no-auth) raw-file endpoint – for <img src>, <link href>, etc.
# inside srcdoc iframes where the browser cannot attach Authorization headers.
# =============================================================================

@public_router.get("/lab/fs/raw/{path:path}")
async def serve_raw_file(path: str):
    """Serve any file under ~/aia as raw bytes with correct Content-Type.

    This endpoint intentionally has no authentication so that browsers can
    load images, fonts, and other assets referenced by slide HTML files.
    Path traversal outside AIA_HOST_ROOT is still blocked.
    """
    target = _resolve(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")

    mime = _content_type(target)
    # Use mimetypes as fallback for binary formats (png, jpg, svg, …)
    if mime == "text/plain":
        guessed, _ = mimetypes.guess_type(str(target))
        if guessed:
            mime = guessed

    return FileResponse(path=str(target), media_type=mime)
