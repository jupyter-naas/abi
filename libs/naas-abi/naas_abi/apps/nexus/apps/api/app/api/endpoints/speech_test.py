"""Unit tests for speech text preparation, language routing, and auth (no network)."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints import speech
from naas_abi.apps.nexus.apps.api.app.api.endpoints.speech import (
    MAX_INPUT_CHARS,
    detect_speech_language,
    prepare_speech_text,
    router,
)
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam


def test_prepare_speech_text_strips_markdown() -> None:
    raw = "# Title\n\n**Hello** [Naas](https://naas.ai) and `code`\n\n```python\nprint(1)\n```"
    assert prepare_speech_text(raw) == "Title Hello Naas and code."


def test_prepare_speech_text_truncates() -> None:
    raw = "a" * (MAX_INPUT_CHARS + 50)
    out = prepare_speech_text(raw)
    assert len(out) == MAX_INPUT_CHARS
    assert out.endswith("...")


def test_prepare_speech_text_empty() -> None:
    assert prepare_speech_text("   ") == ""
    assert prepare_speech_text("```\nonly code\n```") == ""


def test_detect_speech_language_french() -> None:
    text = "Bonjour Jeremy. Je t'entends parfaitement. Je vais très bien, merci."
    assert detect_speech_language(text) == "fr"


def test_detect_speech_language_english() -> None:
    text = "Hello Jeremy. I hear you perfectly. I am doing very well, thank you."
    assert detect_speech_language(text) == "en"


async def _no_db() -> AsyncIterator[None]:
    yield None


def test_unauthenticated_post_speech_returns_401() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/speech")
    app.dependency_overrides[get_db] = _no_db
    response = TestClient(app).post("/api/speech", json={})
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers


def _signed_in_client(user_id: str) -> TestClient:
    from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
        User,
        get_current_user_required,
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/speech")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user_id, email="u@example.com"
    )
    return TestClient(app)


@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
def test_every_role_may_read_aloud(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch, user: str
) -> None:
    # No backend configured: the answer is the route's own, past authorization.
    monkeypatch.setattr(speech, "resolve_speech_backend", lambda: None)

    response = _signed_in_client(user).post("/api/speech", json={"text": "hello"})

    assert response.status_code == 500
    assert "No speech API key" in response.json()["error"]


def test_a_user_with_no_workspace_may_not_use_speech(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(speech, "resolve_speech_backend", lambda: pytest.fail("reached"))

    response = _signed_in_client("stranger").post("/api/speech", json={"text": "hello"})

    assert response.status_code == 403


def test_the_workspace_named_by_the_client_decides(
    team: NexusIam, monkeypatch: pytest.MonkeyPatch
) -> None:
    team.workspace("org-1", "ws-2")
    monkeypatch.setattr(speech, "resolve_speech_backend", lambda: None)
    client = _signed_in_client("member")

    assert client.post("/api/speech?workspace_id=ws-1", json={"text": "hello"}).status_code == 500
    assert client.post("/api/speech?workspace_id=ws-2", json={"text": "hello"}).status_code == 403
    assert client.post("/api/speech/?workspace_id=ws-2", json={"text": "hello"}).status_code == 403


def test_speech_needs_the_chat_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["files"], role_baseline={"owner": ["files"], "member": ["files"]}
    )
    nexus = NexusIam(flags)
    nexus.grant("member", "member", nexus.workspace("org-1", "ws-1"))
    monkeypatch.setattr(speech, "resolve_speech_backend", lambda: pytest.fail("reached"))

    with nexus.installed():
        response = _signed_in_client("member").post("/api/speech", json={"text": "hello"})

    assert response.status_code == 403
