# files (File management API endpoints)

## What it is
FastAPI endpoints for basic file/folder operations backed by `naas_abi_core.services.object_storage.ObjectStorageService`, scoped under the object storage prefix `nexus/files`. All routes require an authenticated user via `get_current_user_required`.

## Public API

### FastAPI router
- `router: APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]`.

### Pydantic models (request/response)
- `FileInfo`
  - Metadata for a file/folder: `name`, `path`, `type` (`"file"`/`"folder"`), optional `size`, `modified`, `content_type`.
- `FileContent`
  - Text file content response: `path`, `content` (UTF-8 string), `content_type`.
- `CreateFileRequest`
  - Create/update payload: `path`, `content` (≤ 10,000,000 chars), `content_type`.
- `CreateFolderRequest`
  - Create folder payload: `path`.
- `RenameRequest`
  - Rename payload: `old_path`, `new_path`.
- `FileListResponse`
  - Directory listing response: `files: list[FileInfo]`, `path`.

### Endpoints
- `GET /`
  - `list_files(request, path="") -> FileListResponse`
  - Lists children under a directory path.
- `POST /`
  - `create_file(request, payload: CreateFileRequest) -> FileInfo`
  - Creates a new file; fails if file/folder already exists at that path.
- `POST /folder`
  - `create_folder(request, payload: CreateFolderRequest) -> FileInfo`
  - Creates a folder (implemented by writing a folder marker object).
- `POST /rename`
  - `rename_file(request, payload: RenameRequest) -> FileInfo`
  - Renames a file or folder. For folders, copies all contained files/markers then deletes originals.
- `POST /upload`
  - `upload_file(request, file: UploadFile, path: str="") -> FileInfo`
  - Uploads a file (max 50MB) into an optional directory `path`.
- `GET /{path:path}`
  - `read_file(request, path) -> FileContent`
  - Reads a file as UTF-8 text; fails on directories or non-text data.
- `PUT /{path:path}`
  - `update_file(request, path, payload: CreateFileRequest) -> FileInfo`
  - Updates an existing file with new UTF-8 content.
- `DELETE /{path:path}`
  - `delete_file(request, path) -> dict`
  - Deletes a file or recursively deletes a folder (files then folder markers).

### Helper functions (module-level)
- `get_object_storage(request: Request) -> ObjectStorageService`
  - Resolves storage from `request.app.state.object_storage`, otherwise falls back to `naas_abi.ABIModule.get_instance().engine.services.object_storage`.
- `normalize_relative_path(path: str, allow_empty: bool=False) -> str`
  - Normalizes a POSIX-like relative path; rejects `..`; trims leading/trailing slashes.
  - Used to prevent path traversal.
- Internal helpers (prefixed `_`) manage storage paths, folder markers, listing, and recursive directory traversal.

## Configuration/Dependencies
- **Authentication**: all routes depend on `get_current_user_required`.
- **Object storage**: expects `request.app.state.object_storage` to be set to an `ObjectStorageService`.
  - If missing, attempts a runtime fallback via `naas_abi.ABIModule`.
- **Constants**
  - `OBJECT_STORAGE_PREFIX = "nexus/files"`: storage prefix for all objects.
  - `FOLDER_MARKER = ".nexus_folder"`: zero-byte object used to represent folders.
  - `MAX_UPLOAD_SIZE = 50 * 1024 * 1024`: upload limit (50MB).

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.files import router as files_router

app = FastAPI()
app.include_router(files_router, prefix="/files", tags=["files"])
```

### Example HTTP calls (illustrative)
- `GET /files?path=projects`
- `POST /files` with JSON `{"path":"projects/readme.md","content":"Hello","content_type":"text/markdown"}`
- `POST /files/folder` with JSON `{"path":"projects"}`
- `GET /files/projects/readme.md`
- `PUT /files/projects/readme.md` with JSON `{"path":"ignored-by-put","content":"Updated","content_type":"text/plain"}`
- `DELETE /files/projects/readme.md`
- `POST /files/upload` as multipart form: `file=@local.bin`, `path=projects/assets`

## Caveats
- Paths are **relative-only**; any segment equal to `..` is rejected with HTTP 400.
- Folder existence is inferred via storage listing and a `.nexus_folder` marker; folder operations depend on that convention.
- `read_file` only supports UTF-8 decodable content; binary files return HTTP 400 (`"File is not text"`).
- `upload_file` enforces a hard 50MB limit; oversize uploads return HTTP 413.
- `list_files` and returned `modified` timestamps use `datetime.now()` (not storage metadata).
