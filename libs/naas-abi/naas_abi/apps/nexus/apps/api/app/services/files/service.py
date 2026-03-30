from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    AlreadyExistsError,
    FileContentData,
    FileInfoData,
    FileListResponseData,
    InvalidPathError,
    IsDirectoryError,
    NotFoundError,
    NotTextError,
    PdfPreviewData,
    PreviewConversionError,
    PreviewUnavailableError,
    RawFileData,
    UnsupportedPreviewError,
    UploadTooLargeError,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class FilesService:
    object_storage_prefix = ""
    folder_marker = ".nexus_folder"
    max_upload_size = 50 * 1024 * 1024

    _content_types = {
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }

    _text_content_types = {
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
    }

    def __init__(self, storage: ObjectStorageService):
        self.storage = storage

    @staticmethod
    def normalize_relative_path(path: str, allow_empty: bool = False) -> str:
        raw = (path or "").strip()
        if not raw:
            if allow_empty:
                return ""
            raise InvalidPathError("Path is required")

        path_obj = PurePosixPath(raw)
        parts = [part for part in path_obj.parts if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise InvalidPathError("Invalid path")

        normalized = "/".join(parts).strip("/")
        if not normalized and not allow_empty:
            raise InvalidPathError("Path is required")
        return normalized

    def list_files(self, path: str = "") -> FileListResponseData:
        normalized_path = self.normalize_relative_path(path, allow_empty=True)
        entries = self._list_directory(normalized_path)
        files: list[FileInfoData] = []

        for entry in entries:
            name = entry.split("/")[-1]
            if self._is_directory(entry):
                files.append(
                    FileInfoData(
                        name=name,
                        path=entry,
                        type="folder",
                        modified=datetime.now(),
                    )
                )
                continue

            try:
                content = self._read_bytes(entry)
            except Exceptions.ObjectNotFound:
                continue

            ext = PurePosixPath(entry).suffix.lower()
            files.append(
                FileInfoData(
                    name=name,
                    path=entry,
                    type="file",
                    size=len(content),
                    modified=datetime.now(),
                    content_type=self._content_types.get(ext, "application/octet-stream"),
                )
            )

        return FileListResponseData(files=files, path=normalized_path)

    def create_file(
        self, path: str, content: str = "", content_type: str = "text/plain"
    ) -> FileInfoData:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path) or self._file_exists(normalized_path):
            raise AlreadyExistsError("File already exists")

        content_bytes = content.encode("utf-8")
        self._write_bytes(normalized_path, content_bytes)
        return FileInfoData(
            name=normalized_path.split("/")[-1],
            path=normalized_path,
            type="file",
            size=len(content_bytes),
            modified=datetime.now(),
            content_type=content_type,
        )

    def create_folder(self, path: str) -> FileInfoData:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path) or self._file_exists(normalized_path):
            raise AlreadyExistsError("Folder already exists")

        self._create_folder_marker(normalized_path)
        return FileInfoData(
            name=normalized_path.split("/")[-1],
            path=normalized_path,
            type="folder",
            modified=datetime.now(),
        )

    def rename(self, old_path: str, new_path: str) -> FileInfoData:
        normalized_old_path = self.normalize_relative_path(old_path)
        normalized_new_path = self.normalize_relative_path(new_path)

        if normalized_old_path == normalized_new_path:
            raise InvalidPathError("old_path and new_path must be different")

        target_exists = self._file_exists(normalized_new_path) or self._is_directory(
            normalized_new_path
        )
        if target_exists:
            raise AlreadyExistsError("Target path already exists")

        if self._is_directory(normalized_old_path):
            files, dirs = self._collect_directory_tree(normalized_old_path)
            if not files and not dirs:
                raise NotFoundError("File or folder not found")

            old_root = f"{normalized_old_path}/"
            for file_path in files:
                relative = file_path[len(old_root) :] if file_path.startswith(old_root) else ""
                destination = (
                    f"{normalized_new_path}/{relative}" if relative else normalized_new_path
                )
                self._write_bytes(destination, self._read_bytes(file_path))
                self._delete_file(file_path)

            for source_dir in dirs:
                relative = source_dir[len(old_root) :] if source_dir.startswith(old_root) else ""
                destination_dir = (
                    f"{normalized_new_path}/{relative}" if relative else normalized_new_path
                )
                self._create_folder_marker(destination_dir)

            for source_dir in reversed(dirs):
                self._delete_folder_marker(source_dir)

            return FileInfoData(
                name=normalized_new_path.split("/")[-1],
                path=normalized_new_path,
                type="folder",
                modified=datetime.now(),
            )

        if not self._file_exists(normalized_old_path):
            raise NotFoundError("File or folder not found")

        content = self._read_bytes(normalized_old_path)
        self._write_bytes(normalized_new_path, content)
        self._delete_file(normalized_old_path)
        return FileInfoData(
            name=normalized_new_path.split("/")[-1],
            path=normalized_new_path,
            type="file",
            size=len(content),
            modified=datetime.now(),
        )

    def upload_file(
        self,
        filename: str,
        path: str,
        content: bytes,
        content_type: str | None,
    ) -> FileInfoData:
        safe_filename = PurePosixPath(filename or "untitled").name
        if not safe_filename:
            raise InvalidPathError("Invalid file name")

        base_path = self.normalize_relative_path(path, allow_empty=True)
        full_path = f"{base_path}/{safe_filename}" if base_path else safe_filename
        normalized_path = self.normalize_relative_path(full_path)

        if len(content) > self.max_upload_size:
            raise UploadTooLargeError(max_size_bytes=self.max_upload_size)

        self._write_bytes(normalized_path, content)
        return FileInfoData(
            name=safe_filename,
            path=normalized_path,
            type="file",
            size=len(content),
            modified=datetime.now(),
            content_type=content_type or "application/octet-stream",
        )

    def preview_file_as_pdf(self, path: str) -> PdfPreviewData:
        normalized_path = self.normalize_relative_path(path)
        ext = PurePosixPath(normalized_path).suffix.lower()
        if ext not in {".ppt", ".pptx"}:
            raise UnsupportedPreviewError("Only PPT/PPTX preview is supported")
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot preview a directory")

        try:
            content_bytes = self._read_bytes(normalized_path)
        except Exceptions.ObjectNotFound as exc:
            raise NotFoundError("File not found") from exc

        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise PreviewUnavailableError(
                "PPTX preview is unavailable: LibreOffice is not installed on the API service."
            )

        with tempfile.TemporaryDirectory(prefix="nexus-ppt-preview-") as tmp_dir:
            input_path = Path(tmp_dir) / PurePosixPath(normalized_path).name
            output_name = f"{PurePosixPath(normalized_path).stem}.pdf"
            output_path = Path(tmp_dir) / output_name
            input_path.write_bytes(content_bytes)

            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(Path(tmp_dir)),
                    str(input_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if result.returncode != 0 or not output_path.exists():
                raise PreviewConversionError("Failed to convert presentation to PDF preview.")

            return PdfPreviewData(content=output_path.read_bytes(), filename=output_name)

    def read_file_raw(self, path: str) -> RawFileData:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot read a directory")

        try:
            content_bytes = self._read_bytes(normalized_path)
        except Exceptions.ObjectNotFound as exc:
            raise NotFoundError("File not found") from exc

        ext = PurePosixPath(normalized_path).suffix.lower()
        filename = PurePosixPath(normalized_path).name
        return RawFileData(
            content=content_bytes,
            media_type=self._content_types.get(ext, "application/octet-stream"),
            filename=filename,
        )

    def read_file(self, path: str) -> FileContentData:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot read a directory")

        try:
            content_bytes = self._read_bytes(normalized_path)
        except Exceptions.ObjectNotFound as exc:
            raise NotFoundError("File not found") from exc

        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NotTextError("File is not text") from exc

        ext = PurePosixPath(normalized_path).suffix.lower()
        content_type = self._text_content_types.get(ext, "text/plain")
        return FileContentData(
            path=normalized_path,
            content=content,
            content_type=content_type,
        )

    def update_file(self, path: str, content: str, content_type: str) -> FileInfoData:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot update a directory")
        if not self._file_exists(normalized_path):
            raise NotFoundError("File not found")

        content_bytes = content.encode("utf-8")
        self._write_bytes(normalized_path, content_bytes)
        return FileInfoData(
            name=normalized_path.split("/")[-1],
            path=normalized_path,
            type="file",
            size=len(content_bytes),
            modified=datetime.now(),
            content_type=content_type,
        )

    def delete_path(self, path: str) -> dict[str, str]:
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path):
            files, dirs = self._collect_directory_tree(normalized_path)
            for file_path in files:
                self._delete_file(file_path)
            for directory in reversed(dirs):
                self._delete_folder_marker(directory)
            return {"message": "Folder deleted", "path": normalized_path}

        if not self._file_exists(normalized_path):
            raise NotFoundError("File or folder not found")

        self._delete_file(normalized_path)
        return {"message": "File deleted", "path": normalized_path}

    def _directory_prefix(self, path: str) -> str:
        relative = self.normalize_relative_path(path, allow_empty=True)
        if relative:
            return f"{self.object_storage_prefix}/{relative}".strip("/")
        return self.object_storage_prefix

    def _split_file_path(self, path: str) -> tuple[str, str]:
        relative = self.normalize_relative_path(path)
        if "/" in relative:
            parent, name = relative.rsplit("/", 1)
            return self._directory_prefix(parent), name
        return self._directory_prefix(""), relative

    def _relative_from_storage_path(self, full_path: str) -> str:
        normalized = full_path.strip("/")
        if normalized == self.object_storage_prefix:
            return ""

        prefix = f"{self.object_storage_prefix}/"
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
        return normalized

    def _file_exists(self, path: str) -> bool:
        prefix, key = self._split_file_path(path)
        try:
            self.storage.get_object(prefix, key)
            return True
        except Exceptions.ObjectNotFound:
            return False

    def _is_directory(self, path: str) -> bool:
        try:
            self.storage.list_objects(self._directory_prefix(path))
            return True
        except Exceptions.ObjectNotFound:
            return False

    def _list_directory(self, path: str) -> list[str]:
        prefix = self._directory_prefix(path)
        try:
            raw_paths = self.storage.list_objects(prefix)
        except Exceptions.ObjectNotFound:
            return []

        children: set[str] = set()
        for raw_path in raw_paths:
            relative = self._relative_from_storage_path(raw_path).strip("/")
            if not relative:
                continue
            if relative == self.folder_marker or relative.endswith(f"/{self.folder_marker}"):
                continue
            children.add(relative)
        return sorted(children)

    def _read_bytes(self, path: str) -> bytes:
        prefix, key = self._split_file_path(path)
        return self.storage.get_object(prefix, key)

    def _write_bytes(self, path: str, content: bytes) -> None:
        prefix, key = self._split_file_path(path)
        self.storage.put_object(prefix, key, content)

    def _delete_file(self, path: str) -> None:
        prefix, key = self._split_file_path(path)
        self.storage.delete_object(prefix, key)

    def _create_folder_marker(self, path: str) -> None:
        self.storage.put_object(self._directory_prefix(path), self.folder_marker, b"")

    def _delete_folder_marker(self, path: str) -> None:
        try:
            self.storage.delete_object(self._directory_prefix(path), self.folder_marker)
        except Exceptions.ObjectNotFound:
            pass

    def _collect_directory_tree(self, root_path: str) -> tuple[list[str], list[str]]:
        all_files: list[str] = []
        all_dirs: list[str] = []
        queue = [self.normalize_relative_path(root_path)]
        seen = set(queue)

        while queue:
            current = queue.pop(0)
            all_dirs.append(current)
            for child in self._list_directory(current):
                if self._is_directory(child):
                    if child not in seen:
                        seen.add(child)
                        queue.append(child)
                else:
                    all_files.append(child)

        return all_files, all_dirs
