"""Files FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi import File as FastAPIFile
from fastapi import UploadFile as FastAPIUploadFile
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
    require_workspace_platform_drive,
    require_workspace_system_drive,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__schemas import (  # noqa: E501
    CreateFileRequest,
    CreateFolderRequest,
    FileContent,
    FileInfo,
    FileListResponse,
    RenameRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import (
    PLATFORM_DRIVE_ROOT,
    SCOPE_MY_DRIVE,
    SCOPE_PATTERN,
    SCOPE_PLATFORM_DRIVE,
    SCOPE_SYSTEM_DRIVE,
    SYSTEM_DRIVE_ROOT,
    my_drive_root,
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    FileContentData,
    FileInfoData,
    FileListResponseData,
)
from naas_abi.apps.nexus.apps.api.app.services.files.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class FilesFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def _to_file_info_schema(value: FileInfoData) -> FileInfo:
    return FileInfo(
        name=value.name,
        path=value.path,
        type=value.type,
        size=value.size,
        modified=value.modified,
        content_type=value.content_type,
    )


def _to_file_content_schema(value: FileContentData) -> FileContent:
    return FileContent(
        path=value.path,
        content=value.content,
        content_type=value.content_type,
    )


def _to_file_list_response_schema(value: FileListResponseData) -> FileListResponse:
    return FileListResponse(
        files=[_to_file_info_schema(file) for file in value.files],
        path=value.path,
        total=value.total,
    )


def _normalize_workspace_id(workspace_id: str) -> str:
    normalized = FilesService.normalize_relative_path(workspace_id)
    if "/" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id must be a single path segment",
        )
    return normalized


def _normalize_user_id(user_id: str) -> str:
    normalized = FilesService.normalize_relative_path(user_id)
    if "/" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must be a single path segment",
        )
    return normalized


def _scope_to_path(root: str, path: str) -> str:
    """Anchor ``path`` under ``root`` regardless of whether the caller already
    prefixed it. Accepts an empty path (returns the root itself). An empty
    ``root`` means "no prefix" — paths are returned as-is, resolving against
    the underlying object-storage root."""
    normalized_path = FilesService.normalize_relative_path(path, allow_empty=True)
    if not root:
        return normalized_path
    if not normalized_path:
        return root
    if normalized_path == root or normalized_path.startswith(f"{root}/"):
        return normalized_path
    return f"{root}/{normalized_path}"


def _resolve_workspace_scoped_path(path: str, workspace_id: str | None) -> tuple[str, str]:
    normalized_path = FilesService.normalize_relative_path(path, allow_empty=True)
    normalized_workspace = _normalize_workspace_id(workspace_id) if workspace_id else None

    if not normalized_workspace:
        if not normalized_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workspace_id is required when path is empty",
            )
        normalized_workspace = normalized_path.split("/", 1)[0]
        # Allow callers that still pass the legacy bare-workspace path layout.
        body = normalized_path.split("/", 1)[1] if "/" in normalized_path else ""
    else:
        # Strip a redundant leading workspace segment from the request path if present
        if normalized_path == normalized_workspace:
            body = ""
        elif normalized_path.startswith(f"{normalized_workspace}/"):
            body = normalized_path[len(normalized_workspace) + 1 :]
        else:
            body = normalized_path

    root = workspace_drive_root(normalized_workspace)
    scoped = root if not body else f"{root}/{body}"
    return normalized_workspace, scoped


def _resolve_my_drive_scoped_path(path: str, user_id: str) -> str:
    normalized_user = _normalize_user_id(user_id)
    return _scope_to_path(my_drive_root(normalized_user), path)


def _resolve_platform_drive_scoped_path(path: str) -> str:
    return _scope_to_path(PLATFORM_DRIVE_ROOT, path)


def _resolve_system_drive_scoped_path(path: str) -> str:
    return _scope_to_path(SYSTEM_DRIVE_ROOT, path)


async def _authorize_workspace_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    files_service: FilesService | None = None,
) -> str:
    resolved_workspace_id, resolved_path = _resolve_workspace_scoped_path(path, workspace_id)
    await require_workspace_access(current_user.id, resolved_workspace_id)
    if files_service is not None:
        LegacyStorageMigrator(files_service).ensure_workspace_drive_migrated(
            resolved_workspace_id
        )
    return resolved_path


def _authorize_my_drive_path(
    current_user: User,
    path: str,
    files_service: FilesService | None = None,
) -> str:
    resolved = _resolve_my_drive_scoped_path(path=path, user_id=current_user.id)
    if files_service is not None:
        LegacyStorageMigrator(files_service).ensure_my_drive_migrated(current_user.id)
    return resolved


async def _authorize_platform_drive_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
) -> str:
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required for platform drive access",
        )
    normalized_workspace = _normalize_workspace_id(workspace_id)
    await require_workspace_platform_drive(current_user.id, normalized_workspace)
    return _resolve_platform_drive_scoped_path(path)


async def _authorize_system_drive_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
) -> str:
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required for system drive access",
        )
    normalized_workspace = _normalize_workspace_id(workspace_id)
    await require_workspace_system_drive(current_user.id, normalized_workspace)
    return _resolve_system_drive_scoped_path(path)


async def _authorize_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    scope: str,
    files_service: FilesService | None = None,
) -> str:
    if scope == SCOPE_MY_DRIVE:
        return _authorize_my_drive_path(
            current_user=current_user,
            path=path,
            files_service=files_service,
        )
    if scope == SCOPE_PLATFORM_DRIVE:
        return await _authorize_platform_drive_path(
            current_user=current_user,
            path=path,
            workspace_id=workspace_id,
        )
    if scope == SCOPE_SYSTEM_DRIVE:
        return await _authorize_system_drive_path(
            current_user=current_user,
            path=path,
            workspace_id=workspace_id,
        )
    return await _authorize_workspace_path(
        current_user=current_user,
        path=path,
        workspace_id=workspace_id,
        files_service=files_service,
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    path: str = Query("", description="Directory path to list"),
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=1000,
        description="Max entries to return. Omit to return the full listing.",
    ),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
    search: str | None = Query(
        default=None,
        max_length=255,
        description="Case-insensitive substring filter on entry name (this folder only)",
    ),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    return _to_file_list_response_schema(
        files_service.list_files(path=scoped_path, limit=limit, offset=offset, search=search)
    )


@router.post("/", response_model=FileInfo)
async def create_file(
    payload: CreateFileRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, payload.path, payload.workspace_id, payload.scope, files_service=files_service
    )
    return _to_file_info_schema(
        files_service.create_file(
            path=scoped_path,
            content=payload.content,
            content_type=payload.content_type,
        )
    )


@router.post("/folder", response_model=FileInfo)
async def create_folder(
    payload: CreateFolderRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, payload.path, payload.workspace_id, payload.scope, files_service=files_service
    )
    return _to_file_info_schema(files_service.create_folder(path=scoped_path))


@router.post("/rename", response_model=FileInfo)
async def rename_file(
    payload: RenameRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_old_path = await _authorize_path(
        current_user,
        payload.old_path,
        payload.workspace_id,
        payload.scope,
        files_service=files_service,
    )
    scoped_new_path = await _authorize_path(
        current_user,
        payload.new_path,
        payload.workspace_id,
        payload.scope,
        files_service=files_service,
    )

    if payload.scope != "workspace":
        return _to_file_info_schema(
            files_service.rename(old_path=scoped_old_path, new_path=scoped_new_path)
        )

    def _workspace_segment(scoped: str) -> str:
        # scoped paths are "naas_abi/workspace-drive/<ws>/..." — extract the <ws>
        parts = scoped.split("/", 3)
        return parts[2] if len(parts) >= 3 else ""

    if _workspace_segment(scoped_old_path) != _workspace_segment(scoped_new_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move files across workspaces",
        )

    return _to_file_info_schema(
        files_service.rename(old_path=scoped_old_path, new_path=scoped_new_path)
    )


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: FastAPIUploadFile = FastAPIFile(...),
    path: str = Form("", max_length=500),
    workspace_id: str | None = Form(default=None),
    scope: str = Form(default="workspace"),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    content = await file.read()
    return _to_file_info_schema(
        files_service.upload_file(
            filename=file.filename or "untitled",
            path=scoped_path,
            content=content,
            content_type=file.content_type,
        )
    )


@router.get("/preview/pdf/{path:path}")
async def preview_file_as_pdf(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    preview = files_service.preview_file_as_pdf(path=scoped_path)

    return Response(
        content=preview.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{preview.filename}"'},
    )


@router.get("/archive/{path:path}")
async def download_folder_archive(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    filename, archive_iterator = files_service.stream_folder_archive(path=scoped_path)
    return StreamingResponse(
        archive_iterator,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/raw/{path:path}")
async def read_file_raw(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    raw_file = files_service.read_file_raw(path=scoped_path)

    return Response(
        content=raw_file.content,
        media_type=raw_file.media_type,
        headers={"Content-Disposition": f'inline; filename="{raw_file.filename}"'},
    )


@router.get("/{path:path}", response_model=FileContent)
async def read_file(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    return _to_file_content_schema(files_service.read_file(path=scoped_path))


@router.put("/{path:path}", response_model=FileInfo)
async def update_file(
    path: str,
    payload: CreateFileRequest,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    effective_workspace_id = workspace_id or payload.workspace_id
    scoped_path = await _authorize_path(current_user, path, effective_workspace_id, scope, files_service=files_service)
    return _to_file_info_schema(
        files_service.update_file(
            path=scoped_path,
            content=payload.content,
            content_type=payload.content_type,
        )
    )


@router.delete("/{path:path}")
async def delete_file(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(current_user, path, workspace_id, scope, files_service=files_service)
    return files_service.delete_path(path=scoped_path)
