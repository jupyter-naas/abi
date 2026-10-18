# files__primary_adapter__schemas

## What it is
Pydantic schemas (request/response and data models) for a file-management API. They define validated payloads for listing files, reading content, creating files/folders, and renaming.

## Public API
- **Type alias**
  - `FileScope = str`  
    Simple alias for representing a file scope (validated in request models via regex).

- **Models**
  - `FileInfo`
    - Purpose: metadata about a file/folder entry.
    - Fields:
      - `name: str`
      - `path: str`
      - `type: str`
      - `size: int | None = None`
      - `modified: datetime | None = None`
      - `content_type: str | None = None`

  - `FileContent`
    - Purpose: represents a file’s content plus its MIME type.
    - Fields:
      - `path: str`
      - `content: str`
      - `content_type: str`

  - `CreateFileRequest`
    - Purpose: request payload for creating/updating a file.
    - Fields/validation:
      - `path: str` (required, `min_length=1`, `max_length=500`)
      - `workspace_id: str | None` (optional, `min_length=1`, `max_length=100`)
      - `scope: str` (default `"workspace"`, must match `^(workspace|my_drive)$`)
      - `content: str` (default `""`, `max_length=10_000_000`)
      - `content_type: str` (default `"text/plain"`, `max_length=100`)

  - `CreateFolderRequest`
    - Purpose: request payload for creating a folder.
    - Fields/validation:
      - `path: str` (required, `min_length=1`, `max_length=500`)
      - `workspace_id: str | None` (optional, `min_length=1`, `max_length=100`)
      - `scope: str` (default `"workspace"`, must match `^(workspace|my_drive)$`)

  - `RenameRequest`
    - Purpose: request payload for renaming/moving a path.
    - Fields/validation:
      - `old_path: str` (required, `min_length=1`, `max_length=500`)
      - `new_path: str` (required, `min_length=1`, `max_length=500`)
      - `workspace_id: str | None` (optional, `min_length=1`, `max_length=100`)
      - `scope: str` (default `"workspace"`, must match `^(workspace|my_drive)$`)

  - `FileListResponse`
    - Purpose: response payload for listing directory entries.
    - Fields:
      - `files: list[FileInfo]`
      - `path: str`

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field` for validation/serialization.
  - `datetime.datetime` for `modified` timestamps.

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__schemas import (
    CreateFileRequest, FileInfo, FileListResponse
)

# Validate an incoming "create file" payload
req = CreateFileRequest(path="docs/readme.txt", content="Hello", scope="workspace")
print(req.model_dump())

# Build a response for a "list files" endpoint
resp = FileListResponse(
    path="docs/",
    files=[
        FileInfo(
            name="readme.txt",
            path="docs/readme.txt",
            type="file",
            size=5,
            modified=datetime.utcnow(),
            content_type="text/plain",
        )
    ],
)
print(resp.model_dump())
```

## Caveats
- `scope` is constrained to `"workspace"` or `"my_drive"` via regex; other values will fail validation.
- `content` is limited to `10_000_000` characters and `content_type` to 100 characters.
- `workspace_id` is optional but, when provided, must be 1–100 characters.
