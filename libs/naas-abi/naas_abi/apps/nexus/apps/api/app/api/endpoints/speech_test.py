"""Unit tests for speech text preparation, language routing, and auth (no network)."""

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.speech import (
    MAX_INPUT_CHARS,
    OPENAI_SPEECH_URL,
    OPENAI_TTS_MODEL,
    OPENROUTER_NARRATION_MODEL,
    OPENROUTER_NARRATION_MODEL_FAST,
    OPENROUTER_SPEECH_URL,
    OPENROUTER_TTS_MODEL,
    OPENROUTER_TTS_VOICE,
    _get_http_client,
    _synthesize_fast,
    detect_speech_language,
    fast_speech_attempts,
    prepare_speech_text,
    resolve_model_and_voice_for_text,
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


def test_resolve_model_and_voice_fast_mode_prefers_flash_for_long_voice_call_sentences(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.api.endpoints.speech._secret",
        lambda _name: None,
    )
    long_sentence = "Hello Jeremy, " + ("this is a detailed spoken sentence " * 8)
    model_normal, _, _ = resolve_model_and_voice_for_text(
        long_sentence,
        default_model=OPENROUTER_TTS_MODEL,
        default_voice=OPENROUTER_TTS_VOICE,
        explicit_model=None,
        explicit_voice=None,
        explicit_language="en",
        fast=False,
    )
    model_fast, _, _ = resolve_model_and_voice_for_text(
        long_sentence,
        default_model=OPENROUTER_TTS_MODEL,
        default_voice=OPENROUTER_TTS_VOICE,
        explicit_model=None,
        explicit_voice=None,
        explicit_language="en",
        fast=True,
    )
    assert model_normal == OPENROUTER_NARRATION_MODEL
    assert model_fast == OPENROUTER_NARRATION_MODEL_FAST


_SPEECH = "naas_abi.apps.nexus.apps.api.app.api.endpoints.speech"
_KOKORO = (OPENROUTER_SPEECH_URL, "sk-or-x", OPENROUTER_TTS_MODEL, OPENROUTER_TTS_VOICE)


def _secrets(values: dict[str, str]):
    return lambda name: values.get(name)


def test_fast_speech_attempts_fall_back_to_flash_then_openai(monkeypatch) -> None:
    monkeypatch.setattr(f"{_SPEECH}._secret", _secrets({"OPENAI_API_KEY": "sk-proj-x"}))
    monkeypatch.setattr(f"{_SPEECH}._slow_model_until", {})
    attempts = fast_speech_attempts(_KOKORO, "en")
    assert [a[2] for a in attempts] == [
        OPENROUTER_TTS_MODEL,
        OPENROUTER_NARRATION_MODEL_FAST,
        OPENAI_TTS_MODEL,
    ]
    assert attempts[1][3] == "en-US-Harper:MAI-Voice-2"
    assert attempts[2][0] == OPENAI_SPEECH_URL


def test_fast_speech_attempts_skip_a_model_cooling_down(monkeypatch) -> None:
    monkeypatch.setattr(f"{_SPEECH}._secret", _secrets({}))
    monkeypatch.setattr(
        f"{_SPEECH}._slow_model_until", {OPENROUTER_TTS_MODEL: time.monotonic() + 30}
    )
    attempts = fast_speech_attempts(_KOKORO, "en")
    assert [a[2] for a in attempts] == [OPENROUTER_NARRATION_MODEL_FAST]


def test_synthesize_fast_moves_on_after_a_stalled_model(monkeypatch) -> None:
    slow: dict[str, float] = {}
    monkeypatch.setattr(f"{_SPEECH}._slow_model_until", slow)

    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["model"] == OPENROUTER_TTS_MODEL:
            raise httpx.ReadTimeout("stalled", request=request)
        return httpx.Response(200, content=b"ID3", headers={"content-type": "audio/mpeg"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(f"{_SPEECH}._get_http_client", lambda: client)
    flash = (OPENROUTER_SPEECH_URL, "sk-or-x", OPENROUTER_NARRATION_MODEL_FAST, "v")
    response = asyncio.run(_synthesize_fast([_KOKORO, flash], "Hello.", "en"))
    assert response.status_code == 200
    assert response.headers["X-TTS-Model"] == OPENROUTER_NARRATION_MODEL_FAST
    assert OPENROUTER_TTS_MODEL in slow


def test_speech_http_client_reuses_warm_pool() -> None:
    c1 = _get_http_client()
    c2 = _get_http_client()
    assert c1 is c2


async def _no_db() -> AsyncIterator[None]:
    yield None


def test_unauthenticated_post_speech_returns_401() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/speech")
    app.dependency_overrides[get_db] = _no_db
    response = TestClient(app).post("/api/speech", json={})
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers
