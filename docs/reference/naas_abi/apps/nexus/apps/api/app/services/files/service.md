# `FilesService`

## What it is
A service layer for basic file/folder operations backed by an `ObjectStorageService`. It normalizes POSIX-style relative paths, stores “folders” via a marker object, supports text and raw reads, and can generate PDF previews for PPT/PPTX using LibreOffice.

## Public API
- `class FilesService(storage: ObjectStorageService)`
  - Wraps an object storage backend to provide file-like operations.

### Class attributes
- `object_storage_prefix: str = ""`  
  Storage prefix prepended to all operations.
- `folder_marker: str = ".nexus_folder"`  
  Marker object name used to represent folders.
- `max_upload_size: int = 50 * 1024 * 1024`  
  Maximum upload size in bytes (50MB).

### Methods
- `normalize_relative_path(path: str, allow_empty: bool = False) -> str` (static)
  - Normalize a user-provided POSIX path:
    - Strips whitespace, removes `.` segments, forbids `..`, strips leading/trailing `/`.
    - If empty and `allow_empty=False`, raises `InvalidPathError`.

- `list_files(path: str = "") -> FileListResponseData`
  - List direct children under `path`.
  - Returns `FileListResponseData(files=[...], path=normalized_path)`.
  - Uses `datetime.now()` for `modified` metadata.

- `create_file(path: str, content: str = "", content_type: str = "text/plain") -> FileInfoData`
  - Create a new file with UTF-8 encoded `content`.
  - Raises `AlreadyExistsError` if target exists as file or folder.

- `create_folder(path: str) -> FileInfoData`
  - Create a folder by writing a marker object (`.nexus_folder`).
  - Raises `AlreadyExistsError` if target exists as file or folder.

- `rename(old_path: str, new_path: str) -> FileInfoData`
  - Rename/move a file or folder.
  - For folders, copies all files to the new prefix, creates folder markers for directories, then removes old files and markers.
  - Errors:
    - `InvalidPathError` if paths are equal.
    - `AlreadyExistsError` if target exists.
    - `NotFoundError` if source not found.

- `upload_file(filename: str, path: str, content: bytes, content_type: str | None) -> FileInfoData`
  - Upload bytes to `path/filename` (filename is sanitized to basename).
  - Raises:
    - `InvalidPathError` if filename invalid.
    - `UploadTooLargeError` if `len(content) > max_upload_size`.

- `preview_file_as_pdf(path: str) -> PdfPreviewData`
  - Convert `.ppt`/`.pptx` to PDF using `soffice`/`libreoffice` in headless mode.
  - Raises:
    - `UnsupportedPreviewError` for non-PPT/PPTX.
    - `IsDirectoryError` if path is a directory.
    - `NotFoundError` if object not found.
    - `PreviewUnavailableError` if LibreOffice binary not present.
    - `PreviewConversionError` on conversion failure (non-zero exit or missing output).
  - Uses a temporary directory and a 60s subprocess timeout.

- `read_file_raw(path: str) -> RawFileData`
  - Read bytes and return `RawFileData(content, media_type, filename)`.
  - Raises `IsDirectoryError`, `NotFoundError`.

- `read_file(path: str) -> FileContentData`
  - Read a UTF-8 text file and return `FileContentData(path, content, content_type)`.
  - Raises:
    - `IsDirectoryError`, `NotFoundError`
    - `NotTextError` if UTF-8 decoding fails.

- `update_file(path: str, content: str, content_type: str) -> FileInfoData`
  - Overwrite an existing file with UTF-8 encoded `content`.
  - Raises `IsDirectoryError` or `NotFoundError`.

- `delete_path(path: str) -> dict[str, str]`
  - Delete a file or recursively delete a folder (files + folder markers).
  - Returns `{"message": "...", "path": normalized_path}`.
  - Raises `NotFoundError` when deleting a non-existent file (folders missing in storage are treated as not-a-directory by `_is_directory`).

## Configuration/Dependencies
- Depends on:
  - `ObjectStorageService` for `get_object`, `put_object`, `delete_object`, `list_objects`.
  - Object storage exceptions: `naas_abi_core.services.object_storage.ObjectStoragePort.Exceptions.ObjectNotFound`.
- Optional system dependency for previews:
  - `soffice` or `libreoffice` executable available on `PATH`.
- Uses folder markers:
  - A folder exists if `list_objects(prefix)` does not raise `ObjectNotFound`.
  - `create_folder()` writes an empty object named `.nexus_folder` under the folder prefix.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

storage = ObjectStorageService(...)  # backend-specific initialization
svc = FilesService(storage)

svc.create_folder("docs")
svc.create_file("docs/readme.md", content="# Hello\n", content_type="text/markdown")

listing = svc.list_files("docs")
text = svc.read_file("docs/readme.md").content

svc.update_file("docs/readme.md", content="# Updated\n", content_type="text/markdown")
svc.rename("docs/readme.md", "docs/README.md")

raw = svc.read_file_raw("docs/README.md")
svc.delete_path("docs/README.md")
```

## Caveats
- Paths are POSIX-only and must be relative; `..` is rejected.
- Folder semantics depend on object storage behavior:
  - `_is_directory()` treats any successful `list_objects(prefix)` as “directory exists”.
  - Empty directories are represented via the `.nexus_folder` marker.
- File/folder metadata:
  - `modified` is set to `datetime.now()` at request time (not storage timestamps).
  - `list_files()` may read full file contents to compute `size`.
- Text reads/writes:
  - `read_file()` assumes UTF-8; non-UTF8 content raises `NotTextError`.
- PPT/PPTX preview:
  - Requires LibreOffice and runs an external subprocess (60s timeout).
