# chat_file_embeddings

## What it is
Utilities for:
- Building collection/cache identifiers for chat file embeddings.
- Chunking markdown into overlapping text segments.
- Generating embeddings either:
  - deterministically via a SHA256-based **hash pseudo-embedding** (`hash-v1`, for tests/offline), or
  - via **OpenAI embeddings** through `langchain_openai.OpenAIEmbeddings`.

## Public API
- `DEFAULT_EMBEDDING_MODEL: str`
  - Default production embedding model name (`"text-embedding-3-small"`).
- `DEFAULT_EMBEDDING_DIMENSION: int`
  - Default embedding dimension (`1536`).

- `build_chat_collection_name(thread_id: str) -> str`
  - Returns a collection name like `chat_<thread_id>`.

- `build_embedding_cache_key(file_sha256: str, embedding_model: str, embedding_dimension: int) -> str`
  - Builds a cache key: `embeddings:<sha256>:<model>:<dimension>`.

- `chunk_markdown(markdown: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> list[str]`
  - Splits markdown text into overlapping fixed-size chunks.
  - Returns `[]` for empty/whitespace input.

- `embed_text_hash(text: str, embedding_model: str, embedding_dimension: int) -> np.ndarray`
  - Deterministic normalized vector based on SHA256 hashing.
  - **Not semantic**; intended for tests/offline usage.
  - Raises `ValueError` if `embedding_dimension <= 0`.

- `embed_many_hash(texts: Sequence[str], embedding_model: str, embedding_dimension: int) -> list[np.ndarray]`
  - Hash-embeds multiple texts (calls `embed_text_hash` per item).

- `embed_texts(texts: Sequence[str], embedding_model: str, embedding_dimension: int, on_progress: Callable[[int], None] | None = None) -> list[np.ndarray]`
  - Embeds multiple texts.
  - If `embedding_model == "hash-v1"`, uses hash embeddings.
  - Otherwise uses `OpenAIEmbeddings.embed_documents`.
  - If `on_progress` is provided and input size exceeds 100, processes in batches of 100 and calls `on_progress(percentage:int)` after each batch.

- `embed_text(text: str, embedding_model: str, embedding_dimension: int) -> np.ndarray`
  - Embeds a single query text.
  - If `embedding_model == "hash-v1"`, uses hash embedding.
  - Otherwise uses `OpenAIEmbeddings.embed_query`.

## Configuration/Dependencies
- Requires `numpy`.
- For non-`hash-v1` models:
  - Requires `langchain_openai` and its `OpenAIEmbeddings`.
  - Requires appropriate OpenAI credentials/config supported by `langchain_openai` (e.g., environment variables).

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    chunk_markdown,
    embed_texts,
    embed_text,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DIMENSION,
)

# Chunk some markdown
chunks = chunk_markdown("# Title\n\nSome long content..." * 50)

# Offline/test embeddings (no API calls)
vecs = embed_texts(chunks, embedding_model="hash-v1", embedding_dimension=64)
qvec = embed_text("find title", embedding_model="hash-v1", embedding_dimension=64)

# Production embeddings (requires langchain_openai + credentials)
prod_vecs = embed_texts(
    chunks,
    embedding_model=DEFAULT_EMBEDDING_MODEL,
    embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
)
```

## Caveats
- `hash-v1` embeddings are deterministic but **carry no semantic meaning** (not suitable for real semantic search).
- `embed_text_hash` requires `embedding_dimension > 0`.
- Progress callback in `embed_texts` is only used when `on_progress` is provided **and** more than 100 texts are embedded; updates are per 100-text batch.
