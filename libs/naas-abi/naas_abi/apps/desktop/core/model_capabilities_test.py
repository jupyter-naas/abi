"""Tests for model tool-capability heuristics."""

from __future__ import annotations

from desktop.core.model_capabilities import (
    format_tools_unsupported_error,
    model_supports_tools,
    ollama_model_supports_tools,
    provider_model_supports_tools,
)


def test_phi_denied() -> None:
    assert ollama_model_supports_tools("phi:latest") is False
    assert model_supports_tools("ollama/phi:latest") is False


def test_qwen_and_llama_allowed() -> None:
    assert ollama_model_supports_tools("qwen2.5-coder:7b") is True
    assert ollama_model_supports_tools("llama3.1:8b") is True
    assert model_supports_tools("ollama/qwen3:8b") is True


def test_cloud_providers_default_capable() -> None:
    assert provider_model_supports_tools("openai", "gpt-4o") is True
    assert provider_model_supports_tools("anthropic", "claude-sonnet-4") is True


def test_denylisted_cloud_model() -> None:
    assert provider_model_supports_tools("openai", "gpt-5-chat-latest") is False


def test_format_tools_unsupported_error_includes_model() -> None:
    message = format_tools_unsupported_error("ollama/phi:latest")
    assert "phi:latest" in message
    assert "tool-capable" in message


def test_first_tool_capable_model_prefers_ollama_over_cloud() -> None:
    from desktop.harness.models import HarnessModel, HarnessProvider
    from desktop.core.model_capabilities import first_tool_capable_model_ref

    providers = [
        HarnessProvider(
            id="openai",
            name="OpenAI",
            models=(HarnessModel(id="o3", name="o3"),),
        ),
        HarnessProvider(
            id="ollama",
            name="Ollama",
            models=(HarnessModel(id="gemma4:latest", name="gemma4:latest"),),
        ),
    ]
    assert first_tool_capable_model_ref(providers) == "ollama/gemma4:latest"
