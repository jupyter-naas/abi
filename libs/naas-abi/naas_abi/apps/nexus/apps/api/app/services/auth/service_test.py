from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import hash_token


@pytest.mark.asyncio
async def test_forgot_password_stores_hashed_token() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )

    service = AuthService(adapter=adapter)
    raw_token = await service.forgot_password("USER@EXAMPLE.COM")

    assert raw_token is not None
    assert raw_token != ""
    adapter.create_password_reset_token.assert_awaited_once()
    stored_token = adapter.create_password_reset_token.await_args.kwargs["token"]
    assert stored_token == hash_token(raw_token)
    assert stored_token != raw_token


@pytest.mark.asyncio
async def test_forgot_password_for_unknown_user_does_not_store_token() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    token = await service.forgot_password("unknown@example.com")

    assert token is None
    adapter.create_password_reset_token.assert_not_called()
    adapter.commit.assert_not_called()
