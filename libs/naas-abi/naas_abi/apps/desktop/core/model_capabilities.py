"""Heuristics for whether a model supports opencode agent tool calling.

ABI Desktop routes chat through opencode agents (``plan`` / ``build``), which
require models that can invoke tools. Cloud providers are assumed capable
unless denylisted; local Ollama models are checked against known patterns.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

# Models / families that cannot drive opencode agent tools.
_DENYLIST: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|[/:_-])phi([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])gemma([2-3]?)([/:_-]|$)", re.I),
    re.compile(r"gpt-5-chat", re.I),
    re.compile(r"chat-latest", re.I),
    re.compile(r"(^|[/:_-])tinyllama([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])neural-chat([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])orca-mini([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])vicuna([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])wizardlm([/:_-]|$)", re.I),
    re.compile(r"(^|[/:_-])stablelm([/:_-]|$)", re.I),
)

# Preferred local default when installed (canonical ref for settings / UI).
PREFERRED_DEFAULT_MODEL_REF = "ollama/qwen2.5-coder:7b"

_PREFERRED_OLLAMA_MODEL = re.compile(r"qwen2\.5-coder", re.I)

# Ollama models known to work with tool calling in opencode.
_OLLAMA_ALLOWLIST: tuple[re.Pattern[str], ...] = (
    re.compile(r"qwen", re.I),
    re.compile(r"llama3", re.I),
    re.compile(r"llama3\.[12]", re.I),
    re.compile(r"deepseek", re.I),
    re.compile(r"command-r", re.I),
    re.compile(r"codellama", re.I),
    re.compile(r"granite", re.I),
    re.compile(r"hermes", re.I),
    re.compile(r"functionary", re.I),
    re.compile(r"firefunction", re.I),
    re.compile(r"mistral-nemo", re.I),
    re.compile(r"gemma4", re.I),
)

_CLOUD_TOOL_CAPABLE_PROVIDERS = frozenset(
    {
        "openai",
        "anthropic",
        "google",
        "gemini",
        "mistral",
        "deepseek",
        "xai",
        "openrouter",
        "groq",
        "cohere",
    }
)


class _ProviderLike(Protocol):
    id: str
    models: tuple[Any, ...]


def _model_id_denied(model_id: str) -> bool:
    return any(pattern.search(model_id) for pattern in _DENYLIST)


def ollama_model_supports_tools(model_id: str) -> bool:
    """Return whether an installed Ollama model can run opencode agents."""
    if _model_id_denied(model_id):
        return False
    return any(pattern.search(model_id) for pattern in _OLLAMA_ALLOWLIST)


def provider_model_supports_tools(provider_id: str, model_id: str) -> bool:
    """Return whether a provider/model pair can run opencode agents."""
    if _model_id_denied(model_id):
        return False
    if provider_id == "ollama":
        return ollama_model_supports_tools(model_id)
    if provider_id in _CLOUD_TOOL_CAPABLE_PROVIDERS:
        return True
    # Unknown providers: optimistic unless explicitly denylisted.
    return True


def model_supports_tools(model_ref: str | None) -> bool:
    """Return whether a ``provider/model`` ref can run opencode agents."""
    if not model_ref or "/" not in model_ref:
        return True
    provider_id, model_id = model_ref.split("/", 1)
    provider_id = provider_id.strip()
    model_id = model_id.strip()
    if not provider_id or not model_id:
        return True
    return provider_model_supports_tools(provider_id, model_id)


def _ollama_model_name(model: Any) -> str | None:
    if isinstance(model, dict):
        raw = model.get("name") or model.get("id")
    else:
        raw = getattr(model, "name", None) or getattr(model, "id", None)
    if not raw:
        return None
    name = str(raw).strip()
    return name or None


def preferred_ollama_model_ref(models: list[Any]) -> str | None:
    """Return ``ollama/<name>`` for an installed qwen2.5-coder, if any."""
    for model in models:
        name = _ollama_model_name(model)
        if not name or not ollama_model_supports_tools(name):
            continue
        if _PREFERRED_OLLAMA_MODEL.search(name):
            return f"ollama/{name}"
    return None


def format_tools_unsupported_error(model_ref: str) -> str:
    """User-facing guidance when a model cannot run agent tools."""
    return (
        f"{model_ref} does not support agent tools. "
        "Pick a tool-capable model (e.g. qwen2.5, llama3.1+, deepseek-r1) "
        "in the model picker or Settings → Models."
    )


def _first_tool_capable_in_provider(provider: _ProviderLike) -> str | None:
    if provider.id == "ollama":
        preferred = preferred_ollama_model_ref(list(provider.models))
        if preferred:
            return preferred
    for model in provider.models:
        model_id = _ollama_model_name(model)
        if not model_id:
            continue
        ref = f"{provider.id}/{model_id}"
        if model_supports_tools(ref):
            return ref
    return None


def first_tool_capable_model_ref(providers: list[_ProviderLike]) -> str | None:
    """Pick the first tool-capable model, preferring local providers."""
    preferred_provider_order = ("ollama", "opencode")
    by_id = {provider.id: provider for provider in providers}

    for provider_id in preferred_provider_order:
        provider = by_id.get(provider_id)
        if provider is None:
            continue
        ref = _first_tool_capable_in_provider(provider)
        if ref:
            return ref

    for provider in providers:
        if provider.id in preferred_provider_order:
            continue
        ref = _first_tool_capable_in_provider(provider)
        if ref:
            return ref
    return None
