"""Files FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi import File as FastAPIFile
from fastapi import UploadFile as FastAPIUploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
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
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    FileContentData,
    FileInfoData,
    FileListResponseData,
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
    )


def _normalize_workspace_id(workspace_id: str) -> str:
    normalized = FilesService.normalize_relative_path(workspace_id)
    if "/" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id must be a single path segment",
        )
    return normalized


def _resolve_workspace_scoped_path(path: str, workspace_id: str | None) -> tuple[str, str]:
    normalized_path = FilesService.normalize_relative_path(path, allow_empty=True)
    normalized_workspace = _normalize_workspace_id(workspace_id) if workspace_id else None

    if normalized_workspace:
        if not normalized_path:
            return normalized_workspace, normalized_workspace
        if normalized_path == normalized_workspace or normalized_path.startswith(
            f"{normalized_workspace}/"
        ):
            return normalized_workspace, normalized_path
        return normalized_workspace, f"{normalized_workspace}/{normalized_path}"

    if not normalized_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required when path is empty",
        )

    workspace = normalized_path.split("/", 1)[0]
    return workspace, normalized_path


async def _authorize_workspace_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
) -> str:
    resolved_workspace_id, resolved_path = _resolve_workspace_scoped_path(path, workspace_id)
    await require_workspace_access(current_user.id, resolved_workspace_id)
    return resolved_path


@router.get("/", response_model=FileListResponse)
async def list_files(
    path: str = Query("", description="Directory path to list"),
    workspace_id: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
    return _to_file_list_response_schema(files_service.list_files(path=scoped_path))


@router.post("/", response_model=FileInfo)
async def create_file(
    payload: CreateFileRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, payload.path, payload.workspace_id)
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
    scoped_path = await _authorize_workspace_path(current_user, payload.path, payload.workspace_id)
    return _to_file_info_schema(files_service.create_folder(path=scoped_path))


@router.post("/rename", response_model=FileInfo)
async def rename_file(
    payload: RenameRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_old_path = await _authorize_workspace_path(
        current_user,
        payload.old_path,
        payload.workspace_id,
    )
    scoped_new_path = await _authorize_workspace_path(
        current_user,
        payload.new_path,
        payload.workspace_id,
    )

    old_workspace = scoped_old_path.split("/", 1)[0]
    new_workspace = scoped_new_path.split("/", 1)[0]
    if old_workspace != new_workspace:
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
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
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
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
    preview = files_service.preview_file_as_pdf(path=scoped_path)

    return Response(
        content=preview.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{preview.filename}"'},
    )


@router.get("/raw/{path:path}")
async def read_file_raw(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
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
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
    return _to_file_content_schema(files_service.read_file(path=scoped_path))


@router.put("/{path:path}", response_model=FileInfo)
async def update_file(
    path: str,
    payload: CreateFileRequest,
    workspace_id: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    effective_workspace_id = workspace_id or payload.workspace_id
    scoped_path = await _authorize_workspace_path(current_user, path, effective_workspace_id)
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
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_workspace_path(current_user, path, workspace_id)
    return files_service.delete_path(path=scoped_path)
