"""Unit tests for speech text preparation, language routing, and auth (no network)."""

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.speech import (
    MAX_INPUT_CHARS,
    detect_speech_language,
    prepare_speech_text,
    router,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db


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
