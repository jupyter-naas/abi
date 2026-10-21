# FilesFastAPIPrimaryAdapter

## What it is
- A FastAPI *primary adapter* that exposes a file-management HTTP API via an `APIRouter`.
- Supports multiple storage scopes:
  - `workspace` (default)
  - `my_drive`
  - `platform_drive`
  - `system_drive`
- Handles:
  - Path normalization and scoping under the appropriate drive root
  - AuthN (router-level `get_current_user_required`)
  - AuthZ checks for workspace and special drives
  - Legacy storage migration triggers for workspace and my-drive operations (when a `FilesService` is provided)

## Public API

### Class
- `FilesFastAPIPrimaryAdapter`
  - `__init__(self)`: exposes the module-level `router` as `self.router`.

### Module-level router
- `router: fastapi.APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]` (all routes require authentication).

### HTTP endpoints (registered on `router`)
- `GET /` → `list_files(...) -> FileListResponse`
  - Lists directory contents with optional paging, search, and sorting.
- `POST /` → `create_file(payload: CreateFileRequest) -> FileInfo`
  - Creates a file at `payload.path` with provided content and content type.
- `POST /folder` → `create_folder(payload: CreateFolderRequest) -> FileInfo`
  - Creates a folder at `payload.path`.
- `POST /rename` → `rename_file(payload: RenameRequest) -> FileInfo`
  - Renames/moves a path.
  - For `scope="workspace"`, rejects moves across different workspaces.
- `POST /upload` → `upload_file(file, path, workspace_id, scope) -> FileInfo`
  - Uploads a file using multipart form-data.
- `GET /preview/pdf/{path}` → `preview_file_as_pdf(...) -> fastapi.Response`
  - Returns an inline PDF preview (`media_type="application/pdf"`).
- `GET /archive/{path}` → `download_folder_archive(...) -> StreamingResponse`
  - Streams a ZIP archive of a folder (`media_type="application/zip"`) as an attachment.
- `POST /extract/{path}` → `extract_archive(...) -> FileInfo`
  - Extracts an archive at the given path.
- `GET /raw/{path}` → `read_file_raw(...) -> fastapi.Response`
  - Returns raw file bytes with service-provided media type and inline disposition.
- `GET /{path}` → `read_file(...) -> FileContent`
  - Returns structured file content (as defined by `FileContent` schema).
- `PUT /{path}` → `update_file(path, payload, workspace_id, scope) -> FileInfo`
  - Updates file content and content type.
  - Workspace id comes from query `workspace_id` or `payload.workspace_id`.
- `DELETE /{path}` → `delete_file(...)`
  - Deletes a file/folder path via the service.

### Internal helpers (module-private)
- Schema conversion:
  - `_to_file_info_schema(FileInfoData) -> FileInfo`
  - `_to_file_content_schema(FileContentData) -> FileContent`
  - `_to_file_list_response_schema(FileListResponseData) -> FileListResponse`
- Normalization and scoping:
  - `_normalize_workspace_id(str) -> str` (rejects multi-segment ids)
  - `_normalize_user_id(str) -> str` (rejects multi-segment ids)
  - `_scope_to_path(root: str, path: str) -> str`
  - `_resolve_workspace_scoped_path(path, workspace_id) -> (workspace_id, resolved_path)`
  - `_resolve_my_drive_scoped_path(path, user_id) -> resolved_path`
  - `_resolve_platform_drive_scoped_path(path) -> resolved_path`
  - `_resolve_system_drive_scoped_path(path) -> resolved_path`
- Authorization + optional migration:
  - `_authorize_workspace_path(...) -> resolved_path` (checks `require_workspace_access`; may migrate workspace drive)
  - `_authorize_my_drive_path(...) -> resolved_path` (may migrate my-drive)
  - `_authorize_platform_drive_path(...) -> resolved_path` (checks `require_workspace_platform_drive`)
  - `_authorize_system_drive_path(...) -> resolved_path` (checks `require_workspace_system_drive`)
  - `_authorize_path(...) -> resolved_path` (dispatches based on scope)

## Configuration/Dependencies
- **FastAPI**
  - `APIRouter`, `Depends`, `Query`, `Form`, `File`, `UploadFile`, `Response`, `HTTPException`, `status`
  - `StreamingResponse` for archive streaming
- **Auth**
  - `get_current_user_required` (router dependency and injected per handler)
  - `require_workspace_access(user_id, workspace_id)`
  - `require_workspace_platform_drive(user_id, workspace_id)`
  - `require_workspace_system_drive(user_id, workspace_id)`
  - `User` type must provide `id`
- **Files service**
  - `get_files_service` provides `FilesService`
  - `FilesService` methods used:
    - `normalize_relative_path(...)` (also used by adapter helpers)
    - `list_files`, `create_file`, `create_folder`, `rename`, `upload_file`
    - `preview_file_as_pdf`, `stream_folder_archive`, `extract_archive`
    - `read_file_raw`, `read_file`, `update_file`, `delete_path`
- **Drive roots / scopes**
  - Constants and helpers: `WORKSPACE_DRIVE_ROOT`, `PLATFORM_DRIVE_ROOT`, `SYSTEM_DRIVE_ROOT`
  - Scopes: `SCOPE_MY_DRIVE`, `SCOPE_PLATFORM_DRIVE`, `SCOPE_SYSTEM_DRIVE`, plus `SCOPE_PATTERN`
  - Root builders: `my_drive_root(user_id)`, `workspace_drive_root(workspace_id)`
- **Migration**
  - `LegacyStorageMigrator(files_service)`:
    - `ensure_workspace_drive_migrated(workspace_id)`
    - `ensure_my_drive_migrated(user_id)`
- **Schemas**
  - Requests: `CreateFileRequest`, `CreateFolderRequest`, `RenameRequest`
  - Responses: `FileInfo`, `FileContent`, `FileListResponse`
- **Headers**
  - `content_disposition(kind, filename)` used for inline/attachment responses.

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI import (
    FilesFastAPIPrimaryAdapter,
)

app = FastAPI()
adapter = FilesFastAPIPrimaryAdapter()

app.include_router(adapter.router, prefix="/files", tags=["files"])
```

## Caveats
- `scope` is validated by `SCOPE_PATTERN` on query-based endpoints; `/upload` accepts `scope` as a plain form field (no pattern constraint in this module).
- Workspace and user ids are normalized and must be **single path segments** (no `/`), otherwise `400`.
- For `scope="workspace"`:
  - If `path` is empty, `workspace_id` is required (`400`).
  - `POST /rename` blocks moves across workspaces by comparing workspace segments extracted from resolved storage paths.
- For `scope="platform_drive"` and `scope="system_drive"`:
  - `workspace_id` is required (`400`) and additional authorization is enforced via drive-specific checks.
- Path handling accepts:
  - relative paths (e.g. `docs/readme.md`)
  - legacy workspace-prefixed paths (e.g. `<ws>/docs/readme.md`)
  - full storage paths already under drive roots; the resolver avoids double-prefixing and rejects mismatched workspace paths.
