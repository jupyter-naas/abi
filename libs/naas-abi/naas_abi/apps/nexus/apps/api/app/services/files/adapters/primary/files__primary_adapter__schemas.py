from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
    content: str = Field(default="", max_length=10_000_000)
    content_type: str = Field(default="text/plain", max_length=100)


class CreateFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)


class RenameRequest(BaseModel):
    old_path: str = Field(..., min_length=1, max_length=500)
    new_path: str = Field(..., min_length=1, max_length=500)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)


class FileListResponse(BaseModel):
    files: list[FileInfo]
    path: str
