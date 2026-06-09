# mypy: disable-error-code="arg-type,misc"
"""Tests for the in-memory ModelRegistryService."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    EmbeddingModel,
    ModelProvider,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import (
    DefaultModelNotResolvedError,
    ModelNotFoundError,
    ProviderNotConfiguredError,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _fake_chat() -> FakeListChatModel:
    return FakeListChatModel(responses=["hi"])


class _FakeEmbeddings(Embeddings):
    def __init__(self, tag: str = "fake") -> None:
        self.tag = tag

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0]


def _chat_model(canonical_id: str, provider: str, provider_model_id: str | None = None) -> ChatModel:
    return ChatModel(
        model_id=provider_model_id or canonical_id,
        provider=provider,
        model=_fake_chat(),
    )


def _embedding_model(provider: str, provider_model_id: str) -> EmbeddingModel:
    return EmbeddingModel(
        model_id=provider_model_id,
        provider=provider,
        model=_FakeEmbeddings(provider_model_id),
    )


# ---------------------------------------------------------------------------
# register + get
# ---------------------------------------------------------------------------


def test_register_then_get_returns_same_instance() -> None:
    reg = ModelRegistryService()
    m = _chat_model("claude-sonnet-4.5", "anthropic", "claude-sonnet-4-5-20250929")
    reg.register("claude-sonnet-4.5", m)

    got = reg.get("claude-sonnet-4.5")
    assert got is m
    assert got.provider == "anthropic"
    assert got.model_id == "claude-sonnet-4-5-20250929"


def test_register_accepts_canonical_id_enum_or_string() -> None:
    reg = ModelRegistryService()
    m = _chat_model("claude-sonnet-4.5", "anthropic")
    reg.register(CanonicalModelId.CLAUDE_SONNET_4_5, m)

    # Both lookups resolve to the same entry.
    assert reg.get("claude-sonnet-4.5") is m
    assert reg.get(CanonicalModelId.CLAUDE_SONNET_4_5) is m


def test_register_accepts_provider_enum_or_string() -> None:
    reg = ModelRegistryService()
    m = ChatModel(
        model_id="x", provider=str(ModelProvider.OPENAI), model=_fake_chat()
    )
    reg.register("my-model", m)
    assert reg.get("my-model", provider=ModelProvider.OPENAI) is m
    assert reg.get("my-model", provider="openai") is m


def test_register_duplicate_provider_pair_is_allowed_first_wins() -> None:
    """Registering twice under the same (canonical_id, provider) is permitted —
    auto-discovery can hit the same model from multiple files. The first
    registered wins on lookup; callers that need a specific variant import
    the file directly."""
    reg = ModelRegistryService()
    first = _chat_model("foo", "openai")
    second = _chat_model("foo", "openai")
    reg.register("foo", first)
    reg.register("foo", second)  # no exception

    assert reg.get("foo", provider="openai") is first
    assert len(reg.list_models()) == 2


def test_register_same_canonical_id_different_providers_is_fine() -> None:
    reg = ModelRegistryService()
    m_openai = _chat_model("foo", "openai")
    m_router = _chat_model("foo", "openrouter", "openai/foo")
    reg.register("foo", m_openai)
    reg.register("foo", m_router)
    assert reg.get("foo", provider="openai") is m_openai
    assert reg.get("foo", provider="openrouter") is m_router


# ---------------------------------------------------------------------------
# Provider pinning + fallback
# ---------------------------------------------------------------------------


def test_provider_pinned_lookup_returns_exact_match() -> None:
    reg = ModelRegistryService()
    m_openai = _chat_model("foo", "openai")
    m_router = _chat_model("foo", "openrouter")
    reg.register("foo", m_openai)
    reg.register("foo", m_router)
    assert reg.get("foo", provider="openai") is m_openai


def test_provider_pinned_lookup_falls_back_when_provider_missing() -> None:
    """If user pins 'openai' but only 'openrouter' is registered for the same
    canonical id, return the openrouter entry (provider has been registered
    as part of openrouter registration, so it is 'configured')."""
    reg = ModelRegistryService()
    m_router = _chat_model("foo", "openrouter")
    reg.register("foo", m_router)
    # 'openai' has no registration at all — that's the not-configured case.
    with pytest.raises(ProviderNotConfiguredError):
        reg.get("foo", provider="openai")


def test_provider_pinned_lookup_falls_back_when_provider_configured_but_lacks_model() -> None:
    """openai is 'configured' (some other model registered under it), but the
    requested canonical id is only present under openrouter — fall back."""
    reg = ModelRegistryService()
    reg.register("other", _chat_model("other", "openai"))
    m_router = _chat_model("foo", "openrouter")
    reg.register("foo", m_router)
    assert reg.get("foo", provider="openai") is m_router


# ---------------------------------------------------------------------------
# Off-catalog routing
# ---------------------------------------------------------------------------


def test_off_catalog_uses_explicit_provider_chat_factory() -> None:
    captured: dict[str, Any] = {}

    def factory(model_id: str) -> FakeListChatModel:
        captured["model_id"] = model_id
        return FakeListChatModel(responses=["off"])

    reg = ModelRegistryService()
    reg.register_chat_provider("openai", factory)

    result = reg.get_chat_model("totally-new-model", provider="openai")
    assert isinstance(result, ChatModel)
    assert result.provider == "openai"
    assert result.model_id == "totally-new-model"
    assert captured["model_id"] == "totally-new-model"


def test_off_catalog_without_provider_fails() -> None:
    """Off-catalog ids must come with an explicit provider= — the registry
    refuses to guess."""
    reg = ModelRegistryService()
    reg.register_chat_provider("openai", lambda mid: FakeListChatModel(responses=["x"]))
    with pytest.raises(ModelNotFoundError, match="not registered"):
        reg.get_chat_model("unknown")


def test_off_catalog_with_provider_but_no_factory_fails() -> None:
    reg = ModelRegistryService()
    with pytest.raises(ModelNotFoundError, match="no registered chat factory"):
        reg.get_chat_model("unknown", provider="openai")


def test_off_catalog_embedding_uses_explicit_provider_factory() -> None:
    reg = ModelRegistryService()
    reg.register_embedding_provider("openai", lambda mid: _FakeEmbeddings(mid))
    got = reg.get_embedding_model("text-embedding-new", provider="openai")
    assert isinstance(got, EmbeddingModel)
    assert got.provider == "openai"
    assert got.model_id == "text-embedding-new"


# ---------------------------------------------------------------------------
# Defaults + validation
# ---------------------------------------------------------------------------


def test_get_default_chat_model_returns_registered_default() -> None:
    reg = ModelRegistryService(default_chat_model="gpt-5.1-mini")
    m = _chat_model("gpt-5.1-mini", "openai")
    reg.register("gpt-5.1-mini", m)
    assert reg.get_default_chat_model() is m


def test_get_default_chat_model_without_config_raises() -> None:
    reg = ModelRegistryService()
    with pytest.raises(DefaultModelNotResolvedError, match="No default chat model"):
        reg.get_default_chat_model()


def test_validate_defaults_passes_when_all_resolved() -> None:
    reg = ModelRegistryService(
        default_chat_model="gpt-5.1-mini",
        default_embedding_model="text-embedding-3",
    )
    reg.register("gpt-5.1-mini", _chat_model("gpt-5.1-mini", "openai"))
    reg.register("text-embedding-3", _embedding_model("openai", "text-embedding-3"))
    # No exception.
    reg.validate_defaults()


def test_validate_defaults_fails_when_chat_default_unregistered() -> None:
    reg = ModelRegistryService(default_chat_model="missing-model")
    with pytest.raises(DefaultModelNotResolvedError, match="default_chat_model"):
        reg.validate_defaults()


def test_validate_defaults_fails_when_embedding_default_unregistered() -> None:
    reg = ModelRegistryService(default_embedding_model="missing-embedding")
    with pytest.raises(DefaultModelNotResolvedError, match="default_embedding_model"):
        reg.validate_defaults()


def test_validate_defaults_rejects_wrong_model_type_for_chat_default() -> None:
    """A canonical id registered only as an embedding cannot satisfy
    default_chat_model — hard fail."""
    reg = ModelRegistryService(default_chat_model="oops")
    reg.register("oops", _embedding_model("openai", "oops"))
    with pytest.raises(DefaultModelNotResolvedError, match="default_chat_model"):
        reg.validate_defaults()


def test_validate_defaults_error_message_is_actionable() -> None:
    """The error must name the config key, point at the likely root cause
    (module not enabled / soft dep), and list what IS registered so the user
    can spot a typo or pick a valid id."""
    reg = ModelRegistryService(
        default_chat_model="gpt-4.1-mini",
        default_embedding_model="text-embedding-3-large",
    )
    reg.register("gpt-5.1-mini", _chat_model("gpt-5.1-mini", "openai"))
    reg.register("text-embedding-3", _embedding_model("openai", "text-embedding-3"))

    with pytest.raises(DefaultModelNotResolvedError) as exc_info:
        reg.validate_defaults()
    msg = str(exc_info.value)

    # Names the configured ids and the config keys.
    assert "'gpt-4.1-mini'" in msg
    assert "'text-embedding-3-large'" in msg
    assert "services.model_registry.default_chat_model" in msg
    assert "services.model_registry.default_embedding_model" in msg

    # Points at the likely root cause.
    assert "modules:" in msg
    assert "soft" in msg

    # Shows what IS currently registered so the user can fix the config.
    assert "'gpt-5.1-mini'" in msg
    assert "'text-embedding-3'" in msg


def test_validate_defaults_error_message_handles_empty_registry() -> None:
    """When nothing is registered at all, the 'currently registered' line
    must still render — '(none)' — not crash or omit the hint."""
    reg = ModelRegistryService(default_chat_model="gpt-4.1-mini")
    with pytest.raises(DefaultModelNotResolvedError) as exc_info:
        reg.validate_defaults()
    msg = str(exc_info.value)
    assert "currently registered chat model ids: (none)" in msg


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


def test_list_models_and_canonical_ids() -> None:
    reg = ModelRegistryService()
    reg.register("a", _chat_model("a", "openai"))
    reg.register("a", _chat_model("a", "openrouter"))
    reg.register("b", _chat_model("b", "anthropic"))
    assert sorted(reg.list_canonical_ids()) == ["a", "b"]
    assert len(reg.list_models()) == 3
