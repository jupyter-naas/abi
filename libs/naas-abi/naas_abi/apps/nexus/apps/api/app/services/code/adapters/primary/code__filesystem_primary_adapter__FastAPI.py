"""Code filesystem FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__dependencies import (
    get_code_filesystem_service,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__exceptions import (
    raise_http_for_code_error,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__schemas import (
    FSEntry,
    FSListResponse,
    RenameBody,
    WriteBody,
)
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeDomainError,
    CodeFSEntryData,
    CodeFSListResponseData,
)
from naas_abi.apps.nexus.apps.api.app.services.code.filesystem_service import CodeFilesystemService

filesystem_router = APIRouter(dependencies=[Depends(get_current_user_required)])


def _to_fs_entry(value: CodeFSEntryData) -> FSEntry:
    return FSEntry(
        name=value.name,
        path=value.path,
        type=value.type,
        size=value.size,
        modified=value.modified,
        writable=value.writable,
    )


def _to_fs_list_response(value: CodeFSListResponseData) -> FSListResponse:
    return FSListResponse(
        files=[_to_fs_entry(entry) for entry in value.files],
        path=value.path,
        sandbox_root=value.sandbox_root,
    )


@filesystem_router.get("/", response_model=FSListResponse)
async def list_path(
    path: str = Query("", description="Path relative to the user's Code sandbox in My Drive"),
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        return _to_fs_list_response(service.list_path(path, user_id=current_user.id))
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@filesystem_router.get("/content", response_class=PlainTextResponse)
async def read_file(
    path: str = Query(..., description="File path in the user's Code sandbox"),
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        return service.read_file(path, user_id=current_user.id)
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@filesystem_router.put("/content")
async def write_file(
    path: str = Query(..., description="File path in the user's Code sandbox"),
    body: WriteBody = WriteBody(),
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        result = service.write_file(path, body.content, user_id=current_user.id)
        return {"path": result.path, "size": result.size}
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@filesystem_router.post("/folder")
async def create_folder(
    path: str = Query(..., description="Folder path in the user's Code sandbox"),
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        return service.create_folder(path, user_id=current_user.id)
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@filesystem_router.post("/rename")
async def rename_path(
    path: str = Query(..., description="Current path in the user's Code sandbox"),
    body: RenameBody = ...,
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        result = service.rename_path(path, body.new_path, user_id=current_user.id)
        return {"old_path": result.old_path, "new_path": result.new_path}
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@filesystem_router.delete("/content")
async def delete_path(
    path: str = Query(..., description="File or folder path in the user's Code sandbox"),
    current_user: User = Depends(get_current_user_required),
    service: CodeFilesystemService = Depends(get_code_filesystem_service),
):
    try:
        result = service.delete_path(path, user_id=current_user.id)
        return {"path": result.path, "deleted": result.deleted}
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)
