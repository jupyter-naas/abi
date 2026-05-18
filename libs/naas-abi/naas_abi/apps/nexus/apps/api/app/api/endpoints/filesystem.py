"""
Real filesystem browser — exposes the host/container filesystem under a
configurable root. Intended for the Code section in Nexus where developers
need direct access to the ABI project source tree.

Root is controlled by the FILESYSTEM_ROOT environment variable (defaults to
/app). Write operations (create/rename/delete) are restricted to the sandbox
subtree controlled by SANDBOX_ROOT (defaults to "sandbox", relative to root).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from pydantic import BaseModel

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# ─── Root / sandbox configuration ─────────────────────────────────────────────

def _get_root() -> Path:
    return Path(os.environ.get("FILESYSTEM_ROOT", "/app")).resolve()


def _get_sandbox() -> Path:
    """Subtree where writes are allowed. Relative to FILESYSTEM_ROOT."""
    root = _get_root()
    rel = os.environ.get("SANDBOX_ROOT", "sandbox")
    sandbox = (root / rel).resolve()
    sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox


def _resolve_safe(rel: str) -> Path:
    """Resolve *rel* under root; raise 400 if it escapes."""
    root = _get_root()
    target = (root / rel.lstrip("/")).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Path outside allowed root")
    return target


def _require_writable(target: Path) -> None:
    """Raise 403 if *target* is outside the sandbox subtree."""
    sandbox = _get_sandbox()
    if not str(target).startswith(str(sandbox)):
        raise HTTPException(
            status_code=403,
            detail=f"Write access restricted to {sandbox.relative_to(_get_root())}/ — read-only outside sandbox",
        )


# ─── Schemas ──────────────────────────────────────────────────────────────────

class FSEntry(BaseModel):
    name: str
    path: str       # relative to root, stable identifier
    type: str       # "file" | "folder"
    size: int
    modified: float
    writable: bool  # true when path is inside sandbox


class FSListResponse(BaseModel):
    files: list[FSEntry]
    path: str
    sandbox_root: str   # relative path of sandbox so the frontend can show it


# ─── Helpers ──────────────────────────────────────────────────────────────────

_IGNORED = {".git", "__pycache__", ".DS_Store", "node_modules", ".venv", ".ruff_cache", ".pytest_cache"}


def _entry(path: Path, root: Path, sandbox: Path) -> FSEntry:
    stat = path.stat()
    return FSEntry(
        name=path.name,
        path=str(path.relative_to(root)),
        type="folder" if path.is_dir() else "file",
        size=stat.st_size,
        modified=stat.st_mtime,
        writable=str(path).startswith(str(sandbox)),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/", response_model=FSListResponse)
def list_path(path: str = Query("", description="Path relative to filesystem root")):
    """List directory contents at *path* (relative to FILESYSTEM_ROOT)."""
    root = _get_root()
    sandbox = _get_sandbox()
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
                entries.append(_entry(child, root, sandbox))
            except OSError:
                pass
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return FSListResponse(
        files=entries,
        path=str(target.relative_to(root)) if target != root else "",
        sandbox_root=str(sandbox.relative_to(root)),
    )


@router.get("/content", response_class=PlainTextResponse)
def read_file(path: str = Query(..., description="File path relative to filesystem root")):
    """Return the raw text content of a file (read anywhere under root)."""
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
def write_file(
    path: str = Query(..., description="File path relative to filesystem root"),
    body: WriteBody = WriteBody(),
):
    """Overwrite a file with new content (sandbox only)."""
    target = _resolve_safe(path)
    _require_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(body.content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": path, "size": target.stat().st_size}


@router.post("/folder")
def create_folder(path: str = Query(..., description="Folder path relative to filesystem root")):
    """Create a directory (sandbox only)."""
    target = _resolve_safe(path)
    _require_writable(target)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"path": path}


class RenameBody(BaseModel):
    new_path: str


@router.post("/rename")
def rename_path(
    path: str = Query(..., description="Current path relative to filesystem root"),
    body: RenameBody = ...,
):
    """Atomically rename/move a file or folder (sandbox only)."""
    src = _resolve_safe(path)
    dst = _resolve_safe(body.new_path)
    _require_writable(src)
    _require_writable(dst)

    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path!r}")
    if dst.exists():
        raise HTTPException(status_code=409, detail=f"Destination already exists: {body.new_path!r}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dst)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"old_path": path, "new_path": body.new_path}


@router.delete("/content")
def delete_path(path: str = Query(..., description="File or folder path relative to filesystem root")):
    """Delete a file or directory tree (sandbox only)."""
    target = _resolve_safe(path)
    _require_writable(target)

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
