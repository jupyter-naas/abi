from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMPermissionError


def _context() -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"chat.message.read"}, is_authenticated=True)
    )


def test_ensure_scope_no_iam_service_is_noop() -> None:
    ensure_scope(
        context=_context(),
        required_scope="chat.message.read",
        denied_message="Denied",
        iam_service=None,
    )


def test_ensure_scope_denies_with_clear_message() -> None:
    iam_service = SimpleNamespace(
        ensure=lambda *args, **kwargs: (_ for _ in ()).throw(
            IAMPermissionError(scope="chat.message.read")
        )
    )

    with pytest.raises(PermissionError, match="Denied"):
        ensure_scope(
            context=_context(),
            required_scope="chat.message.read",
            denied_message="Denied",
            iam_service=iam_service,
        )


@pytest.mark.asyncio
async def test_ensure_workspace_access_no_workspace_service_is_noop() -> None:
    role = await ensure_workspace_access(
        context=_context(),
        workspace_id="ws-1",
        iam_service=None,
        workspace_service=None,
    )

    assert role is None


@pytest.mark.asyncio
async def test_ensure_workspace_access_denies_with_clear_message() -> None:
    workspace_service = SimpleNamespace(
        require_workspace_access=AsyncMock(side_effect=PermissionError("denied"))
    )

    with pytest.raises(PermissionError, match="Workspace access denied"):
        await ensure_workspace_access(
            context=_context(),
            workspace_id="ws-1",
            iam_service=None,
            workspace_service=workspace_service,
        )
