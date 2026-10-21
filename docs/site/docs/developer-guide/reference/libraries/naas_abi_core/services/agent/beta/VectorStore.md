# VectorStore

## What it is
- A minimal in-memory vector store backed by **Qdrant** (using `QdrantClient(":memory:")`).
- Supports inserting text + metadata with **pre-computed embeddings** and running cosine similarity search.

## Public API

### `class VectorStore`
In-memory Qdrant collection wrapper.

#### `__init__(dimension: int = 1536)`
- Creates an in-memory Qdrant client and a collection named `"documents"`.
- Configures vectors with:
  - `size = dimension`
  - `distance = COSINE`

#### `add_texts(texts, metadatas=None, embeddings=None) -> List[str]`
- Inserts points into the `"documents"` collection.
- Payload stored per point:
  - `"text"` plus any metadata keys.
- Returns:
  - List of string IDs assigned sequentially starting at `0`.
- Requires:
  - `embeddings` must be provided (otherwise raises `ValueError`).

#### `similarity_search(query_embedding, k: int = 4) -> List[dict]`
- Runs a similarity query against the stored vectors.
- Returns a list of dicts:
  - `text`: stored text
  - `metadata`: payload keys excluding `"text"`
  - `score`: Qdrant similarity score

## Configuration/Dependencies
- Requires `qdrant-client`:
  - `pip install qdrant-client`
- Uses an in-memory Qdrant instance (`QdrantClient(":memory:")`), so data is not persisted.
- Collection name is fixed to `"documents"`.

## Usage
```python
from naas_abi_core.services.agent.beta.VectorStore import VectorStore

# Create store (dimension must match your embeddings)
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
- `add_texts` does **not** compute embeddings; you must provide `embeddings`.
- No explicit validation that embedding lengths match `dimension`.
- Data is ephemeral due to in-memory Qdrant usage.
- ID generation is local and sequential; IDs reset when a new `VectorStore` is created.
