"""FilesAgent tools for Nexus Files (workspace object storage browser).

Same operations as ``/api/files`` for the two personal-scope drives:
``workspace`` (``naas_abi/workspace-drive/<workspace_id>/...``, membership
checked) and ``my_drive`` (``naas_abi/my-drive/<user_id>/...``). Paths go
through the adapter's own scoping helpers, so a tool cannot step outside the
caller's drive. Platform and system drives need extra per-workspace flags and
are left to the UI.

The file or folder open in the Files browser arrives as the open feature
resource (kind ``file`` or ``folder``; My drive items are prefixed
``my_drive:``), so tools default to it.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    check_member,
    guarded,
    jsonable,
    tool_context,
)

FILE_RESOURCE_KIND = "file"
FOLDER_RESOURCE_KIND = "folder"
_FEATURE = "Files"
_DRIVES = ("workspace", "my_drive")
_MAX_ENTRIES = 200
_MAX_READ_CHARS = 40_000


def _service() -> Any:
    from naas_abi import ABIModule
    from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

    return FilesService(storage=ABIModule.get_instance().engine.services.object_storage)


def _scoped(
    path: str, drive: str, user_id: str, workspace_id: str
) -> str | dict[str, str]:
    """Storage key for ``path`` inside the caller's drive, or an error."""
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI import (
        _resolve_my_drive_scoped_path,
        _resolve_workspace_scoped_path,
    )

    if drive not in _DRIVES:
        return {"error": f"drive must be one of {', '.join(_DRIVES)}."}
    try:
        if drive == "my_drive":
            return _resolve_my_drive_scoped_path(path=path, user_id=user_id)
        resolved_workspace, scoped = _resolve_workspace_scoped_path(path, workspace_id)
    except HTTPException as exc:
        return {"error": str(exc.detail)}
    if resolved_workspace != workspace_id:
        return {"error": "Path is outside this workspace's drive."}
    return scoped


_MY_DRIVE_PREFIX = "my_drive:"


def _split_drive(value: str, drive: str = "") -> tuple[str, str]:
    """(drive, path). The pane sends My drive items as ``my_drive:<path>``;
    a full ``naas_abi/my-drive/...`` key also means My drive."""
    text = (value or "").strip()
    if text.startswith(_MY_DRIVE_PREFIX):
        return "my_drive", text[len(_MY_DRIVE_PREFIX) :]
    if drive:
        return drive, text
    return ("my_drive" if "/my-drive/" in f"/{text}" else "workspace"), text


def _domain_error(exc: Exception) -> dict[str, str] | None:
    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
        FilesDomainError,
    )

    if isinstance(exc, FilesDomainError):
        return {"error": str(exc) or type(exc).__name__}
    return None


def files_tools() -> list[BaseTool]:
    @tool
    def list_files(path: str = "", drive: str = "", query: str = "") -> Any:
        """List a folder in the workspace drive (default) or my_drive.

        Omit path to list the folder open in the Files browser, else the drive
        root. query filters names in this folder. Rows: name, path (full
        storage key), type, size, modified.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        target_drive, wanted = _split_drive(
            (path or "").strip()
            or active_feature_resource_id(FOLDER_RESOURCE_KIND)
            or "",
            (drive or "").strip(),
        )

        def _run() -> Any:
            if target_drive == "workspace":
                role = check_member(user_id, workspace_id)
                if isinstance(role, dict):
                    return role
            scoped = _scoped(wanted, target_drive, user_id, workspace_id)
            if isinstance(scoped, dict):
                return scoped
            try:
                listing = _service().list_files(
                    path=scoped,
                    limit=_MAX_ENTRIES,
                    offset=0,
                    search=(query or "").strip() or None,
                    sort_by="name",
                    sort_dir="asc",
                )
            except Exception as exc:
                known = _domain_error(exc)
                if known:
                    return known
                raise
            return {
                "drive": target_drive,
                "path": listing.path,
                "total": listing.total,
                "entries": jsonable(listing.files),
            }

        return guarded(_FEATURE, _run)

    @tool
    def read_text_file(path: str = "") -> Any:
        """Read a text file (UTF-8) from the workspace drive or my_drive.

        Omit path to read the file open in the Files browser. Binary files
        are refused; long files are truncated.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        raw = (path or "").strip() or active_feature_resource_id(FILE_RESOURCE_KIND)
        if not raw:
            return {"error": "No file is open. Pass path (see list_files)."}
        target_drive, wanted = _split_drive(raw)

        def _run() -> Any:
            if target_drive == "workspace":
                role = check_member(user_id, workspace_id)
                if isinstance(role, dict):
                    return role
            scoped = _scoped(wanted, target_drive, user_id, workspace_id)
            if isinstance(scoped, dict):
                return scoped
            try:
                content = _service().read_file(path=scoped)
            except Exception as exc:
                known = _domain_error(exc)
                if known:
                    return known
                raise
            text = content.content
            return {
                "path": content.path,
                "content_type": content.content_type,
                "truncated": len(text) > _MAX_READ_CHARS,
                "content": text[:_MAX_READ_CHARS],
            }

        return guarded(_FEATURE, _run)

    @tool
    def write_text_file(path: str, content: str, overwrite: bool = False) -> Any:
        """Create a text file in the workspace drive (prefix the path with
        my_drive: for My drive). Set overwrite=True to replace an existing file.

        A bare name lands in the folder open in the Files browser.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        name = (path or "").strip()
        if not name:
            return {"error": "path is required."}
        open_folder = active_feature_resource_id(FOLDER_RESOURCE_KIND)
        if "/" not in name and ":" not in name and open_folder:
            folder_drive, folder = _split_drive(open_folder)
            prefix = _MY_DRIVE_PREFIX if folder_drive == "my_drive" else ""
            name = (
                f"{prefix}{folder.rstrip('/')}/{name}" if folder else f"{prefix}{name}"
            )
        target_drive, name = _split_drive(name)

        def _run() -> Any:
            if target_drive == "workspace":
                role = check_member(user_id, workspace_id)
                if isinstance(role, dict):
                    return role
            scoped = _scoped(name, target_drive, user_id, workspace_id)
            if isinstance(scoped, dict):
                return scoped
            service = _service()
            try:
                try:
                    info = service.create_file(path=scoped, content=content)
                    action = "created"
                except Exception as exc:
                    from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
                        AlreadyExistsError,
                    )

                    if not isinstance(exc, AlreadyExistsError) or not overwrite:
                        raise
                    info = service.update_file(
                        path=scoped, content=content, content_type="text/plain"
                    )
                    action = "overwritten"
            except Exception as exc:
                known = _domain_error(exc)
                if known:
                    if type(exc).__name__ == "AlreadyExistsError":
                        known["hint"] = (
                            "Pass overwrite=True to replace the existing file."
                        )
                    return known
                raise
            out = jsonable(info)
            out["action"] = action
            out["note"] = "Refresh the Files browser to see it."
            return out

        return guarded(_FEATURE, _run)

    return [list_files, read_text_file, write_text_file]
