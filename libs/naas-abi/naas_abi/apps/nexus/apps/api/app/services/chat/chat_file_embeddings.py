from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

import numpy as np

# Default production embedding model. Using "text-embedding-3-small" for
# semantic search; keep "hash-v1" only for unit tests / offline environments.
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSION = 1536


def build_chat_collection_name(thread_id: str) -> str:
    return f"chat_{thread_id}"


def build_embedding_cache_key(
    file_sha256: str,
    embedding_model: str,
    embedding_dimension: int,
) -> str:
    return f"embeddings:{file_sha256}:{embedding_model}:{embedding_dimension}"


def chunk_markdown(
    markdown: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[str]:
    text = (markdown or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - chunk_overlap)
    return chunks


# ---------------------------------------------------------------------------
# Hash-based pseudo-embeddings (for testing / offline use only)
# These produce deterministic vectors but carry NO semantic meaning.
# ---------------------------------------------------------------------------

def embed_text_hash(text: str, embedding_model: str, embedding_dimension: int) -> np.ndarray:
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")

    material = f"{embedding_model}:{text}".encode()
    out = np.zeros(embedding_dimension, dtype=float)

    digest = hashlib.sha256(material).digest()
    cursor = 0
    for i in range(embedding_dimension):
        if cursor >= len(digest):
            digest = hashlib.sha256(digest).digest()
            cursor = 0
        value = digest[cursor]
        cursor += 1
        out[i] = (value / 127.5) - 1.0

    norm = np.linalg.norm(out)
    if norm == 0:
        return out
    return out / norm


def embed_many_hash(
    texts: Sequence[str],
    embedding_model: str,
    embedding_dimension: int,
) -> list[np.ndarray]:
    return [embed_text_hash(t, embedding_model, embedding_dimension) for t in texts]


# ---------------------------------------------------------------------------
# Real embedding helpers (OpenAI / LangChain-compatible)
# ---------------------------------------------------------------------------

def _build_openai_embedder(embedding_model: str, embedding_dimension: int):
    """Build an Embeddings instance for ``embedding_model``.

    Resolution order:
    1. Process-wide ``ModelRegistry`` — if a module registered an
       ``EmbeddingModel`` under this canonical id, return its langchain
       ``Embeddings`` instance with api_key already plumbed by the owning
       module. Lets nexus transparently use Bedrock Titan, Cohere, OpenAI
       text-embedding-3-large, etc. depending on which provider modules
       the user enabled.
    2. Off-catalog (canonical id not registered, e.g. the
       ``text-embedding-3-small`` variant): build an ``OpenAIEmbeddings``
       directly, pulling ``OPENAI_API_KEY`` from the engine's **secret
       service** (not ``os.environ``) so the api key still flows from the
       configured ``services.secret`` adapter. The custom ``dimensions``
       kwarg is preserved because text-embedding-3-* supports it.

    Raises ``RuntimeError`` if neither resolution succeeds.
    """
    from naas_abi_core.engine.context import get_default_model_registry

    registry = get_default_model_registry()
    if registry is not None:
        try:
            return registry.get_embedding_model(embedding_model).model
        except Exception:
            # Not registered — fall through to off-catalog OpenAI construction.
            pass

    from naas_abi import ABIModule  # avoid a top-level cycle

    secret_service = ABIModule.get_instance().engine.services.secret
    api_key = secret_service.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"Cannot build an embedder for {embedding_model!r}: not registered "
            f"in the ModelRegistry and no OPENAI_API_KEY is available via the "
            f"engine's secret service. Either register the embedding model in "
            f"a provider module or add OPENAI_API_KEY to your secret store."
        )

    from langchain_openai import OpenAIEmbeddings
    from pydantic import SecretStr

    kwargs: dict = {"model": embedding_model, "api_key": SecretStr(api_key)}
    # text-embedding-3-* supports a custom `dimensions` parameter
    if "3-" in embedding_model and embedding_dimension > 0:
        kwargs["dimensions"] = embedding_dimension
    return OpenAIEmbeddings(**kwargs)


_EMBED_BATCH_SIZE = 100  # chunks per OpenAI API call when progress tracking


def embed_texts(
    texts: Sequence[str],
    embedding_model: str,
    embedding_dimension: int,
    on_progress: Callable[[int], None] | None = None,
) -> list[np.ndarray]:
    """Embed multiple texts.

    Uses hash-based embeddings when ``embedding_model == "hash-v1"`` (no API
    key required, for tests / offline use).  All other model names are routed
    through LangChain's OpenAI embeddings.

    Args:
        on_progress: Optional callback called after each batch with a
            0-100 percentage indicating how much of the embedding work
            is complete.
    """
    if embedding_model == "hash-v1":
        return embed_many_hash(texts, embedding_model, embedding_dimension)

    lc_model = _build_openai_embedder(embedding_model, embedding_dimension)

    if on_progress is None or len(texts) <= _EMBED_BATCH_SIZE:
        return [np.array(v, dtype=float) for v in lc_model.embed_documents(list(texts))]

    # Process in fixed-size batches so the caller can report incremental progress.
    total = len(texts)
    results: list[np.ndarray] = []
    for i in range(0, total, _EMBED_BATCH_SIZE):
        batch = list(texts[i : i + _EMBED_BATCH_SIZE])
        vecs = lc_model.embed_documents(batch)
        results.extend(np.array(v, dtype=float) for v in vecs)
        done = min(i + _EMBED_BATCH_SIZE, total)
        on_progress(int(done / total * 100))
    return results


def embed_text(
    text: str,
    embedding_model: str,
    embedding_dimension: int,
) -> np.ndarray:
    """Embed a single query text.

    Uses hash-based embedding when ``embedding_model == "hash-v1"``, otherwise
    routes through LangChain's OpenAI embeddings (``embed_query`` path for
    asymmetric models).
    """
    if embedding_model == "hash-v1":
        return embed_text_hash(text, embedding_model, embedding_dimension)

    lc_model = _build_openai_embedder(embedding_model, embedding_dimension)
    return np.array(lc_model.embed_query(text), dtype=float)
