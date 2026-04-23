# `QdrantInMemoryAdapter`

## What it is
- A local (embedded) Qdrant vector store adapter implementing `IVectorStorePort`.
- Supports:
  - Ephemeral in-memory mode (`storage_path=":memory:"`)
  - Filesystem-backed persistence (`storage_path="<dir>"`)
- Provides collection management plus CRUD/search operations for vector documents.

## Public API
### Class: `QdrantInMemoryAdapter(IVectorStorePort)`
#### `__init__(storage_path: str = ":memory:", timeout: int = 300) -> None`
- Configures the adapter (does not create the client yet).
- Stores:
  - `storage_path`: `":memory:"` for ephemeral, otherwise a directory path.
  - `timeout`: passed to `QdrantClient`.

#### `initialize() -> None`
- Creates the embedded `QdrantClient` if not already initialized.
- If `storage_path != ":memory:"`, ensures the directory exists.

#### `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
- Creates a collection with the given vector size and distance metric.
- `distance_metric` supported values:
  - `"cosine"`, `"euclidean"`, `"dot"` (defaults to cosine on unknown values)
- `**kwargs` are forwarded to `client.create_collection(...)`.

#### `delete_collection(collection_name: str) -> None`
- Deletes the named collection.

#### `list_collections() -> List[str]`
- Returns collection names.

#### `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`
- Upserts a batch of vectors.
- For each `VectorDocument`, stores payload fields:
  - `_abi_id`: original document id
  - `_abi_vector`: vector values (list)
  - `payload`: optional `doc.payload`
  - plus `doc.metadata` keys (if provided)
- Raises `RuntimeError` if Qdrant upsert does not complete.

#### `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
- Searches the collection using `query_vector`, returning up to `k` results.
- Optional `filter`: exact-match constraints on payload fields (translated to Qdrant `FieldCondition` + `MatchValue`).
- `include_vectors`:
  - If `True`, attempts to return vectors from stored `_abi_vector` payload; otherwise may fall back to returned `hit.vector`.
- `include_metadata`:
  - If `True`, returns payload keys excluding: `payload`, `_abi_id`, `_abi_vector`.

#### `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
- Retrieves a single vector document by `vector_id`.
- Returns `None` if not found.
- If `include_vector`:
  - Prefers `_abi_vector` from payload; otherwise uses `point.vector` if present.
  - If neither is available, returns an empty `np.array([])`.

#### `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
- Updates vector and/or payload:
  - If `vector` is provided: calls `update_vectors(...)`.
  - If any of `vector`, `metadata`, `payload` are provided: calls `set_payload(...)` with:
    - `_abi_id`: `vector_id`
    - `_abi_vector`: included only when `vector` is provided
    - `payload`: included only when `payload` is provided
    - plus metadata keys (if provided)

#### `delete_vectors(collection_name: str, vector_ids: List[str]) -> None`
- Deletes multiple vectors by id.

#### `count_vectors(collection_name: str) -> int`
- Returns the collection `points_count` (or `0` if absent).

#### `close() -> None`
- Closes the underlying `QdrantClient` and resets it to `None`.

## Configuration/Dependencies
- Dependencies:
  - `qdrant_client` (embedded/local mode via `QdrantClient(location=":memory:")` or `QdrantClient(path=...)`)
  - `numpy`
- Initialization requirement:
  - You must call `initialize()` before any operation; otherwise `RuntimeError("Adapter not initialized")` is raised.
- Persistence:
  - `storage_path=":memory:"` uses in-memory storage.
  - Any other `storage_path` is treated as a directory for local persistence (created if missing).

## Usage
```python
import numpy as np

from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import QdrantInMemoryAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantInMemoryAdapter(storage_path=":memory:")
adapter.initialize()

adapter.create_collection("docs", dimension=3, distance_metric="cosine")

adapter.store_vectors(
    "docs",
    [
        VectorDocument(id="doc-1", vector=np.array([1.0, 0.0, 0.0]), metadata={"type": "a"}, payload={"text": "hello"}),
        VectorDocument(id="doc-2", vector=np.array([0.0, 1.0, 0.0]), metadata={"type": "b"}, payload={"text": "world"}),
    ],
)

results = adapter.search(
    "docs",
    query_vector=np.array([0.9, 0.1, 0.0]),
    k=1,
    filter={"type": "a"},
    include_vectors=False,
)

print(results[0].id, results[0].score, results[0].payload)

adapter.close()
```

## Caveats
- IDs are mapped to Qdrant point IDs using a deterministic UUIDv5 derived from the string `vector_id`; changing an ID changes the stored point key.
- `update_vector(..., metadata=..., payload=...)` sets payload keys provided, but does not explicitly remove keys that were previously stored and are now omitted.
- Search filters are exact matches only (via `MatchValue`); no range or full-text filtering is implemented here.
