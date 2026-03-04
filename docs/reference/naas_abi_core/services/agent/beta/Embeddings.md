# Embeddings

## What it is
A small embeddings utility module that:
- Generates embedding vectors for text (single and batch).
- Selects the backend based on `AI_MODE` (`airgap` vs. default/OpenAI via LangChain).
- Caches results on disk using `CacheFactory` to avoid recomputing embeddings for the same text/model.

## Public API
- `EMBEDDINGS_MODELS_DIMENSIONS_MAP: dict[str, int]`
  - Supported embedding models and their vector dimensions (used for cache keying and validation).

- `embeddings(text) -> list[float]`
  - Returns an embedding vector for a single input string.
  - Behavior depends on environment:
    - `AI_MODE=airgap`: calls a local HTTP embeddings endpoint.
    - Otherwise: uses `langchain_openai.OpenAIEmbeddings.embed_query`.

- `embeddings_batch(texts) -> list[list[float]]`
  - Returns embedding vectors for a list of input strings.
  - Behavior depends on environment:
    - `AI_MODE=airgap`: loops over `texts` and calls `embeddings(text)` per item.
    - Otherwise: uses `langchain_openai.OpenAIEmbeddings.embed_documents`.

> Internal helpers (not intended as public API): `__get_safe_model`, `__compute_key`, `_sha1`, `_sha1s`, `_get_embeddings_model`.

## Configuration/Dependencies
- Environment variables:
  - `AI_MODE`
    - If set to `"airgap"`, uses local server backend and model `"ai/embeddinggemma"`.
  - `OPENROUTER_API_KEY`
    - If set (non-empty), uses OpenRouter via `base_url="https://openrouter.ai/api/v1"` and model `"openai/text-embedding-3-large"`.
    - If not set, uses `OpenAIEmbeddings(model="text-embedding-ada-002")`.

- External services/backends:
  - Airgap mode: `POST http://localhost:12434/engines/llama.cpp/v1/embeddings` with JSON `{"model": ..., "input": ...}`.
  - Default mode: `langchain_openai.OpenAIEmbeddings`.

- Caching:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="intent_mapping")`.
  - Cache keys include model name (sanitized), embedding dimension, and `sha1(text)`.
  - Cached values are stored with `cache_type=DataType.PICKLE`.

- Python dependencies (as imported):
  - `requests` (airgap mode)
  - `langchain_openai` (default mode)
  - `pydantic.SecretStr`
  - `tqdm`
  - `naas_abi_core.services.cache` components

## Usage
```python
from naas_abi_core.services.agent.beta.Embeddings import embeddings, embeddings_batch

vec = embeddings("hello world")
print(len(vec), vec[:5])

batch = embeddings_batch(["one", "two", "three"])
print(len(batch), len(batch[0]))
```

### Airgap backend example
```bash
export AI_MODE=airgap
python -c "from naas_abi_core.services.agent.beta.Embeddings import embeddings; print(len(embeddings('test')))"
```

### OpenRouter example
```bash
export OPENROUTER_API_KEY="your_key"
python -c "from naas_abi_core.services.agent.beta.Embeddings import embeddings; print(len(embeddings('test')))"
```

## Caveats
- Only models present in `EMBEDDINGS_MODELS_DIMENSIONS_MAP` are supported; unsupported models trigger an `AssertionError` during cache key generation.
- Airgap mode requires the local embeddings HTTP server to be running at `localhost:12434`; network errors will raise via `res.raise_for_status()`.
- Cache keys incorporate model dimensions; changing `EMBEDDINGS_MODELS_DIMENSIONS_MAP` can effectively change cache identity for the same text/model.
