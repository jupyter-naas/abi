from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import SCOPE_PATTERN
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
