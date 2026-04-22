import numpy as np
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    build_chat_collection_name,
    build_embedding_cache_key,
    chunk_markdown,
    embed_text,
    embed_text_hash,
    embed_texts,
)


def test_collection_and_cache_key() -> None:
    assert build_chat_collection_name("conv-1") == "chat_conv-1"
    assert build_embedding_cache_key("abc", "hash-v1", 256) == "embeddings:abc:hash-v1:256"


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
