from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
    files__primary_adapter__FastAPI as files_api,
)


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
    assert scoped_path == "ws-1/docs/readme.md"


def test_resolve_workspace_scoped_path_uses_path_workspace_when_not_provided() -> None:
    workspace_id, scoped_path = files_api._resolve_workspace_scoped_path(
        "ws-2/docs/readme.md",
        None,
    )

    assert workspace_id == "ws-2"
    assert scoped_path == "ws-2/docs/readme.md"


@pytest.mark.asyncio
async def test_authorize_workspace_path_checks_workspace_access(monkeypatch) -> None:
    require_access = AsyncMock()
    monkeypatch.setattr(files_api, "require_workspace_access", require_access)

    scoped_path = await files_api._authorize_workspace_path(
        current_user=SimpleNamespace(id="user-1"),
        path="docs/readme.md",
        workspace_id="ws-1",
    )

    assert scoped_path == "ws-1/docs/readme.md"
    require_access.assert_awaited_once_with("user-1", "ws-1")


def test_resolve_my_drive_scoped_path() -> None:
    scoped_path = files_api._resolve_my_drive_scoped_path(
        path="uploads/readme.md",
        user_id="user-1",
    )

    assert scoped_path == "my-drive/user-1/uploads/readme.md"


@pytest.mark.asyncio
async def test_authorize_path_my_drive_skips_workspace_check(monkeypatch) -> None:
    require_access = AsyncMock()
    monkeypatch.setattr(files_api, "require_workspace_access", require_access)

    scoped_path = await files_api._authorize_path(
        current_user=SimpleNamespace(id="user-1"),
        path="uploads/readme.md",
        workspace_id=None,
        scope="my_drive",
    )

    assert scoped_path == "my-drive/user-1/uploads/readme.md"
    require_access.assert_not_awaited()
