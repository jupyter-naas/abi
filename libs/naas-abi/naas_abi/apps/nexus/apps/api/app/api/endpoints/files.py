"""File management API endpoints backed by ABI ObjectStorageService."""

from datetime import datetime
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])

OBJECT_STORAGE_PREFIX = "nexus/files"
FOLDER_MARKER = ".nexus_folder"
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


# Pydantic models
class FileInfo(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'folder'
    size: int | None = None
    modified: datetime | None = None
    content_type: str | None = None


class FileContent(BaseModel):
    path: str
    content: str
    content_type: str


class CreateFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=10_000_000)  # 10MB max content
    content_type: str = Field(default="text/plain", max_length=100)


class CreateFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class RenameRequest(BaseModel):
    old_path: str = Field(..., min_length=1, max_length=500)
    new_path: str = Field(..., min_length=1, max_length=500)


class FileListResponse(BaseModel):
    files: list[FileInfo]
    path: str


def get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage

    # Fallback for routes called from an app where ABIModule wired state was skipped.
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def normalize_relative_path(path: str, allow_empty: bool = False) -> str:
    raw = (path or "").strip()
    if not raw:
        if allow_empty:
            return ""
        raise HTTPException(status_code=400, detail="Path is required")

    path_obj = PurePosixPath(raw)
    parts = [part for part in path_obj.parts if part not in ("", ".")]

    if any(part == ".." for part in parts):
        raise HTTPException(status_code=400, detail="Invalid path")

    normalized = "/".join(parts).strip("/")
    if not normalized and not allow_empty:
        raise HTTPException(status_code=400, detail="Path is required")
    return normalized


def _directory_prefix(path: str) -> str:
    relative = normalize_relative_path(path, allow_empty=True)
    if relative:
        return f"{OBJECT_STORAGE_PREFIX}/{relative}".strip("/")
    return OBJECT_STORAGE_PREFIX


def _split_file_path(path: str) -> tuple[str, str]:
    relative = normalize_relative_path(path)
    if "/" in relative:
        parent, name = relative.rsplit("/", 1)
        return _directory_prefix(parent), name
    return _directory_prefix(""), relative


def _relative_from_storage_path(full_path: str) -> str:
    normalized = full_path.strip("/")
    if normalized == OBJECT_STORAGE_PREFIX:
        return ""
    prefix = f"{OBJECT_STORAGE_PREFIX}/"
    if normalized.startswith(prefix):
        return normalized[len(prefix) :]
    return normalized


def _file_exists(storage: ObjectStorageService, path: str) -> bool:
    prefix, key = _split_file_path(path)
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def _is_directory(storage: ObjectStorageService, path: str) -> bool:
    try:
        storage.list_objects(_directory_prefix(path))
        return True
    except Exceptions.ObjectNotFound:
        return False


def _list_directory(storage: ObjectStorageService, path: str) -> list[str]:
    prefix = _directory_prefix(path)
    try:
        raw_paths = storage.list_objects(prefix)
    except Exceptions.ObjectNotFound:
        return []

    children: set[str] = set()
    for raw_path in raw_paths:
        relative = _relative_from_storage_path(raw_path)
        if not relative:
            continue
        if relative == FOLDER_MARKER or relative.endswith(f"/{FOLDER_MARKER}"):
            continue
        children.add(relative)
    return sorted(children)


def _read_bytes(storage: ObjectStorageService, path: str) -> bytes:
    prefix, key = _split_file_path(path)
    return storage.get_object(prefix, key)


def _write_bytes(storage: ObjectStorageService, path: str, content: bytes) -> None:
    prefix, key = _split_file_path(path)
    storage.put_object(prefix, key, content)


def _delete_file(storage: ObjectStorageService, path: str) -> None:
    prefix, key = _split_file_path(path)
    storage.delete_object(prefix, key)


def _create_folder_marker(storage: ObjectStorageService, path: str) -> None:
    storage.put_object(_directory_prefix(path), FOLDER_MARKER, b"")


def _delete_folder_marker(storage: ObjectStorageService, path: str) -> None:
    try:
        storage.delete_object(_directory_prefix(path), FOLDER_MARKER)
    except Exceptions.ObjectNotFound:
        pass


def _collect_directory_tree(
    storage: ObjectStorageService, root_path: str
) -> tuple[list[str], list[str]]:
    all_files: list[str] = []
    all_dirs: list[str] = []
    queue = [normalize_relative_path(root_path)]
    seen = set(queue)

    while queue:
        current = queue.pop(0)
        all_dirs.append(current)
        for child in _list_directory(storage, current):
            if _is_directory(storage, child):
                if child not in seen:
                    seen.add(child)
                    queue.append(child)
            else:
                all_files.append(child)

    return all_files, all_dirs


# =============================================================================
# SPECIFIC ROUTES FIRST (before wildcard routes)
# =============================================================================


@router.get("/", response_model=FileListResponse)
async def list_files(request: Request, path: str = Query("", description="Directory path to list")):
    """List files and folders in a directory."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(path, allow_empty=True)
    entries = _list_directory(storage, normalized_path)
    files: list[FileInfo] = []

    for entry in entries:
        name = entry.split("/")[-1]
        if _is_directory(storage, entry):
            files.append(
                FileInfo(
                    name=name,
                    path=entry,
                    type="folder",
                    modified=datetime.now(),
                )
            )
            continue

        size: int | None = None
        content_type: str | None = None
        try:
            content = _read_bytes(storage, entry)
            size = len(content)
            ext = PurePosixPath(entry).suffix.lower()
            content_types = {
                ".py": "text/x-python",
                ".js": "text/javascript",
                ".ts": "text/typescript",
                ".json": "application/json",
                ".md": "text/markdown",
                ".txt": "text/plain",
                ".yaml": "text/yaml",
                ".yml": "text/yaml",
            }
            content_type = content_types.get(ext, "application/octet-stream")
        except Exceptions.ObjectNotFound:
            continue

        files.append(
            FileInfo(
                name=name,
                path=entry,
                type="file",
                size=size,
                modified=datetime.now(),
                content_type=content_type,
            )
        )

    return FileListResponse(files=files, path=normalized_path)


@router.post("/", response_model=FileInfo)
async def create_file(request: Request, payload: CreateFileRequest):
    """Create a new file with optional content."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(payload.path)

    if _is_directory(storage, normalized_path) or _file_exists(storage, normalized_path):
        raise HTTPException(status_code=409, detail="File already exists")

    content = payload.content.encode("utf-8")
    _write_bytes(storage, normalized_path, content)

    return FileInfo(
        name=normalized_path.split("/")[-1],
        path=normalized_path,
        type="file",
        size=len(content),
        modified=datetime.now(),
        content_type=payload.content_type,
    )


@router.post("/folder", response_model=FileInfo)
async def create_folder(request: Request, payload: CreateFolderRequest):
    """Create a new folder."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(payload.path)

    if _is_directory(storage, normalized_path) or _file_exists(storage, normalized_path):
        raise HTTPException(status_code=409, detail="Folder already exists")

    _create_folder_marker(storage, normalized_path)

    return FileInfo(
        name=normalized_path.split("/")[-1],
        path=normalized_path,
        type="folder",
        modified=datetime.now(),
    )


@router.post("/rename", response_model=FileInfo)
async def rename_file(request: Request, payload: RenameRequest):
    """Rename a file or folder."""
    storage = get_object_storage(request)
    old_path = normalize_relative_path(payload.old_path)
    new_path = normalize_relative_path(payload.new_path)

    if old_path == new_path:
        raise HTTPException(status_code=400, detail="old_path and new_path must be different")

    target_exists = _file_exists(storage, new_path) or _is_directory(storage, new_path)
    if target_exists:
        raise HTTPException(status_code=409, detail="Target path already exists")

    if _is_directory(storage, old_path):
        files, dirs = _collect_directory_tree(storage, old_path)
        if not files and not dirs:
            raise HTTPException(status_code=404, detail="File or folder not found")

        old_root = f"{old_path}/"
        for file_path in files:
            relative = file_path[len(old_root) :] if file_path.startswith(old_root) else ""
            destination = f"{new_path}/{relative}" if relative else new_path
            _write_bytes(storage, destination, _read_bytes(storage, file_path))
            _delete_file(storage, file_path)

        for source_dir in dirs:
            relative = source_dir[len(old_root) :] if source_dir.startswith(old_root) else ""
            destination_dir = f"{new_path}/{relative}" if relative else new_path
            _create_folder_marker(storage, destination_dir)

        for source_dir in reversed(dirs):
            _delete_folder_marker(storage, source_dir)

        return FileInfo(
            name=new_path.split("/")[-1],
            path=new_path,
            type="folder",
            modified=datetime.now(),
        )

    if not _file_exists(storage, old_path):
        raise HTTPException(status_code=404, detail="File or folder not found")

    content = _read_bytes(storage, old_path)
    _write_bytes(storage, new_path, content)
    _delete_file(storage, old_path)
    return FileInfo(
        name=new_path.split("/")[-1],
        path=new_path,
        type="file",
        size=len(content),
        modified=datetime.now(),
    )


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    path: str = Form("", max_length=500),
):
    """Upload a file (max 50MB)."""
    storage = get_object_storage(request)
    filename = PurePosixPath(file.filename or "untitled").name
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid file name")

    base_path = normalize_relative_path(path, allow_empty=True)
    full_path = f"{base_path}/{filename}" if base_path else filename
    normalized_path = normalize_relative_path(full_path)

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    _write_bytes(storage, normalized_path, content)

    return FileInfo(
        name=filename,
        path=normalized_path,
        type="file",
        size=len(content),
        modified=datetime.now(),
        content_type=file.content_type or "application/octet-stream",
    )


# =============================================================================
# WILDCARD ROUTES LAST (catch-all patterns)
# =============================================================================


@router.get("/{path:path}", response_model=FileContent)
async def read_file(request: Request, path: str):
    """Read file content."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(path)

    if _is_directory(storage, normalized_path):
        raise HTTPException(status_code=400, detail="Cannot read a directory")

    try:
        content_bytes = _read_bytes(storage, normalized_path)
    except Exceptions.ObjectNotFound as e:
        raise HTTPException(status_code=404, detail="File not found") from e

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail="File is not text") from e

    ext = PurePosixPath(normalized_path).suffix.lower()
    content_types = {
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
    }
    content_type = content_types.get(ext, "text/plain")

    return FileContent(path=normalized_path, content=content, content_type=content_type)


@router.put("/{path:path}", response_model=FileInfo)
async def update_file(request: Request, path: str, payload: CreateFileRequest):
    """Update file content."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(path)
    if _is_directory(storage, normalized_path):
        raise HTTPException(status_code=400, detail="Cannot update a directory")
    if not _file_exists(storage, normalized_path):
        raise HTTPException(status_code=404, detail="File not found")

    content = payload.content.encode("utf-8")
    _write_bytes(storage, normalized_path, content)

    return FileInfo(
        name=normalized_path.split("/")[-1],
        path=normalized_path,
        type="file",
        size=len(content),
        modified=datetime.now(),
        content_type=payload.content_type,
    )


@router.delete("/{path:path}")
async def delete_file(request: Request, path: str):
    """Delete a file or folder."""
    storage = get_object_storage(request)
    normalized_path = normalize_relative_path(path)

    if _is_directory(storage, normalized_path):
        files, dirs = _collect_directory_tree(storage, normalized_path)
        for file_path in files:
            _delete_file(storage, file_path)
        for directory in reversed(dirs):
            _delete_folder_marker(storage, directory)
        return {"message": "Folder deleted", "path": normalized_path}

    if not _file_exists(storage, normalized_path):
        raise HTTPException(status_code=404, detail="File or folder not found")

    _delete_file(storage, normalized_path)
    return {"message": "File deleted", "path": normalized_path}
