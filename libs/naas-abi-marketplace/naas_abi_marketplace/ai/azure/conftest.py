"""Fixtures for the azure module tests: no network, no Azure account.

``fake_identity`` replaces ``DefaultAzureCredential`` and
``get_bearer_token_provider`` in ``azure.identity`` and records how they were
called. ``http_requests`` answers every HTTP request in-process and keeps it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

TOKEN = "entra-id-token-for-tests"

CHAT_COMPLETION = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "pong"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}

EMBEDDINGS = {
    "object": "list",
    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
    "model": "text-embedding-3-large",
    "usage": {"prompt_tokens": 1, "total_tokens": 1},
}


@pytest.fixture(autouse=True)
def _no_azure_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """langchain and openai read these: a developer's shell must not leak in."""
    for name in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_AD_TOKEN",
        "AZURE_OPENAI_ENDPOINT",
        "OPENAI_API_KEY",
        "OPENAI_API_VERSION",
        "AZURE_CLIENT_ID",
    ):
        monkeypatch.delenv(name, raising=False)


@dataclass
class FakeIdentity:
    token: str = TOKEN
    credentials: list[dict[str, Any]] = field(default_factory=list)
    scopes: list[tuple[str, ...]] = field(default_factory=list)
    token_calls: int = 0

    def provider(self) -> str:
        self.token_calls += 1
        return self.token


@pytest.fixture
def fake_identity(monkeypatch: pytest.MonkeyPatch) -> FakeIdentity:
    identity = FakeIdentity()

    class FakeDefaultAzureCredential:
        def __init__(self, **kwargs: Any) -> None:
            identity.credentials.append(kwargs)

    def fake_get_bearer_token_provider(credential: Any, *scopes: str):
        assert isinstance(credential, FakeDefaultAzureCredential)
        identity.scopes.append(scopes)
        return identity.provider

    monkeypatch.setattr(
        "azure.identity.DefaultAzureCredential", FakeDefaultAzureCredential
    )
    monkeypatch.setattr(
        "azure.identity.get_bearer_token_provider", fake_get_bearer_token_provider
    )
    return identity


@pytest.fixture
def no_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any use of azure.identity fails the test."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("azure.identity must not be used with an API key")

    monkeypatch.setattr("azure.identity.DefaultAzureCredential", refuse)
    monkeypatch.setattr("azure.identity.get_bearer_token_provider", refuse)


@pytest.fixture
def http_requests(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handle_request(self: httpx.HTTPTransport, request: httpx.Request):
        seen.append(request)
        body = (
            EMBEDDINGS if request.url.path.endswith("/embeddings") else CHAT_COMPLETION
        )
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
    return seen
