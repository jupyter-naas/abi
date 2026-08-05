from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from naas_abi.apps.nexus.apps.api.app.services.integrations.github.service import (
    _DEVICE_STORE,
    DeviceSession,
    GitHubConnectService,
)


@pytest.fixture(autouse=True)
def clear_device_sessions() -> None:
    with _DEVICE_STORE.lock:
        _DEVICE_STORE.sessions.clear()
    yield
    with _DEVICE_STORE.lock:
        _DEVICE_STORE.sessions.clear()


@pytest.mark.asyncio
async def test_poll_device_flow_completes_and_writes_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")

    session = DeviceSession(
        session_id="sess-1",
        device_code="device-code",
        user_code="ABCD-1234",
        verification_uri="https://github.com/login/device",
        interval=5,
        expires_at=__import__("time").time() + 600,
        client_id="test-client-id",
    )
    with _DEVICE_STORE.lock:
        _DEVICE_STORE.sessions[session.session_id] = session

    poll_response = MagicMock()
    poll_response.json.return_value = {
        "access_token": "gho_device_token",
        "token_type": "bearer",
        "scope": "repo,read:user",
    }

    user_response = MagicMock()
    user_response.status_code = 200
    user_response.json.return_value = {"login": "octocat"}

    with patch(
        "naas_abi.apps.nexus.apps.api.app.services.integrations.github.service.httpx.AsyncClient"
    ) as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post.return_value = poll_response
        client.get.return_value = user_response
        client_cls.return_value = client

        result = await GitHubConnectService.poll_device_flow("sess-1")

    assert result["status"] == "complete"
    assert result["connected"] is True
    assert result["github_login"] == "octocat"
    assert "gho_device_token" in (tmp_path / ".env").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_start_device_flow_requires_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_OAUTH_CLIENT_ID", raising=False)
    with pytest.raises(RuntimeError, match="GitHub OAuth is not configured"):
        await GitHubConnectService.start_device_flow()
