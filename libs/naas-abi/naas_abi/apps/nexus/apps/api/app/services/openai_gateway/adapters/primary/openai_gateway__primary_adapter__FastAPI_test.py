from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.openai_gateway.adapters.primary import (
    openai_gateway__primary_adapter__FastAPI as shim,
)


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(shim.router, prefix="/v1")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="user@example.com", name="User One"
    )

    async def _fake_stream(
        model: str, messages: object, thread_id: str
    ) -> AsyncGenerator[str, None]:
        for piece in ["Hello", " world"]:
            yield piece

    monkeypatch.setattr(shim, "_stream_agent_text", _fake_stream)
    monkeypatch.setattr(shim, "_list_agent_model_ids", lambda: ["aia", "support"])
    return TestClient(app)


def test_models(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.get("/v1/models")
    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()["data"]]
    assert "aia" in ids


def test_chat_completion_non_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "aia", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["choices"][0]["message"]["content"] == "Hello world"


def test_chat_completion_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "aia",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "data: [DONE]" in body
    contents: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: ") and "[DONE]" not in line:
            payload = json.loads(line[len("data: ") :])
            delta = payload["choices"][0]["delta"]
            if "content" in delta:
                contents.append(delta["content"])
    assert "".join(contents) == "Hello world"
