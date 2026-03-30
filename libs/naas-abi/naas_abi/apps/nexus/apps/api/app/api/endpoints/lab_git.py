"""
Lab git API — exposes real git state of the ~/aia repo to Nexus.

Runs git commands against AIA_HOST_ROOT (bind-mounted ~/aia).
All write operations (checkout, create branch) are intentionally minimal
and safe: no force-push, no reset --hard, no destructive ops.
"""

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])

AIA_HOST_ROOT = Path(os.environ.get("AIA_HOST_ROOT", "/app/aia-host")).resolve()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _git(*args: str, check: bool = True) -> str:
    """Run a git command in AIA_HOST_ROOT and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(AIA_HOST_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if check and result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"git {' '.join(args)} failed: {result.stderr.strip()}",
        )
    return result.stdout.strip()


def _is_git_repo() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(AIA_HOST_ROOT),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return result.returncode == 0


# ─── Models ──────────────────────────────────────────────────────────────────

class GitBranch(BaseModel):
    name: str
    current: bool
    remote: bool = False
    ahead: int = 0
    behind: int = 0


class GitChangedFile(BaseModel):
    status: str   # M, A, D, ?, R, C …
    path: str


class GitStatus(BaseModel):
    branch: str
    ahead: int
    behind: int
    changed: list[GitChangedFile]
    staged: list[GitChangedFile]
    untracked: list[GitChangedFile]
    is_dirty: bool


class CheckoutRequest(BaseModel):
    branch: str = Field(..., min_length=1, max_length=200)
    create: bool = False


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/branches")
async def list_branches() -> list[GitBranch]:
    """List all local (and remote-tracking) branches."""
    if not _is_git_repo():
        raise HTTPException(status_code=400, detail="Not a git repository")

    current = _git("branch", "--show-current")

    # Local branches
    local_raw = _git("branch", "--format=%(refname:short)")
    local_branches: list[GitBranch] = []
    for name in local_raw.splitlines():
        name = name.strip()
        if not name:
            continue
        # Get ahead/behind vs upstream
        ahead, behind = 0, 0
        try:
            rev = _git("rev-list", "--left-right", "--count", f"{name}...origin/{name}", check=False)
            if rev:
                parts = rev.split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])
        except Exception:
            pass
        local_branches.append(GitBranch(
            name=name,
            current=(name == current),
            remote=False,
            ahead=ahead,
            behind=behind,
        ))

    return local_branches


@router.get("/status")
async def git_status() -> GitStatus:
    """Return current branch + working-tree status."""
    if not _is_git_repo():
        raise HTTPException(status_code=400, detail="Not a git repository")

    branch = _git("branch", "--show-current") or "HEAD"

    # Ahead/behind upstream
    ahead, behind = 0, 0
    try:
        rev = _git("rev-list", "--left-right", "--count", f"HEAD...origin/{branch}", check=False)
        if rev:
            parts = rev.split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
    except Exception:
        pass

    # Porcelain status
    raw = _git("status", "--porcelain=v1")
    staged: list[GitChangedFile] = []
    changed: list[GitChangedFile] = []
    untracked: list[GitChangedFile] = []

    for line in raw.splitlines():
        if len(line) < 3:
            continue
        xy = line[:2]
        path = line[3:].strip().split(" -> ")[-1]  # handle renames
        x, y = xy[0], xy[1]

        if x == "?" and y == "?":
            untracked.append(GitChangedFile(status="?", path=path))
            continue
        if x != " " and x != "?":
            staged.append(GitChangedFile(status=x, path=path))
        if y != " " and y != "?":
            changed.append(GitChangedFile(status=y, path=path))

    return GitStatus(
        branch=branch,
        ahead=ahead,
        behind=behind,
        staged=staged,
        changed=changed,
        untracked=untracked,
        is_dirty=bool(staged or changed or untracked),
    )


@router.post("/checkout")
async def checkout_branch(payload: CheckoutRequest) -> dict:
    """Checkout (or create) a branch."""
    if not _is_git_repo():
        raise HTTPException(status_code=400, detail="Not a git repository")

    branch = payload.branch.strip()
    if not branch:
        raise HTTPException(status_code=400, detail="Branch name is required")

    if payload.create:
        _git("checkout", "-b", branch)
    else:
        _git("checkout", branch)

    return {"branch": branch, "created": payload.create}
