"""Unauthenticated transcribe requests must 401 before audio handling."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.transcribe import (
    DEFAULT_DOMAIN_VOCABULARY,
    _get_http_client,
    build_transcription_prompt,
    normalize_transcription_language,
    router,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db


async def _no_db() -> AsyncIterator[None]:
    yield None


def test_unauthenticated_post_transcribe_returns_401() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/transcribe")
    app.dependency_overrides[get_db] = _no_db
    response = TestClient(app).post("/api/transcribe", json={})
    assert response.status_code == 401
    assert "Authorization" not in response.request.headers


def test_build_transcription_prompt_combines_domain_and_agent_vocabulary() -> None:
    assert build_transcription_prompt(None) == DEFAULT_DOMAIN_VOCABULARY
    combined = build_transcription_prompt("Bob, Forvis Mazars")
    assert DEFAULT_DOMAIN_VOCABULARY in combined
    assert "Bob, Forvis Mazars" in combined


def test_normalize_transcription_language_keeps_iso_639_1_only() -> None:
    assert normalize_transcription_language("fr-FR") == "fr"
    assert normalize_transcription_language("en_US") == "en"
    assert normalize_transcription_language(" DE ") == "de"
    assert normalize_transcription_language(None) is None
    assert normalize_transcription_language("") is None
    assert normalize_transcription_language("auto") is None
    assert normalize_transcription_language("zh-Hans-CN") == "zh"


def test_transcribe_http_client_reuses_warm_pool() -> None:
    c1 = _get_http_client()
    c2 = _get_http_client()
    assert c1 is c2
