"""Files FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response
from fastapi import File as FastAPIFile
from fastapi import UploadFile as FastAPIUploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
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
    AlreadyExistsError,
    FileContentData,
    FileInfoData,
    FileListResponseData,
    InvalidPathError,
    IsDirectoryError,
    NotFoundError,
    NotTextError,
    PreviewConversionError,
    PreviewUnavailableError,
    UnsupportedPreviewError,
    UploadTooLargeError,
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


def _raise_http_exception(exc: Exception) -> None:
    if isinstance(exc, InvalidPathError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, AlreadyExistsError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, IsDirectoryError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, NotTextError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, UploadTooLargeError):
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    if isinstance(exc, UnsupportedPreviewError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, PreviewUnavailableError):
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    if isinstance(exc, PreviewConversionError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise


@router.get("/", response_model=FileListResponse)
async def list_files(
    path: str = Query("", description="Directory path to list"),
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_list_response_schema(files_service.list_files(path=path))
    except Exception as exc:
        _raise_http_exception(exc)


@router.post("/", response_model=FileInfo)
async def create_file(
    payload: CreateFileRequest,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_info_schema(
            files_service.create_file(
                path=payload.path,
                content=payload.content,
                content_type=payload.content_type,
            )
        )
    except Exception as exc:
        _raise_http_exception(exc)


@router.post("/folder", response_model=FileInfo)
async def create_folder(
    payload: CreateFolderRequest,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_info_schema(files_service.create_folder(path=payload.path))
    except Exception as exc:
        _raise_http_exception(exc)


@router.post("/rename", response_model=FileInfo)
async def rename_file(
    payload: RenameRequest,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_info_schema(
            files_service.rename(old_path=payload.old_path, new_path=payload.new_path)
        )
    except Exception as exc:
        _raise_http_exception(exc)


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: FastAPIUploadFile = FastAPIFile(...),
    path: str = Form("", max_length=500),
    files_service: FilesService = Depends(get_files_service),
):
    content = await file.read()
    try:
        return _to_file_info_schema(
            files_service.upload_file(
                filename=file.filename or "untitled",
                path=path,
                content=content,
                content_type=file.content_type,
            )
        )
    except Exception as exc:
        _raise_http_exception(exc)


@router.get("/preview/pdf/{path:path}")
async def preview_file_as_pdf(
    path: str,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        preview = files_service.preview_file_as_pdf(path=path)
    except Exception as exc:
        _raise_http_exception(exc)

    return Response(
        content=preview.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{preview.filename}"'},
    )


@router.get("/raw/{path:path}")
async def read_file_raw(
    path: str,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        raw_file = files_service.read_file_raw(path=path)
    except Exception as exc:
        _raise_http_exception(exc)

    return Response(
        content=raw_file.content,
        media_type=raw_file.media_type,
        headers={"Content-Disposition": f'inline; filename="{raw_file.filename}"'},
    )


@router.get("/{path:path}", response_model=FileContent)
async def read_file(
    path: str,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_content_schema(files_service.read_file(path=path))
    except Exception as exc:
        _raise_http_exception(exc)


@router.put("/{path:path}", response_model=FileInfo)
async def update_file(
    path: str,
    payload: CreateFileRequest,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return _to_file_info_schema(
            files_service.update_file(
                path=path,
                content=payload.content,
                content_type=payload.content_type,
            )
        )
    except Exception as exc:
        _raise_http_exception(exc)


@router.delete("/{path:path}")
async def delete_file(
    path: str,
    files_service: FilesService = Depends(get_files_service),
):
    try:
        return files_service.delete_path(path=path)
    except Exception as exc:
        _raise_http_exception(exc)
