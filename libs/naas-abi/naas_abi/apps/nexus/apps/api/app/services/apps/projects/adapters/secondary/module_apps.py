"""Module apps on disk, as the Apps catalog sees them.

The folder comes from the catalog (``module_app_dir``), so a module that
reshapes discovery (Bob's nested ``apps/<library>/<name>``) resolves the same
way the Apps page does. Git facts (repo-relative path, commit) are read from
``.git`` without a git binary; without a checkout the project root is the
API's working directory.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppOrigin,
    ModuleAppSource,
    ModuleAppSourcePort,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    skipped_on_import,
)

_SKIP_WALK = {"node_modules", ".git", ".wrangler", "__pycache__"}


def git_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_dir(root: Path) -> Path | None:
    dot_git = root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():  # worktree or submodule: "gitdir: <path>"
        line = dot_git.read_text(encoding="utf-8").strip()
        if line.startswith("gitdir:"):
            target = Path(line[len("gitdir:") :].strip())
            return target if target.is_absolute() else (root / target).resolve()
    return None


def head_commit(root: Path) -> str | None:
    git_dir = _git_dir(root)
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head or None
    ref = head[len("ref:") :].strip()
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip() or None
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha
    return None


class ModuleAppSourceDisk(ModuleAppSourcePort):
    def __init__(
        self,
        *,
        app_dir: Callable[[str], Path | None],
        modules: Callable[[], Iterable[Any]],
        project_root: Path | None = None,
    ) -> None:
        self._app_dir = app_dir
        self._modules = modules
        cwd = Path.cwd()
        self.project_root = project_root or git_root(cwd) or cwd

    def _in_project(self, path: Path) -> str | None:
        """Repo-relative path when ``path`` belongs to the host project repo."""
        try:
            rel = path.resolve().relative_to(self.project_root.resolve())
        except ValueError:
            return None
        # Vendored checkouts (.abi) and installed packages are other repos.
        if any(part.startswith(".") or part == "site-packages" for part in rel.parts):
            return None
        root = git_root(path)
        if root is not None and root.resolve() != self.project_root.resolve():
            return None
        return rel.as_posix()

    def get(self, app_id: str) -> ModuleAppSource | None:
        app_dir = self._app_dir(app_id)
        if app_dir is None or not app_dir.is_dir():
            return None
        module_path, _, app_name = app_id.partition(":")
        try:
            manifest = json.loads((app_dir / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        if not isinstance(manifest, dict):
            manifest = {}
        files: dict[str, bytes] = {}
        skipped: list[str] = []
        pending = [app_dir]
        while pending:
            directory = pending.pop()
            for entry in sorted(directory.iterdir()):
                rel = entry.relative_to(app_dir).as_posix()
                if entry.is_dir():
                    if entry.name in _SKIP_WALK:
                        skipped.append(f"{rel}/")
                    else:
                        pending.append(entry)
                    continue
                if not entry.is_file():
                    continue
                if skipped_on_import(rel):
                    skipped.append(rel)
                    continue
                files[rel] = entry.read_bytes()
        repo_path = self._in_project(app_dir)
        root = git_root(app_dir)
        url = manifest.get("url")
        origin = AppOrigin(
            app_id=app_id,
            module_path=module_path,
            app_name=app_name,
            repo_path=repo_path,
            source_commit=head_commit(root) if root is not None else None,
            kind="bundled" if str(url or "").startswith("html:") else "external",
            url=str(url) if url else None,
        )
        return ModuleAppSource(
            origin=origin, manifest=manifest, files=files, skipped=tuple(skipped)
        )

    def module_targets(self) -> dict[str, str]:
        targets: dict[str, str] = {}
        for module in self._modules():
            module_root = getattr(module, "module_root_path", None)
            if not module_root:
                continue
            rel = self._in_project(Path(module_root))
            if rel is None:
                continue
            targets[module.__class__.__module__] = f"{rel}/apps"
        return targets
