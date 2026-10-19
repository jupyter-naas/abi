"""Files FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi import File as FastAPIFile
from fastapi import UploadFile as FastAPIUploadFile
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.content_disposition import content_disposition
from naas_abi.apps.nexus.apps.api.app.core.user_content import user_content_headers
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    get_files_service,
    workspace_setting,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__schemas import (  # noqa: E501
    CreateFileRequest,
    CreateFolderRequest,
    FileContent,
    FileInfo,
    FileListResponse,
    RenameRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.scripts.legacy_storage_migration import (
    LegacyStorageMigrator,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    PLATFORM_DRIVE_ROOT,
    SCOPE_MY_DRIVE,
    SCOPE_PATTERN,
    SCOPE_PLATFORM_DRIVE,
    SCOPE_SYSTEM_DRIVE,
    SYSTEM_DRIVE_ROOT,
    WORKSPACE_DRIVE_ROOT,
    my_drive_root,
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    FileContentData,
    FileInfoData,
    FileListResponseData,
)
from naas_abi.apps.nexus.apps.api.app.services.files.placement import (
    ensure_workspace_drive_placed,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi_core.engine.call_context import as_service_account

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class FilesFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


# What a request does to a file, and the IAM action it needs on each kind of drive:
# the workspace and platform drives, the system drive (admins), My drive.
_ACTIONS: dict[str, tuple[str, str, str]] = {
    "list": ("ListFiles", "ListSystemFiles", "ListMyFiles"),
    "read": ("GetFile", "GetSystemFile", "GetMyFile"),
    "write": ("PutFile", "PutSystemFile", "PutMyFile"),
    "delete": ("DeleteFile", "DeleteSystemFile", "DeleteMyFile"),
}


def _declares(op: str) -> list:
    """The route authorizes inline, once the drive and the path are resolved."""
    return [declares(name) for name in _ACTIONS[op]]


def _below(storage_path: str, root: str) -> list[str]:
    """The segments of ``storage_path`` under ``root`` (all of them for no root)."""
    rest = storage_path[len(root) :] if root else storage_path
    return [segment for segment in rest.split("/") if segment]


def _reject_system_path(*paths: str) -> None:
    """System files (any path segment starting with ".") are read-only over HTTP.

    The UI hides and locks them; this is the same rule enforced server-side, so
    no client can create, change, move or delete them. Server code that owns
    them (folder markers, agents) goes through FilesService directly.
    """
    for path in paths:
        if any(segment.startswith(".") for segment in path.split("/") if segment):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='System files (names starting with ".") are read-only',
            )


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
    ``root`` means "no prefix" : paths are returned as-is, resolving against
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
    """Resolve a workspace-drive path to its storage key.

    Callers may pass:
    - a path relative to the workspace root (``docs/readme.md``)
    - a legacy bare-workspace path (``ws-1/docs/readme.md``)
    - a full storage path returned by list/create (``naas_abi/workspace-drive/ws-1/...``)

    List/rename/delete round-trip the full storage path from the API response, so
    already-scoped paths must not be re-prefixed under the workspace root.
    """
    normalized_path = FilesService.normalize_relative_path(path, allow_empty=True)
    normalized_workspace = _normalize_workspace_id(workspace_id) if workspace_id else None
    drive_prefix = f"{WORKSPACE_DRIVE_ROOT}/"

    if not normalized_workspace:
        if not normalized_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="workspace_id is required when path is empty",
            )
        if normalized_path.startswith(drive_prefix):
            rest = normalized_path[len(drive_prefix) :]
            if not rest:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="workspace_id is required when path is empty",
                )
            normalized_workspace = _normalize_workspace_id(rest.split("/", 1)[0])
        else:
            # Legacy bare-workspace path layout: <ws>/...
            normalized_workspace = _normalize_workspace_id(normalized_path.split("/", 1)[0])

    root = workspace_drive_root(normalized_workspace)

    # Full storage paths from list/create/rename round-trips.
    if normalized_path == WORKSPACE_DRIVE_ROOT:
        return normalized_workspace, root
    if normalized_path == root or normalized_path.startswith(f"{root}/"):
        return normalized_workspace, normalized_path
    if normalized_path.startswith(drive_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is outside the requested workspace",
        )

    # Strip a redundant leading workspace segment, then anchor under the root.
    if normalized_path == normalized_workspace:
        body = ""
    elif normalized_path.startswith(f"{normalized_workspace}/"):
        body = normalized_path[len(normalized_workspace) + 1 :]
    else:
        body = normalized_path

    return normalized_workspace, _scope_to_path(root, body)


def _resolve_my_drive_scoped_path(path: str, user_id: str) -> str:
    normalized_user = _normalize_user_id(user_id)
    return _scope_to_path(my_drive_root(normalized_user), path)


def _resolve_platform_drive_scoped_path(path: str) -> str:
    return _scope_to_path(PLATFORM_DRIVE_ROOT, path)


def _resolve_system_drive_scoped_path(path: str) -> str:
    return _scope_to_path(SYSTEM_DRIVE_ROOT, path)


def _migrate_legacy_layout(
    files_service: FilesService, *, workspace_id: str | None = None, user_id: str | None = None
) -> None:
    """Move a drive of the old layout, once. The legacy roots belong to nobody
    IAM knows, so the move is Nexus's own, after the caller was authorized."""
    migrator = LegacyStorageMigrator(files_service)
    with as_service_account("api"):
        if workspace_id is not None:
            migrator.ensure_workspace_drive_migrated(workspace_id)
        if user_id is not None:
            migrator.ensure_my_drive_migrated(user_id)


async def _authorize_workspace_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    op: str,
    files_service: FilesService | None = None,
) -> str:
    resolved_workspace_id, resolved_path = _resolve_workspace_scoped_path(path, workspace_id)
    await authz.require(
        _ACTIONS[op][0],
        user=current_user,
        workspace=resolved_workspace_id,
        id=("workspace", *_below(resolved_path, workspace_drive_root(resolved_workspace_id))),
    )
    await ensure_workspace_drive_placed(resolved_workspace_id)
    if files_service is not None:
        _migrate_legacy_layout(files_service, workspace_id=resolved_workspace_id)
    return resolved_path


async def _authorize_my_drive_path(
    current_user: User,
    path: str,
    op: str,
    files_service: FilesService | None = None,
) -> str:
    resolved = _resolve_my_drive_scoped_path(path=path, user_id=current_user.id)
    await authz.require(
        _ACTIONS[op][2],
        user=current_user,
        id=(current_user.id, *_below(resolved, my_drive_root(current_user.id))),
    )
    if files_service is not None:
        _migrate_legacy_layout(files_service, user_id=current_user.id)
    return resolved


async def _authorize_platform_drive_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    op: str,
) -> str:
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required for platform drive access",
        )
    normalized_workspace = _normalize_workspace_id(workspace_id)
    scoped = _resolve_platform_drive_scoped_path(path)
    await authz.require(
        _ACTIONS[op][0],
        user=current_user,
        workspace=normalized_workspace,
        id=("platform", *_below(scoped, PLATFORM_DRIVE_ROOT)),
    )
    # A workspace uses the shared drive only when it switched it on.
    if not await workspace_setting(normalized_workspace, "platform_drive_enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform drive is not enabled for this workspace",
        )
    return scoped


async def _authorize_system_drive_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    op: str,
) -> str:
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required for system drive access",
        )
    normalized_workspace = _normalize_workspace_id(workspace_id)
    scoped = _resolve_system_drive_scoped_path(path)
    await authz.require(
        _ACTIONS[op][1],
        user=current_user,
        workspace=normalized_workspace,
        id=("system", *_below(scoped, SYSTEM_DRIVE_ROOT)),
        denied="Workspace admin role required",
    )
    # The whole tree the workspace holds, only when it switched the drive on.
    if not await workspace_setting(normalized_workspace, "system_drive_enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System drive is not enabled for this workspace",
        )
    await ensure_workspace_drive_placed(normalized_workspace)
    return scoped


async def _authorize_path(
    current_user: User,
    path: str,
    workspace_id: str | None,
    scope: str,
    op: str,
    files_service: FilesService | None = None,
) -> str:
    if scope == SCOPE_MY_DRIVE:
        return await _authorize_my_drive_path(
            current_user=current_user,
            path=path,
            op=op,
            files_service=files_service,
        )
    if scope == SCOPE_PLATFORM_DRIVE:
        return await _authorize_platform_drive_path(
            current_user=current_user,
            path=path,
            workspace_id=workspace_id,
            op=op,
        )
    if scope == SCOPE_SYSTEM_DRIVE:
        return await _authorize_system_drive_path(
            current_user=current_user,
            path=path,
            workspace_id=workspace_id,
            op=op,
        )
    return await _authorize_workspace_path(
        current_user=current_user,
        path=path,
        workspace_id=workspace_id,
        op=op,
        files_service=files_service,
    )


@router.get("/", response_model=FileListResponse, dependencies=_declares("list"))
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
    sort_by: str = Query(
        default="name",
        pattern="^(name|size|modified)$",
        description="Column to sort the full listing by before paging",
    ),
    sort_dir: str = Query(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort direction",
    ),
    include_hidden: bool = Query(
        default=True,
        description='List system entries (names starting with ".")',
    ),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "list", files_service=files_service
    )
    return _to_file_list_response_schema(
        files_service.list_files(
            path=scoped_path,
            limit=limit,
            offset=offset,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            include_hidden=include_hidden,
        )
    )


@router.post("/", response_model=FileInfo, dependencies=_declares("write"))
async def create_file(
    payload: CreateFileRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(payload.path)
    scoped_path = await _authorize_path(
        current_user,
        payload.path,
        payload.workspace_id,
        payload.scope,
        "write",
        files_service=files_service,
    )
    return _to_file_info_schema(
        files_service.create_file(
            path=scoped_path,
            content=payload.content,
            content_type=payload.content_type,
        )
    )


@router.post("/folder", response_model=FileInfo, dependencies=_declares("write"))
async def create_folder(
    payload: CreateFolderRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(payload.path)
    scoped_path = await _authorize_path(
        current_user,
        payload.path,
        payload.workspace_id,
        payload.scope,
        "write",
        files_service=files_service,
    )
    return _to_file_info_schema(files_service.create_folder(path=scoped_path))


@router.post("/rename", response_model=FileInfo, dependencies=_declares("write"))
async def rename_file(
    payload: RenameRequest,
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(payload.old_path, payload.new_path)
    scoped_old_path = await _authorize_path(
        current_user,
        payload.old_path,
        payload.workspace_id,
        payload.scope,
        "delete",
        files_service=files_service,
    )
    scoped_new_path = await _authorize_path(
        current_user,
        payload.new_path,
        payload.workspace_id,
        payload.scope,
        "write",
        files_service=files_service,
    )

    if payload.scope != "workspace":
        return _to_file_info_schema(
            files_service.rename(old_path=scoped_old_path, new_path=scoped_new_path)
        )

    def _workspace_segment(scoped: str) -> str:
        # scoped paths are "naas_abi/workspace-drive/<ws>/...", extract the <ws>
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


@router.post("/upload", response_model=FileInfo, dependencies=_declares("write"))
async def upload_file(
    file: FastAPIUploadFile = FastAPIFile(...),
    path: str = Form("", max_length=500),
    workspace_id: str | None = Form(default=None),
    scope: str = Form(default="workspace"),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(path, file.filename or "")
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "write", files_service=files_service
    )
    content = await file.read()
    return _to_file_info_schema(
        files_service.upload_file(
            filename=file.filename or "untitled",
            path=scoped_path,
            content=content,
            content_type=file.content_type,
        )
    )


@router.get("/preview/pdf/{path:path}", dependencies=_declares("read"))
async def preview_file_as_pdf(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "read", files_service=files_service
    )
    preview = files_service.preview_file_as_pdf(path=scoped_path)

    return Response(
        content=preview.content,
        media_type="application/pdf",
        headers=user_content_headers(preview.filename, "application/pdf"),
    )


@router.get("/archive/{path:path}", dependencies=_declares("read"))
async def download_folder_archive(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "read", files_service=files_service
    )
    filename, archive_iterator = files_service.stream_folder_archive(path=scoped_path)
    return StreamingResponse(
        archive_iterator,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition("attachment", filename)},
    )


@router.post("/extract/{path:path}", response_model=FileInfo, dependencies=_declares("write"))
async def extract_archive(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(path)
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "write", files_service=files_service
    )
    return _to_file_info_schema(files_service.extract_archive(path=scoped_path))


@router.get("/raw/{path:path}", dependencies=_declares("read"))
async def read_file_raw(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "read", files_service=files_service
    )
    raw_file = files_service.read_file_raw(path=scoped_path)

    return Response(
        content=raw_file.content,
        media_type=raw_file.media_type,
        headers=user_content_headers(raw_file.filename, raw_file.media_type),
    )


@router.get("/{path:path}", response_model=FileContent, dependencies=_declares("read"))
async def read_file(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "read", files_service=files_service
    )
    return _to_file_content_schema(files_service.read_file(path=scoped_path))


@router.put("/{path:path}", response_model=FileInfo, dependencies=_declares("write"))
async def update_file(
    path: str,
    payload: CreateFileRequest,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(path)
    effective_workspace_id = workspace_id or payload.workspace_id
    scoped_path = await _authorize_path(
        current_user, path, effective_workspace_id, scope, "write", files_service=files_service
    )
    return _to_file_info_schema(
        files_service.update_file(
            path=scoped_path,
            content=payload.content,
            content_type=payload.content_type,
        )
    )


@router.delete("/{path:path}", dependencies=_declares("delete"))
async def delete_file(
    path: str,
    workspace_id: str | None = Query(default=None, max_length=100),
    scope: str = Query(default="workspace", pattern=SCOPE_PATTERN),
    current_user: User = Depends(get_current_user_required),
    files_service: FilesService = Depends(get_files_service),
):
    _reject_system_path(path)
    scoped_path = await _authorize_path(
        current_user, path, workspace_id, scope, "delete", files_service=files_service
    )
    return files_service.delete_path(path=scoped_path)
