"""Tests for the Ollama integration (probe, opencode config sync, API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from desktop.integrations import (
    DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_SETTING_KEY,
    OpencodeConfigError,
    create_integrations_router,
    probe_ollama,
    sync_opencode_config,
)
from desktop.store import DesktopStore

TAGS_PAYLOAD: dict[str, Any] = {
    "models": [
        {
            "name": "phi:latest",
            "model": "phi:latest",
            "modified_at": "2026-06-01T10:00:00.000Z",
            "size": 1600000000,
            "details": {"parameter_size": "3B", "quantization_level": "Q4_0"},
        },
        {
            "name": "llama3.2:3b",
            "model": "llama3.2:3b",
            "modified_at": "2026-06-01T10:00:00.000Z",
            "size": 2019393189,
            "digest": "a80c4f17acd5",
            "details": {
                "format": "gguf",
                "family": "llama",
                "parameter_size": "3.2B",
                "quantization_level": "Q4_K_M",
            },
        },
        {
            "name": "qwen3:8b",
            "model": "qwen3:8b",
            "modified_at": "2026-05-20T08:30:00.000Z",
            "size": 5200000000,
            "digest": "b91d5f28bce6",
            "details": {"parameter_size": "8.2B", "quantization_level": "Q4_0"},
        },
    ]
}


def ollama_transport(
    payload: dict[str, Any] | None = None, status_code: int = 200
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(status_code, json=payload or {})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def offline_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    return httpx.MockTransport(handler)


# -- probe --------------------------------------------------------------


class TestProbeOllama:
    @pytest.mark.asyncio
    async def test_connected_parses_models(self) -> None:
        result = await probe_ollama(
            "http://localhost:11434", transport=ollama_transport(TAGS_PAYLOAD)
        )
        assert result["connected"] is True
        assert result["error"] is None
        assert result["models"][0]["name"] == "phi:latest"
        assert result["models"][0]["supports_tools"] is False
        assert result["models"][1]["name"] == "llama3.2:3b"
        assert result["models"][1]["supports_tools"] is True
        assert result["models"][2]["name"] == "qwen3:8b"

    @pytest.mark.asyncio
    async def test_trailing_slash_base_url(self) -> None:
        result = await probe_ollama(
            "http://localhost:11434/", transport=ollama_transport(TAGS_PAYLOAD)
        )
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_unreachable_reports_disconnected(self) -> None:
        result = await probe_ollama(
            "http://localhost:11434", transport=offline_transport()
        )
        assert result["connected"] is False
        assert result["models"] == []
        assert "refused" in result["error"]

    @pytest.mark.asyncio
    async def test_http_error_reports_disconnected(self) -> None:
        result = await probe_ollama(
            "http://localhost:11434", transport=ollama_transport(status_code=500)
        )
        assert result["connected"] is False
        assert result["error"]

    @pytest.mark.asyncio
    async def test_malformed_payload_yields_no_models(self) -> None:
        result = await probe_ollama(
            "http://localhost:11434",
            transport=ollama_transport({"models": [42, {"no_name": True}]}),
        )
        assert result["connected"] is True
        assert result["models"] == []


# -- opencode.json sync ----------------------------------------------------


class TestSyncOpencodeConfig:
    def models(self) -> list[dict[str, Any]]:
        return [
            {"name": "llama3.2:3b", "size": 1, "parameter_size": "3.2B"},
            {"name": "qwen3:8b", "size": 2, "parameter_size": "8.2B"},
        ]

    def test_sync_skips_non_tool_models(self, tmp_path: Path) -> None:
        models = [
            {"name": "phi:latest"},
            {"name": "llama3.2:3b", "size": 1, "parameter_size": "3.2B"},
            {"name": "qwen3:8b", "size": 2, "parameter_size": "8.2B"},
        ]
        changed = sync_opencode_config(
            tmp_path, "http://localhost:11434", models
        )
        assert changed is True
        config = json.loads((tmp_path / "opencode.json").read_text())
        assert set(config["provider"]["ollama"]["models"]) == {
            "llama3.2:3b",
            "qwen3:8b",
        }

    def test_creates_fresh_config(self, tmp_path: Path) -> None:
        changed = sync_opencode_config(
            tmp_path, "http://localhost:11434", self.models()
        )
        assert changed is True
        config = json.loads((tmp_path / "opencode.json").read_text())
        ollama = config["provider"]["ollama"]
        assert ollama["npm"] == "@ai-sdk/openai-compatible"
        assert ollama["options"]["baseURL"] == "http://localhost:11434/v1"
        assert set(ollama["models"]) == {"llama3.2:3b", "qwen3:8b"}

    def test_preserves_unrelated_keys(self, tmp_path: Path) -> None:
        existing = {
            "$schema": "https://opencode.ai/config.json",
            "theme": "dark",
            "provider": {"anthropic": {"options": {"apiKey": "{env:KEY}"}}},
        }
        (tmp_path / "opencode.json").write_text(json.dumps(existing))
        sync_opencode_config(tmp_path, "http://localhost:11434", self.models())
        config = json.loads((tmp_path / "opencode.json").read_text())
        assert config["theme"] == "dark"
        assert config["provider"]["anthropic"] == {"options": {"apiKey": "{env:KEY}"}}
        assert "ollama" in config["provider"]

    def test_preserves_user_ollama_customization(self, tmp_path: Path) -> None:
        existing = {
            "provider": {
                "ollama": {
                    "name": "My Ollama",
                    "options": {"headers": {"X-Custom": "1"}},
                    "models": {
                        "llama3.2:3b": {
                            "name": "Llama tuned",
                            "limit": {"context": 8192},
                        },
                        "hand-added:1b": {"name": "Hand added"},
                    },
                }
            }
        }
        (tmp_path / "opencode.json").write_text(json.dumps(existing))
        sync_opencode_config(tmp_path, "http://localhost:11434", self.models())
        ollama = json.loads((tmp_path / "opencode.json").read_text())["provider"][
            "ollama"
        ]
        # Forced keys required for the provider to work.
        assert ollama["npm"] == "@ai-sdk/openai-compatible"
        assert ollama["options"]["baseURL"] == "http://localhost:11434/v1"
        # User customization survives.
        assert ollama["name"] == "My Ollama"
        assert ollama["options"]["headers"] == {"X-Custom": "1"}
        assert ollama["models"]["llama3.2:3b"]["name"] == "Llama tuned"
        assert ollama["models"]["llama3.2:3b"]["limit"] == {"context": 8192}
        assert "hand-added:1b" in ollama["models"]
        # Newly installed model was added.
        assert "qwen3:8b" in ollama["models"]

    def test_idempotent_returns_unchanged(self, tmp_path: Path) -> None:
        assert sync_opencode_config(tmp_path, "http://x:1", self.models()) is True
        assert sync_opencode_config(tmp_path, "http://x:1", self.models()) is False

    def test_base_url_change_is_a_change(self, tmp_path: Path) -> None:
        sync_opencode_config(tmp_path, "http://x:1", self.models())
        assert sync_opencode_config(tmp_path, "http://y:2", self.models()) is True

    def test_corrupt_config_raises_and_is_untouched(self, tmp_path: Path) -> None:
        (tmp_path / "opencode.json").write_text("{not json")
        with pytest.raises(OpencodeConfigError):
            sync_opencode_config(tmp_path, "http://localhost:11434", self.models())
        assert (tmp_path / "opencode.json").read_text() == "{not json"


# -- API router --------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> DesktopStore:
    s = DesktopStore(tmp_path / "desktop.db")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    s.update_settings({"workspace_root": str(workspace)})
    yield s
    s.close()


def make_client(
    store: DesktopStore,
    transport: httpx.MockTransport,
    on_config_change=None,
) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_integrations_router(
            store, transport=transport, on_config_change=on_config_change
        )
    )
    return TestClient(app)


class TestIntegrationsApi:
    def test_list_connected(self, store: DesktopStore) -> None:
        client = make_client(store, ollama_transport(TAGS_PAYLOAD))
        payload = client.get("/api/integrations").json()
        (ollama,) = payload["integrations"]
        assert ollama["id"] == "ollama"
        assert ollama["name"] == "Ollama"
        assert ollama["connected"] is True
        assert ollama["base_url"] == DEFAULT_OLLAMA_BASE_URL
        assert [m["name"] for m in ollama["models"]] == [
            "phi:latest",
            "llama3.2:3b",
            "qwen3:8b",
        ]
        # opencode.json was synced into the workspace.
        workspace = Path(store.get_settings()["workspace_root"])
        config = json.loads((workspace / "opencode.json").read_text())
        assert "ollama" in config["provider"]

    def test_list_disconnected(self, store: DesktopStore) -> None:
        client = make_client(store, offline_transport())
        (ollama,) = client.get("/api/integrations").json()["integrations"]
        assert ollama["connected"] is False
        assert ollama["models"] == []
        assert ollama["error"]
        workspace = Path(store.get_settings()["workspace_root"])
        assert not (workspace / "opencode.json").exists()

    def test_put_updates_base_url_and_persists(self, store: DesktopStore) -> None:
        client = make_client(store, ollama_transport(TAGS_PAYLOAD))
        response = client.put(
            "/api/integrations/ollama", json={"base_url": "http://127.0.0.1:9999/"}
        )
        payload = response.json()
        assert payload["base_url"] == "http://127.0.0.1:9999"
        assert store.get_settings()[OLLAMA_SETTING_KEY] == "http://127.0.0.1:9999"
        assert payload["connected"] is True

    def test_put_rejects_blank_base_url(self, store: DesktopStore) -> None:
        client = make_client(store, ollama_transport(TAGS_PAYLOAD))
        response = client.put("/api/integrations/ollama", json={"base_url": "   "})
        assert response.status_code == 422

    def test_config_change_callback_fires_once(self, store: DesktopStore) -> None:
        calls: list[bool] = []
        client = make_client(
            store,
            ollama_transport(TAGS_PAYLOAD),
            on_config_change=lambda: calls.append(True),
        )
        client.get("/api/integrations")
        assert len(calls) == 1
        # Second probe with identical state: config unchanged, no restart.
        client.get("/api/integrations")
        assert len(calls) == 1

    def test_no_callback_when_offline(self, store: DesktopStore) -> None:
        calls: list[bool] = []
        client = make_client(
            store, offline_transport(), on_config_change=lambda: calls.append(True)
        )
        client.get("/api/integrations")
        assert calls == []

    def test_corrupt_opencode_config_reported_not_fatal(
        self, store: DesktopStore
    ) -> None:
        workspace = Path(store.get_settings()["workspace_root"])
        (workspace / "opencode.json").write_text("{not json")
        client = make_client(store, ollama_transport(TAGS_PAYLOAD))
        (ollama,) = client.get("/api/integrations").json()["integrations"]
        assert ollama["connected"] is True
        assert "opencode.json" in ollama["error"]
        assert (workspace / "opencode.json").read_text() == "{not json"
