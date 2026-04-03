# VectorStore

## What it is
- A minimal in-memory vector store backed by **Qdrant** (via `qdrant-client`).
- Stores texts + metadata alongside provided embedding vectors and supports cosine-similarity search.

## Public API
- `class VectorStore(dimension: int = 1536)`
  - Creates an in-memory Qdrant collection named `"documents"` with cosine distance and given vector dimension.
- `VectorStore.add_texts(texts, metadatas=None, embeddings=None) -> List[str]`
  - Upserts a batch of points containing:
    - `payload["text"]` = original text
    - additional payload fields from corresponding metadata dict
  - Requires `embeddings` (no embedding generation is performed).
  - Returns string IDs for inserted items.
- `VectorStore.similarity_search(query_embedding, k: int = 4) -> List[dict]`
  - Queries the collection with a provided embedding vector.
  - Returns a list of dicts: `{"text": ..., "metadata": ..., "score": ...}`.

## Configuration/Dependencies
- Dependency: `qdrant-client`
  - Install: `pip install qdrant-client`
- Storage: in-memory Qdrant instance (`QdrantClient(":memory:")`)
- Collection:
  - name: `"documents"`
  - distance: cosine
  - vector size: `dimension` passed to constructor

## Usage
```python
from naas_abi_core.services.agent.beta.VectorStore import VectorStore

store = VectorStore(dimension=3)

texts = ["hello world", "goodbye world"]
metadatas = [{"source": "a"}, {"source": "b"}]
embeddings = [
    [1.0, 0.0, 0.0],
    [0.9, 0.1, 0.0],
]

ids = store.add_texts(texts=texts, metadatas=metadatas, embeddings=embeddings)
results = store.similarity_search(query_embedding=[1.0, 0.0, 0.0], k=2)

print(ids)
print(results)
```

## Caveats
- `add_texts(...)` raises `ValueError` if `embeddings` is not provided.
- The Qdrant collection is always created in `__init__` with a fixed name (`"documents"`); data is not persisted (in-memory only).
- IDs are auto-assigned sequential integers starting from `0` and returned as strings.
