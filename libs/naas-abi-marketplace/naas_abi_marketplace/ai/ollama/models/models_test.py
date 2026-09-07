"""What the shipped model definitions promise must match what Ollama does.

Both of these were wrong and silent. Ollama allocates a 4096-token context
regardless of the model, and truncates past it without an error — so a
``context_window`` in ABI metadata is decoration unless ``num_ctx`` is passed
to the client too.
"""

from __future__ import annotations

from naas_abi_marketplace.ai.ollama.defaults import (
    DEFAULT_CHAT_MODEL_TAG,
    DEFAULT_EMBEDDING_MODEL_TAG,
)
from naas_abi_marketplace.ai.ollama.models.nomic_embed_text import NomicEmbedTextModel
from naas_abi_marketplace.ai.ollama.models.qwen2_5_3b import Qwen25ThreeBModel


def test_chat_model_requests_the_context_window_it_advertises() -> None:
    """Without num_ctx, `ollama ps` reports CONTEXT 4096 and truncates."""
    definition = Qwen25ThreeBModel.model
    assert definition.context_window == Qwen25ThreeBModel.CONTEXT_WINDOW
    # `.model` is typed as the generic BaseChatModel; num_ctx is ChatOllama's.
    assert (
        getattr(definition.model, "num_ctx", None) == Qwen25ThreeBModel.CONTEXT_WINDOW
    )


def test_chat_model_tag_matches_the_shared_default() -> None:
    assert Qwen25ThreeBModel.MODEL_ID == DEFAULT_CHAT_MODEL_TAG
    assert Qwen25ThreeBModel.model.model_id == DEFAULT_CHAT_MODEL_TAG


def test_embedding_model_tag_matches_the_shared_default() -> None:
    assert NomicEmbedTextModel.MODEL_ID == DEFAULT_EMBEDDING_MODEL_TAG


def test_embedding_model_does_not_claim_8k_context() -> None:
    """It reports 2048 and drops the rest silently; num_ctx does not lift it.

    Measured: two ~3000-word documents differing only in their final sentence
    embed to cosine 1.0, while the same tails within the limit give 0.868.
    """
    described = NomicEmbedTextModel.model.description
    assert described is not None
    assert "8k" not in described
    assert "2048" in described
