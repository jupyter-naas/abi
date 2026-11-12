"""A chat request picks a provider type and model; the workspace configures the rest.

Endpoints, keys and account ids in a request are ignored: a turn reaches only
the providers the workspace (its agent rows, secrets and ABI server) or the
platform's Ollama configure, and never spends the platform's own keys.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services import provider_runtime
from naas_abi.apps.nexus.apps.api.app.services.chat import service as chat_service
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (  # noqa: E501
    to_complete_chat_input,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (  # noqa: E501
    ChatRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import (
    ChatService,
    ProviderNotConfiguredError,
)

SECRET = "listener-value-5c1e"


class _Listener:
    def __init__(self) -> None:
        self.hits: list[str] = []
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                listener.hits.append(self.path)
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                body = json.dumps({"completion": SECRET}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        threading.Thread(target=self._httpd.serve_forever, args=(0.05,), daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    srv = _Listener()
    yield srv
    srv.close()


@pytest.fixture
def ollama_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def offline(endpoint: str | None = None) -> dict:
        return {"status": "offline", "models": [], "multimodal_models": []}

    monkeypatch.setattr(chat_service, "check_ollama_status", offline)


def _request(provider: dict) -> ChatRequest:
    return ChatRequest.model_validate(
        {"workspace_id": "ws-1", "message": "hi", "provider": provider}
    )


def _service() -> ChatService:
    adapter = SimpleNamespace(
        get_conversation_by_id_for_user=AsyncMock(
            return_value=SimpleNamespace(id="conv-1", workspace_id="ws-1", user_id="u-1")
        ),
        get_conversation_by_id=AsyncMock(return_value=None),
        create_conversation=AsyncMock(return_value=SimpleNamespace(id="conv-1")),
        get_agent_by_id=AsyncMock(return_value=None),
        create_message=AsyncMock(return_value="msg-1"),
        touch_conversation=AsyncMock(),
    )
    service = ChatService(adapter=adapter)
    service.build_provider_messages_with_agents = AsyncMock(  # type: ignore[method-assign]
        return_value=[SimpleNamespace(role="user", content="hi", images=None)]
    )
    service.build_system_prompt = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.build_abi_injection_preamble = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._inject_chat_vector_context = lambda provider_messages, **_: (  # type: ignore[method-assign]
        provider_messages,
        [],
    )
    service.touch_conversation = AsyncMock()  # type: ignore[method-assign]
    return service


def test_chat_request_keeps_no_endpoint_or_key() -> None:
    request = _request(
        {
            "id": "x",
            "name": "x",
            "type": "abi",
            "enabled": True,
            "endpoint": "http://127.0.0.1:1",
            "api_key": "client-key",
            "account_id": "client-account",
            "model": "agent",
        }
    )
    assert request.provider is not None
    dumped = request.provider.model_dump()
    assert {"endpoint", "api_key", "account_id"}.isdisjoint(dumped)
    provider = to_complete_chat_input(request).provider
    assert provider is not None
    assert not hasattr(provider, "endpoint")
    assert not hasattr(provider, "api_key")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["abi", "custom", "ollama"])
async def test_chat_turn_keeps_to_workspace_providers(
    listener: _Listener, ollama_offline: None, kind: str
) -> None:
    request = _request(
        {
            "id": "x",
            "name": "x",
            "type": kind,
            "enabled": True,
            "endpoint": listener.url,
            "model": "../../admin/config?from=",
        }
    )
    result = await _service().complete_chat_request(
        user_id="u-1", request=to_complete_chat_input(request), now=datetime.now()
    )
    assert listener.hits == []
    assert SECRET not in (result.assistant_content or "")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["openai", "anthropic", "cloudflare"])
async def test_chat_turn_keeps_platform_keys_to_the_platform(
    ollama_offline: None, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """A provider a request names, with no key, is not given the platform's key."""
    built: list[dict] = []

    class Recorder:
        def __init__(self, api_key: str | None = None, **_: object) -> None:
            built.append({"api_key": api_key})
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **_: object) -> object:
            message = SimpleNamespace(content="ok")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                content=[SimpleNamespace(text="ok")],
            )

    settings = provider_runtime.nexus_config.settings
    monkeypatch.setattr(settings, "openai_api_key", "PLATFORM-KEY", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "PLATFORM-KEY", raising=False)
    monkeypatch.setattr(settings, "cloudflare_api_token", "PLATFORM-KEY", raising=False)
    monkeypatch.setattr(settings, "cloudflare_account_id", "PLATFORM-ACCOUNT", raising=False)
    monkeypatch.setattr(provider_runtime, "HAS_OPENAI", True)
    monkeypatch.setattr(provider_runtime, "HAS_ANTHROPIC", True)
    monkeypatch.setattr(provider_runtime, "openai", SimpleNamespace(OpenAI=Recorder), raising=False)
    monkeypatch.setattr(
        provider_runtime, "anthropic", SimpleNamespace(Anthropic=Recorder), raising=False
    )

    request = _request({"id": "x", "name": "x", "type": kind, "enabled": True, "model": "o1-pro"})
    service = ChatService(adapter=SimpleNamespace(get_agent_by_id=AsyncMock(return_value=None)))
    with pytest.raises(ProviderNotConfiguredError):
        await service.resolve_provider(
            provider=to_complete_chat_input(request).provider,
            has_images=False,
            agent_id=None,
            workspace_id="ws-1",
        )

    # Even handed a keyless configuration directly, the runtime does not
    # reach for the platform's key.
    config = provider_runtime.ProviderConfig(
        id="x", name="x", type=kind, enabled=True, model="o1-pro"
    )
    with pytest.raises(ValueError):
        await provider_runtime.complete_chat(
            [provider_runtime.Message(role="user", content="hi")],
            config,
            None,
            injection_preamble=None,
        )
    assert all(b["api_key"] != "PLATFORM-KEY" for b in built)


@pytest.mark.asyncio
async def test_chat_ollama_selection_keeps_the_platform_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def online(endpoint: str | None = None) -> dict:
        return {"status": "online", "models": ["qwen3:8b"], "multimodal_models": []}

    monkeypatch.setattr(chat_service, "check_ollama_status", online)
    monkeypatch.setattr(chat_service, "resolve_endpoint", lambda: "http://ollama.platform:11434")
    service = ChatService(adapter=SimpleNamespace(get_agent_by_id=AsyncMock(return_value=None)))

    installed = _request(
        {
            "id": "x",
            "name": "x",
            "type": "ollama",
            "enabled": True,
            "endpoint": "http://127.0.0.1:1",
            "model": "qwen3:8b",
        }
    )
    resolved = await service.resolve_provider(
        provider=to_complete_chat_input(installed).provider, has_images=False
    )
    assert resolved is not None
    assert (resolved.endpoint, resolved.model) == ("http://ollama.platform:11434", "qwen3:8b")

    missing = _request(
        {"id": "x", "name": "x", "type": "ollama", "enabled": True, "model": "not-installed"}
    )
    resolved = await service.resolve_provider(
        provider=to_complete_chat_input(missing).provider, has_images=False
    )
    assert resolved is None or resolved.model != "not-installed"


@pytest.fixture
def ollama_online(monkeypatch: pytest.MonkeyPatch) -> None:
    async def online(endpoint: str | None = None) -> dict:
        return {"status": "online", "models": ["qwen3:8b"], "multimodal_models": []}

    monkeypatch.setattr(chat_service, "check_ollama_status", online)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["openai", "anthropic", "cloudflare", "custom", "perplexity"])
async def test_chat_turn_keeps_a_named_provider_or_says_it_is_not_configured(
    ollama_online: None, kind: str
) -> None:
    """A provider the workspace does not configure is an error, not another model."""
    request = _request({"id": "x", "name": "x", "type": kind, "enabled": True, "model": "m"})
    result = await _service().complete_chat_request(
        user_id="u-1", request=to_complete_chat_input(request), now=datetime.now()
    )
    assert "not configured for the workspace" in (result.assistant_content or "")
    assert result.provider_used is None


def _agent_row(provider: str, model_id: str = "m-1") -> SimpleNamespace:
    return SimpleNamespace(
        id="agent-1",
        workspace_id="ws-1",
        name="Agent",
        class_name=None,
        model_id=model_id,
        provider=provider,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "secrets", "expected"),
    [
        (
            "cloudflare",
            {"CLOUDFLARE_API_TOKEN": "cf-token", "CLOUDFLARE_ACCOUNT_ID": "cf-account"},
            ("cloudflare", None, "cf-token", "cf-account"),
        ),
        (
            "perplexity",
            {"PERPLEXITY_API_KEY": "pplx-key"},
            ("perplexity", "https://api.perplexity.ai", "pplx-key", None),
        ),
    ],
)
async def test_chat_providers_keep_to_workspace_secrets(
    monkeypatch: pytest.MonkeyPatch, kind: str, secrets: dict, expected: tuple
) -> None:
    monkeypatch.setattr(chat_service, "decrypt_secret_value", lambda value: value)
    service = ChatService(adapter=SimpleNamespace())
    service.get_agent = AsyncMock(return_value=_agent_row(kind))  # type: ignore[method-assign]

    async def secret(workspace_id: str, key: str):
        assert workspace_id == "ws-1"
        value = secrets.get(key)
        return SimpleNamespace(encrypted_value=value) if value else None

    service.get_workspace_secret = secret  # type: ignore[method-assign]
    request = _request({"id": "x", "name": "x", "type": kind, "enabled": True, "model": "m"})
    resolved = await service.resolve_provider(
        provider=to_complete_chat_input(request).provider,
        has_images=False,
        agent_id="agent-1",
        workspace_id="ws-1",
    )
    assert resolved is not None
    assert (resolved.type, resolved.endpoint, resolved.api_key, resolved.account_id) == expected
    assert resolved.model == "m-1"

    # Without the workspace's secrets, the named provider is not configured.
    secrets.clear()
    with pytest.raises(ProviderNotConfiguredError):
        await service.resolve_provider(
            provider=to_complete_chat_input(request).provider,
            has_images=False,
            agent_id="agent-1",
            workspace_id="ws-1",
        )
