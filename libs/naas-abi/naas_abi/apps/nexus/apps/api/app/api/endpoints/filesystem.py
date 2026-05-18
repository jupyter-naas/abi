"""
Real filesystem browser — exposes the host/container filesystem under a
configurable root. Intended for the Code section in Nexus where developers
need direct access to the ABI project source tree.

Root is controlled by the FILESYSTEM_ROOT environment variable (defaults to
/app, which is where the ABI project is mounted inside Docker).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter()

# ─── Root configuration ───────────────────────────────────────────────────────

def _get_root() -> Path:
    return Path(os.environ.get("FILESYSTEM_ROOT", "/app")).resolve()


def _resolve_safe(rel: str) -> Path:
    """Resolve rel under root; raise 400 if it escapes."""
    root = _get_root()
    target = (root / rel.lstrip("/")).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Path outside allowed root")
    return target


# ─── Schemas ─────────────────────────────────────────────────────────────────

class FSEntry(BaseModel):
    name: str
    path: str       # relative to root, used as the stable identifier
    type: str       # "file" | "folder"
    size: int
    modified: float


class FSListResponse(BaseModel):
    files: list[FSEntry]
    path: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

_IGNORED = {".git", "__pycache__", ".DS_Store", "node_modules", ".venv", ".ruff_cache", ".pytest_cache"}


def _entry(path: Path, root: Path) -> FSEntry:
    stat = path.stat()
    return FSEntry(
        name=path.name,
        path=str(path.relative_to(root)),
        type="folder" if path.is_dir() else "file",
        size=stat.st_size,
        modified=stat.st_mtime,
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=FSListResponse)
def list_path(path: str = Query("", description="Path relative to filesystem root")):
    """List directory contents at *path* (relative to FILESYSTEM_ROOT)."""
    root = _get_root()
    target = _resolve_safe(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path!r}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries: list[FSEntry] = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in _IGNORED:
                continue
            try:
                entries.append(_entry(child, root))
            except OSError:
                pass
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return FSListResponse(
        files=entries,
        path=str(target.relative_to(root)) if target != root else "",
    )


@router.get("/content", response_class=PlainTextResponse)
def read_file(path: str = Query(..., description="File path relative to filesystem root")):
    """Return the raw text content of a file."""
    target = _resolve_safe(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path!r}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    try:
        return target.read_text(errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class WriteBody(BaseModel):
    content: str = ""


@router.put("/content")
def write_file(path: str = Query(..., description="File path relative to filesystem root"), body: WriteBody = WriteBody()):
    """Overwrite a file with new content. Creates parent directories if needed."""
    target = _resolve_safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(body.content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": path, "size": target.stat().st_size}


@router.post("/folder")
def create_folder(path: str = Query(..., description="Folder path relative to filesystem root")):
    """Create a directory (and any missing parents)."""
    target = _resolve_safe(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": path}


@router.delete("/content")
def delete_path(path: str = Query(..., description="File or folder path relative to filesystem root")):
    """Delete a file or directory tree."""
    import shutil

    target = _resolve_safe(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path!r}")
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": path, "deleted": True}
