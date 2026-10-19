"""Unauthenticated transcribe requests must 401 before audio handling."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints import transcribe
from naas_abi.apps.nexus.apps.api.app.api.endpoints.transcribe import router
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam


async def _no_db() -> AsyncIterator[None]:
    yield None


def test_unauthenticated_post_transcribe_returns_401() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/transcribe")
    app.dependency_overrides[get_db] = _no_db
    response = TestClient(app).post("/api/transcribe", json={})
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers


def _signed_in_client(user_id: str) -> TestClient:
    from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
        User,
        get_current_user_required,
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/transcribe")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user_id, email="u@example.com"
    )
    return TestClient(app)


def _post(client: TestClient, query: str = ""):
    return client.post(
        f"/api/transcribe{query}",
        files={"audio": ("clip.webm", b"audio", "audio/webm")},
        data={"conversation_id": "conv-1"},
    )


@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
def test_every_role_may_dictate(team: NexusIam, monkeypatch: pytest.MonkeyPatch, user: str) -> None:
    monkeypatch.setattr(transcribe, "resolve_transcription_backend", lambda: None)

    response = _post(_signed_in_client(user))

    assert response.status_code == 500
    assert "No transcription API key" in response.json()["error"]


def test_a_user_with_no_workspace_may_not_dictate(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(transcribe, "resolve_transcription_backend", lambda: pytest.fail("reached"))

    assert _post(_signed_in_client("stranger")).status_code == 403


def test_the_workspace_named_by_the_client_decides(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    team.workspace("org-1", "ws-2")
    monkeypatch.setattr(transcribe, "resolve_transcription_backend", lambda: None)
    client = _signed_in_client("member")

    assert _post(client, "?workspace_id=ws-1").status_code == 500
    assert _post(client, "?workspace_id=ws-2").status_code == 403


def test_dictation_needs_the_chat_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["files"], role_baseline={"owner": ["files"], "member": ["files"]}
    )
    nexus = NexusIam(flags)
    nexus.grant("member", "member", nexus.workspace("org-1", "ws-1"))
    monkeypatch.setattr(transcribe, "resolve_transcription_backend", lambda: pytest.fail("reached"))

    with nexus.installed():
        response = _post(_signed_in_client("member"))

    assert response.status_code == 403
