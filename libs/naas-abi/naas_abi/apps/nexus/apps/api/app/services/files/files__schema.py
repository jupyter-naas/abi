from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class FilesDomainError(Exception):
    pass


class InvalidPathError(FilesDomainError):
    pass


class AlreadyExistsError(FilesDomainError):
    pass


class NotFoundError(FilesDomainError):
    pass


class IsDirectoryError(FilesDomainError):
    pass


class NotTextError(FilesDomainError):
    pass


class UnsupportedPreviewError(FilesDomainError):
    pass


class PreviewUnavailableError(FilesDomainError):
    pass


class PreviewConversionError(FilesDomainError):
    pass


class UploadTooLargeError(FilesDomainError):
    def __init__(self, max_size_bytes: int):
        self.max_size_bytes = max_size_bytes
        super().__init__(f"File too large. Max size is {max_size_bytes // (1024 * 1024)}MB")


@dataclass(frozen=True)
class FileInfoData:
    name: str
    path: str
    type: str
    size: int | None = None
    modified: datetime | None = None
    content_type: str | None = None


@dataclass(frozen=True)
class FileContentData:
    path: str
    content: str
    content_type: str


@dataclass(frozen=True)
class FileListResponseData:
    files: list[FileInfoData]
    path: str


@dataclass(frozen=True)
class RawFileData:
    content: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class PdfPreviewData:
    content: bytes
    filename: str
