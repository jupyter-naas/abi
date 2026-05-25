"""Code sandbox backed by My Drive object storage."""

from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeFilesystemOSError,
    CodeFSDeleteResultData,
    CodeFSEntryData,
    CodeFSListResponseData,
    CodeFSRenameResultData,
    CodeFSWriteResultData,
    CodeInvalidPathError,
    CodePathAlreadyExistsError,
    CodePathNotDirectoryError,
    CodePathNotFileError,
    CodePathNotFoundError,
    CodePathOutsideRootError,
    CodeWriteForbiddenError,
)
from naas_abi.apps.nexus.apps.api.app.services.code.port import CodeFilesystemPort
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import my_drive_code_root
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    AlreadyExistsError,
    FilesDomainError,
    InvalidPathError,
    IsDirectoryError,
    NotFoundError,
    NotTextError,
)
from naas_abi.apps.nexus.apps.api.app.services.files.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService


class MyDriveFilesystemAdapter(CodeFilesystemPort):
    def __init__(self, files_service: FilesService):
        self._files = files_service

    def _require_user_id(self, user_id: str | None) -> str:
        if not user_id:
            raise CodeInvalidPathError("Authenticated user is required for Code sandbox access")
        normalized = FilesService.normalize_relative_path(user_id)
        if "/" in normalized:
            raise CodePathOutsideRootError("user_id must be a single path segment")
        return normalized

    def _sandbox_root(self, user_id: str) -> str:
        return my_drive_code_root(user_id)

    def _ensure_sandbox(self, user_id: str) -> str:
        root = self._sandbox_root(user_id)
        LegacyStorageMigrator(self._files).ensure_my_drive_migrated(user_id)
        if not self._files._is_directory(root):
            try:
                self._files.create_folder(root)
            except AlreadyExistsError:
                pass
        return root

    def _resolve_path(self, path: str, user_id: str) -> str:
        root = self._ensure_sandbox(user_id)
        normalized = FilesService.normalize_relative_path(path, allow_empty=True)
        if not normalized:
            return root
        if normalized == root or normalized.startswith(f"{root}/"):
            return normalized
        return f"{root}/{normalized}"

    def _require_writable(self, target: str, user_id: str) -> None:
        root = self._sandbox_root(user_id)
        if target != root and not target.startswith(f"{root}/"):
            raise CodeWriteForbiddenError(root)

    @staticmethod
    def _modified_to_float(value: datetime | None) -> float:
        if value is None:
            return 0.0
        return value.timestamp()

    @staticmethod
    def _translate_files_error(exc: FilesDomainError) -> CodeFilesystemOSError | CodePathNotFoundError | CodePathAlreadyExistsError | CodePathNotDirectoryError | CodePathNotFileError | CodeInvalidPathError:
        if isinstance(exc, NotFoundError):
            return CodePathNotFoundError(str(exc))
        if isinstance(exc, AlreadyExistsError):
            return CodePathAlreadyExistsError(str(exc))
        if isinstance(exc, InvalidPathError):
            return CodeInvalidPathError(str(exc))
        if isinstance(exc, IsDirectoryError):
            return CodePathNotDirectoryError(str(exc))
        if isinstance(exc, NotTextError):
            return CodePathNotFileError(str(exc))
        return CodeFilesystemOSError(str(exc))

    def _to_entry(self, path: str, entry_type: str, size: int | None, modified: datetime | None, sandbox: str) -> CodeFSEntryData:
        return CodeFSEntryData(
            name=path.split("/")[-1],
            path=path,
            type=entry_type,
            size=size or 0,
            modified=self._modified_to_float(modified),
            writable=path == sandbox or path.startswith(f"{sandbox}/"),
        )

    def list_directory(
        self, path: str, user_id: str | None = None
    ) -> CodeFSListResponseData:
        uid = self._require_user_id(user_id)
        sandbox = self._ensure_sandbox(uid)
        target = self._resolve_path(path, uid)
        try:
            listing = self._files.list_files(path=target)
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc

        entries = [
            self._to_entry(
                file.path,
                file.type,
                file.size,
                file.modified,
                sandbox,
            )
            for file in listing.files
        ]
        return CodeFSListResponseData(files=entries, path=target, sandbox_root=sandbox)

    def read_file(self, path: str, user_id: str | None = None) -> str:
        uid = self._require_user_id(user_id)
        target = self._resolve_path(path, uid)
        try:
            return self._files.read_file(path=target).content
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc

    def write_file(
        self, path: str, content: str, user_id: str | None = None
    ) -> CodeFSWriteResultData:
        uid = self._require_user_id(user_id)
        target = self._resolve_path(path, uid)
        self._require_writable(target, uid)
        try:
            if self._files._file_exists(target):
                result = self._files.update_file(target, content, "text/plain")
            else:
                result = self._files.create_file(target, content, "text/plain")
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc
        return CodeFSWriteResultData(path=target, size=result.size or len(content.encode("utf-8")))

    def create_folder(self, path: str, user_id: str | None = None) -> dict[str, str]:
        uid = self._require_user_id(user_id)
        target = self._resolve_path(path, uid)
        self._require_writable(target, uid)
        try:
            self._files.create_folder(path=target)
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc
        return {"path": target}

    def rename_path(
        self, path: str, new_path: str, user_id: str | None = None
    ) -> CodeFSRenameResultData:
        uid = self._require_user_id(user_id)
        src = self._resolve_path(path, uid)
        dst = self._resolve_path(new_path, uid)
        self._require_writable(src, uid)
        self._require_writable(dst, uid)
        try:
            self._files.rename(old_path=src, new_path=dst)
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc
        return CodeFSRenameResultData(old_path=src, new_path=dst)

    def delete_path(
        self, path: str, user_id: str | None = None
    ) -> CodeFSDeleteResultData:
        uid = self._require_user_id(user_id)
        target = self._resolve_path(path, uid)
        self._require_writable(target, uid)
        try:
            self._files.delete_path(path=target)
        except FilesDomainError as exc:
            raise self._translate_files_error(exc) from exc
        return CodeFSDeleteResultData(path=target, deleted=True)
