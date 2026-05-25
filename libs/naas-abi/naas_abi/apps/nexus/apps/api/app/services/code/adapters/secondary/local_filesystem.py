from __future__ import annotations

import os
import shutil
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeFilesystemOSError,
    CodeFSDeleteResultData,
    CodeFSEntryData,
    CodeFSListResponseData,
    CodeFSRenameResultData,
    CodeFSWriteResultData,
    CodePathAlreadyExistsError,
    CodePathNotDirectoryError,
    CodePathNotFileError,
    CodePathNotFoundError,
    CodePathOutsideRootError,
    CodeWriteForbiddenError,
)
from naas_abi.apps.nexus.apps.api.app.services.code.port import CodeFilesystemPort

_IGNORED = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "node_modules",
    ".venv",
    ".ruff_cache",
    ".pytest_cache",
}


class LocalFilesystemAdapter(CodeFilesystemPort):
    def get_root(self) -> Path:
        return Path(os.environ.get("FILESYSTEM_ROOT", "/app")).resolve()

    def get_base_sandbox_rel(self) -> str:
        return os.environ.get("SANDBOX_ROOT", "sandbox").strip("/") or "sandbox"

    def resolve_sandbox_rel(self, user_id: str | None) -> str:
        base = self.get_base_sandbox_rel()
        if not user_id:
            return base
        normalized = user_id.strip().strip("/")
        if not normalized or "/" in normalized or ".." in normalized.split("/"):
            raise CodePathOutsideRootError("user_id must be a single path segment")
        return f"{base}/{normalized}"

    def _sandbox_path(self, user_id: str | None) -> Path:
        root = self.get_root()
        rel = self.resolve_sandbox_rel(user_id)
        sandbox = (root / rel).resolve()
        sandbox.mkdir(parents=True, exist_ok=True)
        return sandbox

    def _resolve_safe(self, rel: str) -> Path:
        root = self.get_root()
        target = (root / rel.lstrip("/")).resolve()
        if not str(target).startswith(str(root)):
            raise CodePathOutsideRootError("Path outside allowed root")
        return target

    def _require_writable(self, target: Path, user_id: str | None) -> None:
        sandbox = self._sandbox_path(user_id)
        if not str(target).startswith(str(sandbox)):
            sandbox_rel = str(sandbox.relative_to(self.get_root()))
            raise CodeWriteForbiddenError(sandbox_rel)

    def _entry(self, path: Path, root: Path, sandbox: Path) -> CodeFSEntryData:
        stat = path.stat()
        return CodeFSEntryData(
            name=path.name,
            path=str(path.relative_to(root)),
            type="folder" if path.is_dir() else "file",
            size=stat.st_size,
            modified=stat.st_mtime,
            writable=str(path).startswith(str(sandbox)),
        )

    def list_directory(
        self, path: str, user_id: str | None = None
    ) -> CodeFSListResponseData:
        root = self.get_root()
        sandbox = self._sandbox_path(user_id)
        target = self._resolve_safe(path)

        if not target.exists():
            raise CodePathNotFoundError(f"Path not found: {path!r}")
        if not target.is_dir():
            raise CodePathNotDirectoryError("Path is not a directory")

        entries: list[CodeFSEntryData] = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name in _IGNORED:
                    continue
                try:
                    entries.append(self._entry(child, root, sandbox))
                except OSError:
                    pass
        except PermissionError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc

        return CodeFSListResponseData(
            files=entries,
            path=str(target.relative_to(root)) if target != root else "",
            sandbox_root=str(sandbox.relative_to(root)),
        )

    def read_file(self, path: str, user_id: str | None = None) -> str:
        target = self._resolve_safe(path)
        if not target.exists():
            raise CodePathNotFoundError(f"File not found: {path!r}")
        if not target.is_file():
            raise CodePathNotFileError("Path is not a file")
        try:
            return target.read_text(errors="replace")
        except OSError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc

    def write_file(
        self, path: str, content: str, user_id: str | None = None
    ) -> CodeFSWriteResultData:
        target = self._resolve_safe(path)
        self._require_writable(target, user_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content)
        except OSError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc
        return CodeFSWriteResultData(path=path, size=target.stat().st_size)

    def create_folder(self, path: str, user_id: str | None = None) -> dict[str, str]:
        target = self._resolve_safe(path)
        self._require_writable(target, user_id)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc
        return {"path": path}

    def rename_path(
        self, path: str, new_path: str, user_id: str | None = None
    ) -> CodeFSRenameResultData:
        src = self._resolve_safe(path)
        dst = self._resolve_safe(new_path)
        self._require_writable(src, user_id)
        self._require_writable(dst, user_id)

        if not src.exists():
            raise CodePathNotFoundError(f"Path not found: {path!r}")
        if dst.exists():
            raise CodePathAlreadyExistsError(f"Destination already exists: {new_path!r}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            src.rename(dst)
        except OSError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc
        return CodeFSRenameResultData(old_path=path, new_path=new_path)

    def delete_path(
        self, path: str, user_id: str | None = None
    ) -> CodeFSDeleteResultData:
        target = self._resolve_safe(path)
        self._require_writable(target, user_id)

        if not target.exists():
            raise CodePathNotFoundError(f"Path not found: {path!r}")
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        except OSError as exc:
            raise CodeFilesystemOSError(str(exc)) from exc
        return CodeFSDeleteResultData(path=path, deleted=True)
