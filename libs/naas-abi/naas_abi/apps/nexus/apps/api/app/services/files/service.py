from __future__ import annotations

import io
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path, PurePosixPath

from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    AlreadyExistsError,
    ArchiveTooLargeError,
    ExtractTooLargeError,
    FileContentData,
    FileInfoData,
    FileListResponseData,
    InvalidArchiveError,
    InvalidPathError,
    IsDirectoryError,
    NotFoundError,
    NotTextError,
    PdfPreviewData,
    PreviewConversionError,
    PreviewUnavailableError,
    RawFileData,
    UnsupportedArchiveError,
    UnsupportedPreviewError,
    UploadTooLargeError,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class FilesService:
    object_storage_prefix = ""
    folder_marker = ".nexus_folder"
    max_upload_size = 50 * 1024 * 1024
    max_archive_files = 10_000
    max_extract_files = 10_000
    max_extract_uncompressed_bytes = 512 * 1024 * 1024
    max_extract_member_bytes = 100 * 1024 * 1024
    archive_chunk_size = 64 * 1024

    _EXTRACTABLE_SUFFIXES = (
        ".tar.gz",
        ".tgz",
        ".tar",
        ".zip",
    )

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
        ".zip": "application/zip",
        ".tar": "application/x-tar",
        ".gz": "application/gzip",
        ".tgz": "application/gzip",
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

    _SORT_KEYS = frozenset({"name", "size", "modified"})

    def list_files(
        self,
        path: str = "",
        limit: int | None = None,
        offset: int = 0,
        search: str | None = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> FileListResponseData:
        """List a directory's entries.

        ``_list_directory`` returns a stable, alphabetically sorted listing, so
        we can slice it with ``offset``/``limit`` *before* categorizing entries
        or reading metadata. This is what keeps large folders (e.g. 200+ files)
        responsive: only the requested page pays the per-entry storage cost.
        ``limit=None`` returns every entry (unchanged legacy behavior).

        ``search`` filters entries by a case-insensitive substring of their name
        (the final path segment) before paging, so ``total`` reflects the number
        of matches and pagination walks the filtered set — the same folder-scoped
        match the UI used to do client-side.

        ``sort_by`` (``name`` | ``size`` | ``modified``) and ``sort_dir``
        (``asc`` | ``desc``) order the full filtered listing before paging, so
        the sort spans every page rather than just the current one. Sorting by
        name needs no per-entry metadata, so only the returned page is stat-ed;
        sorting by size or modified must stat every entry to compare them.
        """
        normalized_path = self.normalize_relative_path(path, allow_empty=True)
        entries = self._list_directory(normalized_path)

        needle = search.strip().lower() if search else ""
        if needle:
            entries = [entry for entry in entries if needle in entry.split("/")[-1].lower()]

        total = len(entries)
        sort_key = sort_by if sort_by in self._SORT_KEYS else "name"
        reverse = sort_dir == "desc"
        start = max(offset, 0)

        if sort_key == "name":
            entries.sort(key=lambda entry: entry.split("/")[-1].lower(), reverse=reverse)
            page = entries[start : start + limit] if limit is not None else entries[start:]
            files = [
                info for entry in page if (info := self._build_file_info(entry)) is not None
            ]
        else:
            infos = [
                info for entry in entries if (info := self._build_file_info(entry)) is not None
            ]
            if sort_key == "size":
                infos.sort(
                    key=lambda info: info.size if info.size is not None else -1,
                    reverse=reverse,
                )
            else:  # modified
                infos.sort(key=lambda info: info.modified or datetime.min, reverse=reverse)
            files = infos[start : start + limit] if limit is not None else infos[start:]

        return FileListResponseData(files=files, path=normalized_path, total=total)

    def _build_file_info(self, entry: str) -> FileInfoData | None:
        """Resolve a single directory entry into a ``FileInfoData``.

        Returns ``None`` when the entry vanished between listing and stat (a
        concurrent delete). Files carry real size/modified metadata pulled via a
        cheap ``stat`` — no full object read. Folders have no tracked timestamp,
        so ``modified`` is left unset.

        If a storage adapter cannot produce metadata for an object, the listing
        must still succeed: the file is returned without size/modified rather
        than dropped or raised (size/modified sorts then treat it as unknown).
        """
        name = entry.split("/")[-1]
        if self._is_directory(entry):
            return FileInfoData(name=name, path=entry, type="folder")
        ext = PurePosixPath(entry).suffix.lower()
        content_type = self._content_types.get(ext, "application/octet-stream")
        try:
            size, modified = self._stat_file(entry)
        except Exceptions.ObjectNotFound:
            return None
        except Exception:
            # Never let a metadata hiccup on one object break the whole listing.
            return FileInfoData(name=name, path=entry, type="file", content_type=content_type)
        return FileInfoData(
            name=name,
            path=entry,
            type="file",
            size=size,
            modified=modified,
            content_type=content_type,
        )

    def _stat_file(self, path: str) -> tuple[int, datetime | None]:
        prefix, key = self._split_file_path(path)
        meta = self.storage.get_object_metadata(prefix, key)
        return meta.file_size_bytes, meta.modified_time

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

    # Office-style formats LibreOffice can render to PDF for preview.
    PDF_PREVIEW_EXTENSIONS: frozenset[str] = frozenset({
        ".ppt", ".pptx", ".odp",
        ".doc", ".docx", ".odt", ".rtf",
        ".xls", ".xlsx", ".xlsm", ".xlsb", ".ods",
    })

    def preview_file_as_pdf(self, path: str) -> PdfPreviewData:
        normalized_path = self.normalize_relative_path(path)
        ext = PurePosixPath(normalized_path).suffix.lower()
        if ext not in self.PDF_PREVIEW_EXTENSIONS:
            raise UnsupportedPreviewError(
                "PDF preview is not supported for this file type"
            )
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot preview a directory")

        try:
            content_bytes = self._read_bytes(normalized_path)
        except Exceptions.ObjectNotFound as exc:
            raise NotFoundError("File not found") from exc

        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise PreviewUnavailableError(
                "Office preview is unavailable: LibreOffice is not installed on the API service."
            )

        with tempfile.TemporaryDirectory(prefix="nexus-office-preview-") as tmp_dir:
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

    def stream_folder_archive(self, path: str) -> tuple[str, Iterator[bytes]]:
        normalized_path = self.normalize_relative_path(path, allow_empty=True)
        if not self._is_directory(normalized_path):
            raise NotFoundError("Folder not found")

        files, _dirs = self._collect_directory_tree(normalized_path)
        if len(files) > self.max_archive_files:
            raise ArchiveTooLargeError(
                file_count=len(files), max_files=self.max_archive_files
            )

        folder_name = normalized_path.rsplit("/", 1)[-1] if normalized_path else "files"
        archive_filename = f"{folder_name}.zip"
        root_prefix = f"{normalized_path}/" if normalized_path else ""

        def _iter_archive() -> Iterator[bytes]:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tmp.close()
            tmp_path = Path(tmp.name)
            try:
                with zipfile.ZipFile(
                    tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED
                ) as zip_file:
                    for file_path in files:
                        if root_prefix and file_path.startswith(root_prefix):
                            arcname = file_path[len(root_prefix) :]
                        else:
                            arcname = file_path
                        if not arcname:
                            continue
                        zip_file.writestr(arcname, self._read_bytes(file_path))
                with tmp_path.open("rb") as handle:
                    while chunk := handle.read(self.archive_chunk_size):
                        yield chunk
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        return archive_filename, _iter_archive()

    def extract_archive(self, path: str) -> FileInfoData:
        """Extract a stored archive into a sibling folder next to the archive.

        Destination is named after the archive stem (``foo.zip`` -> ``foo``).
        If that name is taken, uses the UI collision style ``foo-1``, ``foo-2``, ...
        Rejects zip-slip paths, symlinks, and archives that exceed size/count caps.
        On failure after the destination folder was created, deletes that folder.
        """
        normalized_path = self.normalize_relative_path(path)
        if self._is_directory(normalized_path):
            raise IsDirectoryError("Cannot extract a directory")
        if not self._file_exists(normalized_path):
            raise NotFoundError("File not found")

        archive_name = PurePosixPath(normalized_path).name
        fmt = self._detect_archive_format(archive_name)
        if fmt is None:
            raise UnsupportedArchiveError(
                "Unsupported archive type. Supported: .zip, .tar, .tar.gz, .tgz"
            )

        try:
            archive_bytes = self._read_bytes(normalized_path)
        except Exceptions.ObjectNotFound as exc:
            raise NotFoundError("File not found") from exc

        parent = str(PurePosixPath(normalized_path).parent)
        if parent == ".":
            parent = ""
        stem = self._archive_stem(archive_name)
        destination = self._unique_sibling_folder(parent, stem)

        # Validate and materialize members before creating the destination so
        # invalid archives leave no partial folder behind.
        try:
            if fmt == "zip":
                planned = self._plan_zip_extract(archive_bytes, destination)
            else:
                planned = self._plan_tar_extract(archive_bytes, destination)
        except (InvalidArchiveError, ExtractTooLargeError, UnsupportedArchiveError):
            raise
        except Exception as exc:
            raise InvalidArchiveError("Failed to read archive") from exc

        self._create_folder_marker(destination)
        try:
            for kind, target, data in planned:
                if kind == "dir":
                    self._ensure_parent_folders(target, under=destination)
                    if not self._is_directory(target):
                        self._create_folder_marker(target)
                else:
                    self._ensure_parent_folders(target, under=destination)
                    self._write_bytes(target, data)
        except Exception:
            try:
                self.delete_path(destination)
            except Exception:
                pass
            raise

        return FileInfoData(
            name=destination.split("/")[-1],
            path=destination,
            type="folder",
            modified=datetime.now(),
        )

    @classmethod
    def _detect_archive_format(cls, filename: str) -> str | None:
        lower = filename.lower()
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "tar"
        if lower.endswith(".tar"):
            return "tar"
        if lower.endswith(".zip"):
            return "zip"
        return None

    @classmethod
    def _archive_stem(cls, filename: str) -> str:
        lower = filename.lower()
        for suffix in cls._EXTRACTABLE_SUFFIXES:
            if lower.endswith(suffix):
                return filename[: -len(suffix)]
        return PurePosixPath(filename).stem

    def _unique_sibling_folder(self, parent: str, stem: str) -> str:
        safe_stem = PurePosixPath(stem).name.strip() or "archive"
        if safe_stem in (".", "..") or "/" in safe_stem:
            raise InvalidPathError("Invalid archive name")

        def _taken(path: str) -> bool:
            # Directory check first: FS adapter raises IsADirectoryError on get_object.
            return self._is_directory(path) or self._file_exists(path)

        candidate = f"{parent}/{safe_stem}" if parent else safe_stem
        if not _taken(candidate):
            return candidate

        # Match browse UI getUniqueName: base, base-1, base-2, ...
        counter = 1
        while True:
            name = f"{safe_stem}-{counter}"
            candidate = f"{parent}/{name}" if parent else name
            if not _taken(candidate):
                return candidate
            counter += 1

    def _safe_extract_member_path(self, member_name: str, destination: str) -> str | None:
        """Return a storage path under ``destination``, or None to skip.

        Rejects absolute paths, ``..`` segments, empty names, and anything that
        would resolve outside the destination folder (zip-slip).
        """
        raw = (member_name or "").replace("\\", "/").strip()
        if not raw or raw.endswith("/"):
            return None
        if raw.startswith("/") or PurePosixPath(raw).is_absolute():
            raise InvalidArchiveError(f"Archive member has an absolute path: {member_name}")

        parts = [part for part in PurePosixPath(raw).parts if part not in ("", ".")]
        if not parts:
            return None
        if any(part == ".." for part in parts):
            raise InvalidArchiveError(
                f"Archive member escapes destination (path traversal): {member_name}"
            )

        relative = "/".join(parts)
        full = f"{destination}/{relative}"
        dest_prefix = f"{destination}/"
        if full != destination and not full.startswith(dest_prefix):
            raise InvalidArchiveError(
                f"Archive member escapes destination: {member_name}"
            )
        return full

    @staticmethod
    def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            return True
        return False

    def _plan_zip_extract(
        self, archive_bytes: bytes, destination: str
    ) -> list[tuple[str, str, bytes]]:
        try:
            zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
        except zipfile.BadZipFile as exc:
            raise InvalidArchiveError("Invalid or corrupted ZIP archive") from exc

        planned: list[tuple[str, str, bytes]] = []
        file_count = 0
        total_uncompressed = 0
        with zf:
            for info in zf.infolist():
                name = info.filename
                if self._zip_member_is_symlink(info):
                    raise InvalidArchiveError(
                        f"Archive contains a symlink which is not allowed: {name}"
                    )

                if name.endswith("/") or info.is_dir():
                    dir_rel = name.rstrip("/").replace("\\", "/")
                    if dir_rel:
                        dir_full = self._safe_extract_member_path(dir_rel, destination)
                        if dir_full is not None:
                            planned.append(("dir", dir_full, b""))
                    continue

                target = self._safe_extract_member_path(name, destination)
                if target is None:
                    continue

                file_count += 1
                if file_count > self.max_extract_files:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive has too many files "
                            f"(limit {self.max_extract_files})"
                        )
                    )

                size = info.file_size
                if size > self.max_extract_member_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive member is too large: {name} "
                            f"(limit {self.max_extract_member_bytes // (1024 * 1024)}MB)"
                        )
                    )
                total_uncompressed += size
                if total_uncompressed > self.max_extract_uncompressed_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            "Archive uncompressed size exceeds limit "
                            f"({self.max_extract_uncompressed_bytes // (1024 * 1024)}MB)"
                        )
                    )

                try:
                    data = zf.read(info)
                except Exception as exc:
                    raise InvalidArchiveError(
                        f"Failed to read archive member: {name}"
                    ) from exc

                if len(data) > self.max_extract_member_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive member is too large: {name} "
                            f"(limit {self.max_extract_member_bytes // (1024 * 1024)}MB)"
                        )
                    )
                total_uncompressed = total_uncompressed - size + len(data)
                if total_uncompressed > self.max_extract_uncompressed_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            "Archive uncompressed size exceeds limit "
                            f"({self.max_extract_uncompressed_bytes // (1024 * 1024)}MB)"
                        )
                    )

                planned.append(("file", target, data))

        return planned

    def _plan_tar_extract(
        self, archive_bytes: bytes, destination: str
    ) -> list[tuple[str, str, bytes]]:
        try:
            tf = tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*")
        except tarfile.TarError as exc:
            raise InvalidArchiveError("Invalid or corrupted tar archive") from exc

        planned: list[tuple[str, str, bytes]] = []
        file_count = 0
        total_uncompressed = 0
        with tf:
            for member in tf.getmembers():
                name = member.name
                if member.issym() or member.islnk():
                    raise InvalidArchiveError(
                        f"Archive contains a link which is not allowed: {name}"
                    )

                if member.isdir():
                    dir_full = self._safe_extract_member_path(name, destination)
                    if dir_full is not None:
                        planned.append(("dir", dir_full, b""))
                    continue

                if not member.isfile():
                    continue

                target = self._safe_extract_member_path(name, destination)
                if target is None:
                    continue

                file_count += 1
                if file_count > self.max_extract_files:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive has too many files "
                            f"(limit {self.max_extract_files})"
                        )
                    )

                size = member.size
                if size > self.max_extract_member_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive member is too large: {name} "
                            f"(limit {self.max_extract_member_bytes // (1024 * 1024)}MB)"
                        )
                    )
                total_uncompressed += size
                if total_uncompressed > self.max_extract_uncompressed_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            "Archive uncompressed size exceeds limit "
                            f"({self.max_extract_uncompressed_bytes // (1024 * 1024)}MB)"
                        )
                    )

                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                data = extracted.read()
                if len(data) > self.max_extract_member_bytes:
                    raise ExtractTooLargeError(
                        reason=(
                            f"Archive member is too large: {name} "
                            f"(limit {self.max_extract_member_bytes // (1024 * 1024)}MB)"
                        )
                    )

                planned.append(("file", target, data))

        return planned

    def _ensure_parent_folders(self, file_path: str, *, under: str) -> None:
        """Create missing ancestor folders between ``under`` and ``file_path``."""
        parent = str(PurePosixPath(file_path).parent)
        if parent in ("", ".") or parent == under:
            return
        under_prefix = f"{under}/"
        if not parent.startswith(under_prefix):
            return
        relative = parent[len(under_prefix) :]
        current = under
        for part in PurePosixPath(relative).parts:
            current = f"{current}/{part}"
            if not self._is_directory(current):
                self._create_folder_marker(current)

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
        except (NotADirectoryError, OSError):
            # Some adapters (e.g. local filesystem) surface "this is a file,
            # not a directory" as a low-level OSError rather than as
            # ObjectNotFound — treat that as "not a directory" too.
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
