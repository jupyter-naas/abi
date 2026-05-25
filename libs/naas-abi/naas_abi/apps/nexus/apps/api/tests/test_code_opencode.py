"""Integration tests for the Code section OpenCode proxy (/api/opencode).

These endpoints reach an external OpenCode server (host.docker.internal:4005
when the ABI stack runs in Docker). Tests skip gracefully when OpenCode is
not running.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _require_opencode(client, headers):
    response = await client.get("/api/opencode/health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    if not data.get("healthy"):
        pytest.skip(data.get("error") or "opencode not running")
    return data


class TestCodeOpencode:
    async def test_health(self, client, test_user):
        data = await _require_opencode(client, test_user["headers"])
        assert data["healthy"] is True

    async def test_providers_default_model_and_sessions(self, client, test_user):
        await _require_opencode(client, test_user["headers"])

        providers = await client.get("/api/opencode/providers", headers=test_user["headers"])
        assert providers.status_code == 200

        default_model = await client.get(
            "/api/opencode/default-model",
            headers=test_user["headers"],
        )
        assert default_model.status_code == 200

        sessions = await client.get("/api/opencode/sessions", headers=test_user["headers"])
        assert sessions.status_code == 200

    async def test_requires_auth(self, client):
        response = await client.get("/api/opencode/health")
        assert response.status_code == 401
