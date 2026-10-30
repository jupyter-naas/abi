from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
    files__primary_adapter__FastAPI as files_api,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied


def test_resolve_workspace_scoped_path_rejects_empty_path_without_workspace() -> None:
    with pytest.raises(HTTPException) as exc_info:
        files_api._resolve_workspace_scoped_path("", None)

    assert exc_info.value.status_code == 400


def test_resolve_workspace_scoped_path_prefixes_relative_path() -> None:
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "docs/readme.md",
        "ws-1",
    )

    assert workspace_id == "ws-1"
    assert scoped_path == "naas_abi/workspace-drive/ws-1/docs/readme.md"


def test_resolve_workspace_scoped_path_uses_path_workspace_when_not_provided() -> None:
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "ws-2/docs/readme.md",
        None,
    )

    assert workspace_id == "ws-2"
    assert scoped_path == "naas_abi/workspace-drive/ws-2/docs/readme.md"


def test_resolve_workspace_scoped_path_keeps_full_storage_path() -> None:
    """List/rename round-trip full storage paths; do not double-prefix them."""
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "naas_abi/workspace-drive/ws-1/operations",
        "ws-1",
    )

    assert workspace_id == "ws-1"
    assert scoped_path == "naas_abi/workspace-drive/ws-1/operations"


def test_resolve_workspace_scoped_path_keeps_workspace_root_folder() -> None:
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "naas_abi/workspace-drive/ws-1",
        "ws-1",
    )

    assert workspace_id == "ws-1"
    assert scoped_path == "naas_abi/workspace-drive/ws-1"


def test_resolve_workspace_scoped_path_infers_workspace_from_full_storage_path() -> None:
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "naas_abi/workspace-drive/ws-3/s2_intelligence",
        None,
    )

    assert workspace_id == "ws-3"
    assert scoped_path == "naas_abi/workspace-drive/ws-3/s2_intelligence"


def test_resolve_workspace_scoped_path_rejects_other_workspace_storage_path() -> None:
    with pytest.raises(HTTPException) as exc_info:
        files_api._resolve_workspace_scoped_path(
            "naas_abi/workspace-drive/ws-other/ops",
            "ws-1",
        )

    assert exc_info.value.status_code == 400
    assert "outside the requested workspace" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_authorize_workspace_path_asks_iam_for_the_workspace(team) -> None:
    scoped_path = await files_api._authorize_workspace_path(
        current_user=SimpleNamespace(id="member"),
        path="docs/readme.md",
        workspace_id="ws-1",
        op="read",
    )

    assert scoped_path == "naas_abi/workspace-drive/ws-1/docs/readme.md"
    with pytest.raises(AuthzDenied) as denied:
        await files_api._authorize_workspace_path(
            current_user=SimpleNamespace(id="stranger"),
            path="docs/readme.md",
            workspace_id="ws-1",
            op="read",
        )
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_authorize_workspace_path_needs_a_write_role_to_write(team) -> None:
    for user, allowed in (("viewer", False), ("member", True)):
        attempt = files_api._authorize_workspace_path(
            current_user=SimpleNamespace(id=user),
            path="docs/readme.md",
            workspace_id="ws-1",
            op="write",
        )
        if allowed:
            await attempt
        else:
            with pytest.raises(AuthzDenied):
                await attempt


def test_resolve_my_drive_scoped_path() -> None:
    scoped_path = files_api._resolve_my_drive_scoped_path(
        path="uploads/readme.md",
        user_id="user-1",
    )

    assert scoped_path == "naas_abi/my-drive/user-1/uploads/readme.md"


def test_resolve_platform_drive_scoped_path() -> None:
    scoped_path = files_api._resolve_platform_drive_scoped_path("shared/readme.md")
    assert scoped_path == "naas_abi/platform-drive/shared/readme.md"


@pytest.mark.asyncio
async def test_authorize_path_my_drive_is_the_callers_own_and_names_no_workspace(team) -> None:
    scoped_path = await files_api._authorize_path(
        current_user=SimpleNamespace(id="member"),
        path="uploads/readme.md",
        workspace_id=None,
        scope="my_drive",
        op="read",
    )

    assert scoped_path == "naas_abi/my-drive/member/uploads/readme.md"


@pytest.mark.asyncio
async def test_authorize_path_platform_drive_requires_workspace(team) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await files_api._authorize_path(
            current_user=SimpleNamespace(id="member"),
            path="shared/readme.md",
            workspace_id=None,
            scope="platform_drive",
            op="read",
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_authorize_path_platform_drive_checks_flag(team, monkeypatch) -> None:
    enabled = {"platform_drive_enabled": True}

    async def setting(workspace_id: str, name: str) -> bool:
        assert workspace_id == "ws-1"
        return enabled[name]

    monkeypatch.setattr(files_api, "workspace_setting", setting)
    user = SimpleNamespace(id="member")

    scoped_path = await files_api._authorize_path(
        current_user=user,
        path="shared/readme.md",
        workspace_id="ws-1",
        scope="platform_drive",
        op="read",
    )
    assert scoped_path == "naas_abi/platform-drive/shared/readme.md"

    enabled["platform_drive_enabled"] = False
    with pytest.raises(HTTPException) as exc_info:
        await files_api._authorize_path(
            current_user=user,
            path="shared/readme.md",
            workspace_id="ws-1",
            scope="platform_drive",
            op="read",
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "path",
    [".env", "docs/.abi", "docs/.abi/config.yaml", "naas_abi/workspace-drive/ws-1/.gitkeep"],
)
def test_reject_system_path_refuses_dot_segments(path: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        files_api._reject_system_path(path)

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "path",
    ["", "docs/readme.md", "naas_abi/workspace-drive/ws-1/archive.tar.gz", "/docs//notes"],
)
def test_reject_system_path_allows_ordinary_paths(path: str) -> None:
    files_api._reject_system_path(path)


def test_reject_system_path_checks_every_path_given() -> None:
    # Rename: an ordinary file cannot be renamed into a system name either.
    with pytest.raises(HTTPException):
        files_api._reject_system_path("docs/readme.md", "docs/.readme.md")
