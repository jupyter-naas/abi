from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_api,
)


@pytest.mark.asyncio
async def test_forgot_password_never_logs_token(caplog) -> None:
    token_value = "sensitive-reset-token"
    auth_service = AsyncMock()
    auth_service.forgot_password = AsyncMock(return_value=token_value)

    response = await auth_api.forgot_password(
        request=auth_api.ForgotPasswordRequest(email="user@example.com"),
        auth_service=auth_service,
    )

    assert response["status"] == "success"
    assert token_value not in caplog.text
    auth_service.forgot_password.assert_awaited_once_with("user@example.com")
