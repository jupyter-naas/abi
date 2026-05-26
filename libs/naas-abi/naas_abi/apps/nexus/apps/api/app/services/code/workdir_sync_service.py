"""Sync My Drive Code sandbox to a local OpenCode/terminal workdir."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import my_drive_code_root
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import AlreadyExistsError
from naas_abi.apps.nexus.apps.api.app.services.files.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

_SYNC_IGNORE = {".nexus_sync", ".DS_Store", "__pycache__"}


@dataclass(frozen=True)
class CodeWorkdirSyncResult:
    local_path: str
    remote_root: str
    files_pulled: int = 0
    files_pushed: int = 0


class CodeWorkdirSyncService:
    def __init__(self, files_service: FilesService):
        self._files = files_service

    def sync_base(self) -> Path:
        raw = os.environ.get("CODE_WORKDIR_SYNC_ROOT")
        if not raw:
            raw = os.environ.get("OPENCODE_WORKDIR") or "/app/sandbox"
        path = Path(raw).expanduser()
        if str(path).startswith("/app/"):
            return path.resolve()
        return path.resolve()

    def local_workdir(self, user_id: str) -> Path:
        normalized = FilesService.normalize_relative_path(user_id)
        if "/" in normalized:
            raise ValueError("user_id must be a single path segment")
        return (self.sync_base() / normalized / "code").resolve()

    def opencode_workdir(self, user_id: str) -> str:
        """Path passed to the host OpenCode process (may differ from container sync path)."""
        local = self.local_workdir(user_id)
        host_root = os.environ.get("OPENCODE_HOST_WORKDIR", "").strip()
        if host_root:
            container_root = self.sync_base()
            try:
                rel = local.relative_to(container_root)
            except ValueError:
                return str(local)
            return str((Path(host_root).expanduser() / rel).resolve())
        return str(local)

    def remote_root(self, user_id: str) -> str:
        return my_drive_code_root(user_id)

    def _ensure_remote_root(self, user_id: str) -> str:
        root = self.remote_root(user_id)
        LegacyStorageMigrator(self._files).ensure_my_drive_migrated(user_id)
        if not self._files._is_directory(root):
            try:
                self._files.create_folder(root)
            except AlreadyExistsError:
                pass
        return root

    def pull(self, user_id: str) -> CodeWorkdirSyncResult:
        remote = self._ensure_remote_root(user_id)
        local = self.local_workdir(user_id)
        local.mkdir(parents=True, exist_ok=True)

        pulled = 0
        if self._files._is_directory(remote):
            files, _dirs = self._files._collect_directory_tree(remote)
            for remote_path in files:
                rel = PurePosixPath(remote_path).relative_to(PurePosixPath(remote))
                target = local / rel.as_posix()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self._files._read_bytes(remote_path))
                pulled += 1

        marker = local / ".nexus_sync"
        marker.write_text(remote, encoding="utf-8")
        return CodeWorkdirSyncResult(local_path=str(local), remote_root=remote, files_pulled=pulled)

    def push(self, user_id: str) -> CodeWorkdirSyncResult:
        remote = self._ensure_remote_root(user_id)
        local = self.local_workdir(user_id)
        if not local.exists():
            return CodeWorkdirSyncResult(local_path=str(local), remote_root=remote, files_pushed=0)

        pushed = 0
        for path in sorted(local.rglob("*")):
            if not path.is_file():
                continue
            if path.name in _SYNC_IGNORE:
                continue
            rel = path.relative_to(local).as_posix()
            remote_path = f"{remote}/{rel}" if rel else remote
            content = path.read_bytes()
            if self._files._file_exists(remote_path):
                self._files._write_bytes(remote_path, content)
            else:
                try:
                    text = content.decode("utf-8")
                    self._files.create_file(remote_path, text, "text/plain")
                except UnicodeDecodeError:
                    self._files._write_bytes(remote_path, content)
            pushed += 1

        return CodeWorkdirSyncResult(local_path=str(local), remote_root=remote, files_pushed=pushed)

    def sync(self, user_id: str, direction: str = "both") -> CodeWorkdirSyncResult:
        normalized = direction.strip().lower()
        if normalized == "pull":
            return self.pull(user_id)
        if normalized == "push":
            return self.push(user_id)
        pulled = self.pull(user_id)
        pushed = self.push(user_id)
        return CodeWorkdirSyncResult(
            local_path=pulled.local_path,
            remote_root=pulled.remote_root,
            files_pulled=pulled.files_pulled,
            files_pushed=pushed.files_pushed,
        )
