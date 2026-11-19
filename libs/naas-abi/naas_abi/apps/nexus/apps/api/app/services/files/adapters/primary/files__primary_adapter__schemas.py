from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import SCOPE_PATTERN
from pydantic import BaseModel, Field

FileScope = str


class FileInfo(BaseModel):
    name: str
    path: str
    type: str
    size: int | None = None
    modified: datetime | None = None
    content_type: str | None = None


class FileContent(BaseModel):
    path: str
    content: str
    content_type: str


class CreateFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)
    scope: str = Field(default="workspace", pattern=SCOPE_PATTERN)
    content: str = Field(default="", max_length=10_000_000)
    content_type: str = Field(default="text/plain", max_length=100)


class CreateFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)
    scope: str = Field(default="workspace", pattern=SCOPE_PATTERN)


class RenameRequest(BaseModel):
    old_path: str = Field(..., min_length=1, max_length=500)
    new_path: str = Field(..., min_length=1, max_length=500)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)
    scope: str = Field(default="workspace", pattern=SCOPE_PATTERN)


class FileListResponse(BaseModel):
    files: list[FileInfo]
    path: str
    # Total entries in the directory before limit/offset paging.
    total: int = 0


class FileView(BaseModel):
    """A view of a drive: a starting folder the caller may open (``GET /api/files/views``)."""

    # ``my_files``, ``workspace_files``, ``organization_files``, ``platform_files``,
    # ``system_files``.
    id: str
    label: str
    # The drive it is a view of: ``file_system`` (the object storage), the only one today.
    drive: str
    # The ``scope`` the files routes take for it.
    scope: str
    # Its folder in the drive: a storage path, "" for the whole store (System Files).
    root: str


class FileViewsResponse(BaseModel):
    views: list[FileView]
