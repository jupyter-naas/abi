import logging
from types import SimpleNamespace

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    build_chat_collection_name,
    build_embedding_cache_key,
    chunk_markdown,
    embed_text,
    embed_text_hash,
    embed_texts,
)
from naas_abi.apps.nexus.apps.api.app.services.direct_model_providers import (
    DirectModelProviderDisabledError,
)
from naas_abi_core.engine.context import with_model_registry_override
from naas_abi_core.models.Model import EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryPort import ModelNotFoundError
from naas_abi_core.services.model_registry.ModelRegistryService import ModelRegistryService


def test_collection_and_cache_key() -> None:
    assert build_chat_collection_name("conv-1") == "chat_conv-1"
    assert (
        build_embedding_cache_key("ws-1", "abc", "hash-v1", 256)
        == "embeddings:ws-1:abc:hash-v1:256"
    )


def test_chunk_markdown_basic() -> None:
    chunks = chunk_markdown("a" * 3000, chunk_size=1000, chunk_overlap=100)
    assert len(chunks) >= 3
    assert all(isinstance(c, str) and c for c in chunks)


def test_chunk_markdown_empty() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("   ") == []


def test_chunk_markdown_short_text_is_one_chunk() -> None:
    chunks = chunk_markdown("hello world", chunk_size=1000, chunk_overlap=100)
    assert chunks == ["hello world"]


def test_embed_text_hash_dimension_and_stability() -> None:
    v1 = embed_text_hash("hello", "hash-v1", 64)
    v2 = embed_text_hash("hello", "hash-v1", 64)
    assert v1.shape[0] == 64
    assert (v1 == v2).all()


def test_embed_text_hash_is_unit_length() -> None:
    v = embed_text_hash("some text", "hash-v1", 128)
    assert abs(np.linalg.norm(v) - 1.0) < 1e-6


def test_embed_texts_hash_v1_batch() -> None:
    texts = ["apple", "banana", "cherry"]
    vecs = embed_texts(texts, embedding_model="hash-v1", embedding_dimension=32)
    assert len(vecs) == 3
    for v in vecs:
        assert v.shape == (32,)


def test_embed_text_hash_v1_single() -> None:
    v = embed_text("hello world", embedding_model="hash-v1", embedding_dimension=64)
    expected = embed_text_hash("hello world", "hash-v1", 64)
    assert (v == expected).all()


def test_embed_texts_different_inputs_produce_different_vectors() -> None:
    v1 = embed_texts(["foo"], embedding_model="hash-v1", embedding_dimension=64)[0]
    v2 = embed_texts(["bar"], embedding_model="hash-v1", embedding_dimension=64)[0]
    assert not np.allclose(v1, v2)


class _Embeddings(Embeddings):
    """A LangChain ``Embeddings`` double: one fixed vector per text."""

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 1.0]


def _registry(*embedding_models: str) -> ModelRegistryService:
    """The engine's model registry, holding ``embedding_models`` only."""
    registry = ModelRegistryService()
    for model_id in embedding_models:
        registry.register(
            model_id, EmbeddingModel(model_id=model_id, provider="self-hosted", model=_Embeddings())
        )
    return registry


@pytest.fixture
def openai_fallback(monkeypatch: pytest.MonkeyPatch) -> list[_Embeddings]:
    """The OpenAI fallback, doubled: the platform's OPENAI_API_KEY in the secret
    service and ``OpenAIEmbeddings``. Returns each embedder it built."""
    import langchain_openai
    from naas_abi import ABIModule

    secret = SimpleNamespace(get=lambda name: "sk-test" if name == "OPENAI_API_KEY" else None)
    engine = SimpleNamespace(services=SimpleNamespace(secret=secret))
    monkeypatch.setattr(ABIModule, "get_instance", lambda: SimpleNamespace(engine=engine))
    built: list[_Embeddings] = []

    def build(**kwargs) -> _Embeddings:
        built.append(_Embeddings(**kwargs))
        return built[-1]

    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", build)
    return built


def test_a_registered_embedding_model_embeds_with_direct_providers_off(
    direct_model_providers_off: None, openai_fallback: list[_Embeddings]
) -> None:
    with with_model_registry_override(_registry("text-embedding-3-small")):
        vectors = embed_texts(["a", "b"], "text-embedding-3-small", 1536)
        query = embed_text("q", "text-embedding-3-small", 1536)

    assert [v.tolist() for v in vectors] == [[1.0, 0.0], [1.0, 0.0]]
    assert query.tolist() == [0.0, 1.0]
    assert openai_fallback == []


def test_an_unregistered_embedding_model_is_refused_with_direct_providers_off(
    direct_model_providers_off: None, openai_fallback: list[_Embeddings]
) -> None:
    """No silent OpenAI fallback: the error names the model to register."""
    with with_model_registry_override(_registry()):
        with pytest.raises(DirectModelProviderDisabledError) as refused:
            embed_texts(["a"], "text-embedding-3-small", 1536)

    message = str(refused.value)
    assert "'text-embedding-3-small' is not registered in the model registry" in message
    assert "direct_model_providers_enabled: false" in message
    assert "Register 'text-embedding-3-small' as an embedding model" in message
    assert isinstance(refused.value, RuntimeError)
    assert isinstance(refused.value.__cause__, ModelNotFoundError)
    assert openai_fallback == []


def test_the_openai_fallback_warns_that_it_bypasses_the_registry(
    monkeypatch: pytest.MonkeyPatch,
    openai_fallback: list[_Embeddings],
    caplog: pytest.LogCaptureFixture,
) -> None:
    from naas_abi.apps.nexus.apps.api.app.core import config

    monkeypatch.setattr(config.settings, "direct_model_providers_enabled", True)

    with with_model_registry_override(_registry()):
        with caplog.at_level(logging.WARNING):
            vectors = embed_texts(["a"], "text-embedding-3-small", 1536)

    assert [v.tolist() for v in vectors] == [[1.0, 0.0]]
    (embedder,) = openai_fallback
    assert embedder.kwargs["model"] == "text-embedding-3-small"
    assert embedder.kwargs["api_key"].get_secret_value() == "sk-test"
    assert embedder.kwargs["dimensions"] == 1536
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "'text-embedding-3-small' is not registered in the model registry" in w
        and "bypassing the model registry" in w
        for w in warnings
    )
