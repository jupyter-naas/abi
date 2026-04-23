# FilesFastAPIPrimaryAdapter

## What it is
- A FastAPI *primary adapter* exposing a file-management HTTP API.
- Provides an `APIRouter` with endpoints to list, create, upload, read, rename, preview, update, and delete files/folders.
- Enforces authentication and (for workspace scope) workspace access checks, and normalizes/rewrites paths for workspace and “my drive” scopes.

## Public API

### Class
- `FilesFastAPIPrimaryAdapter`
  - `__init__()`: assigns the module-level FastAPI `router` to `self.router`.

### FastAPI router
Module-level:
- `router: APIRouter` (configured with `Depends(get_current_user_required)` for all routes)

Endpoints (registered on `router`):
- `GET /`
  - `list_files(path="", workspace_id=None, scope="workspace") -> FileListResponse`
  - Lists directory contents for a scoped path.
- `POST /`
  - `create_file(payload: CreateFileRequest) -> FileInfo`
  - Creates a file with provided content/content_type.
- `POST /folder`
  - `create_folder(payload: CreateFolderRequest) -> FileInfo`
  - Creates a folder at the scoped path.
- `POST /rename`
  - `rename_file(payload: RenameRequest) -> FileInfo`
  - Renames/moves a path; blocks cross-workspace moves when `scope="workspace"`.
- `POST /upload`
  - `upload_file(file, path="", workspace_id=None, scope="workspace") -> FileInfo`
  - Uploads a file (multipart form), reads bytes from `UploadFile`, stores via service.
- `GET /preview/pdf/{path}`
  - `preview_file_as_pdf(path, workspace_id=None, scope="workspace") -> Response`
  - Returns an inline PDF preview response (`media_type="application/pdf"`).
- `GET /raw/{path}`
  - `read_file_raw(path, workspace_id=None, scope="workspace") -> Response`
  - Returns raw bytes with `media_type` from the service and inline disposition.
- `GET /{path}`
  - `read_file(path, workspace_id=None, scope="workspace") -> FileContent`
  - Reads a file and returns structured content.
- `PUT /{path}`
  - `update_file(path, payload: CreateFileRequest, workspace_id=None, scope="workspace") -> FileInfo`
  - Updates file content/content_type; workspace id is taken from query or payload.
- `DELETE /{path}`
  - `delete_file(path, workspace_id=None, scope="workspace")`
  - Deletes a file/folder path via the service.

### Internal helpers (not part of HTTP surface but used within module)
- `_to_file_info_schema(FileInfoData) -> FileInfo`
- `_to_file_content_schema(FileContentData) -> FileContent`
- `_to_file_list_response_schema(FileListResponseData) -> FileListResponse`
- `_normalize_workspace_id(str) -> str`: normalizes and rejects multi-segment ids.
- `_normalize_user_id(str) -> str`: normalizes and rejects multi-segment ids.
- `_resolve_workspace_scoped_path(path, workspace_id) -> (workspace_id, resolved_path)`
- `_resolve_my_drive_scoped_path(path, user_id) -> resolved_path`
- `_authorize_workspace_path(current_user, path, workspace_id) -> resolved_path`
- `_authorize_path(current_user, path, workspace_id, scope) -> resolved_path`

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Depends`, `Query`, `Form`, `File`, `UploadFile`, `Response`, `HTTPException`.
- **Auth dependencies**:
  - `get_current_user_required`: required on all routes (router-level dependency and per-endpoint injection).
  - `require_workspace_access(user_id, workspace_id)`: enforced for `scope="workspace"`.
  - `User`: current user type (must provide `id`).
- **Service dependency**:
  - `get_files_service`: provides `FilesService`.
  - `FilesService` methods used:
    - `normalize_relative_path(...)` (also used by adapter helpers)
    - `list_files`, `create_file`, `create_folder`, `rename`, `upload_file`
    - `preview_file_as_pdf`, `read_file_raw`, `read_file`, `update_file`, `delete_path`
- **Schemas** (request/response models):
  - Requests: `CreateFileRequest`, `CreateFolderRequest`, `RenameRequest`
  - Responses: `FileInfo`, `FileContent`, `FileListResponse`

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI import (
    FilesFastAPIPrimaryAdapter,
)

app = FastAPI()
adapter = FilesFastAPIPrimaryAdapter()

# Choose an appropriate prefix for your API
app.include_router(adapter.router, prefix="/files", tags=["files"])
```

## Caveats
- `scope` is restricted to `workspace` or `my_drive` (validated by query/form patterns on most endpoints).
- For `scope="workspace"`:
  - Workspace access is enforced via `require_workspace_access`.
  - `workspace_id` must be a **single path segment** (no `/`), otherwise `400`.
  - If `path` is empty, `workspace_id` is required (`400`).
  - `POST /rename` rejects moves across workspaces (`400`).
- For `scope="my_drive"`:
  - Paths are rewritten under `my-drive/{current_user.id}`.
- Paths and ids are normalized using `FilesService.normalize_relative_path`; invalid normalization outcomes can trigger `400` errors as implemented by the adapter.
