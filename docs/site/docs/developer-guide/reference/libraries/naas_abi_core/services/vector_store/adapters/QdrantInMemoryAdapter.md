# `QdrantInMemoryAdapter`

## What it is
- A local (embedded) Qdrant vector store adapter implementing `IVectorStorePort`.
- Supports:
  - Ephemeral in-memory mode (`storage_path=":memory:"`)
  - Filesystem-backed persistence (`storage_path="<dir>"`)
- Provides collection management plus CRUD/search/list operations for vector documents.

## Public API

### Class: `QdrantInMemoryAdapter(IVectorStorePort)`
#### `__init__(storage_path: str = ":memory:", timeout: int = 300) -> None`
- Stores configuration; does not create the Qdrant client yet.
- Parameters:
  - `storage_path`: `":memory:"` for in-memory; otherwise a directory path for persistence.
  - `timeout`: passed to `QdrantClient`.

#### `initialize() -> None`
- Creates the embedded `QdrantClient` if not already initialized.
- If `storage_path != ":memory:"`, creates the directory if needed.

#### `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
- Creates a collection with a single vector field of the given size and distance metric.
- Supported `distance_metric` values:
  - `"cosine"`, `"euclidean"`, `"dot"` (unknown values default to cosine)
- `**kwargs` are forwarded to `client.create_collection(...)`.

#### `delete_collection(collection_name: str) -> None`
- Deletes the collection.

#### `list_collections() -> list[str]`
- Lists collection names.

#### `store_vectors(collection_name: str, documents: list[VectorDocument]) -> None`
- Upserts a batch of vectors.
- Stores vector data in two places:
  - Qdrant vector field: `doc.vector`
  - Payload: `_abi_vector` (list form of the vector)
- Payload also includes:
  - `_abi_id`: original `VectorDocument.id`
  - `payload`: `doc.payload` (if provided)
  - plus all `doc.metadata` keys (if provided)
- Raises `RuntimeError` if the upsert status is not `COMPLETED`.

#### `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: dict[str, Any] | None = None, include_vectors: bool = False, include_metadata: bool = True) -> list[SearchResult]`
- Searches the collection and returns up to `k` results.
- Optional `filter`:
  - Translated into Qdrant `Filter(must=[FieldCondition(... MatchValue ...)])` (exact matches).
- `include_vectors`:
  - If `True`, returns the vector from payload (`_abi_vector`) if present, else from `hit.vector` if available.
- `include_metadata`:
  - If `True`, returns payload keys excluding `payload`, `_abi_id`, `_abi_vector`.

#### `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> VectorDocument | None`
- Retrieves a single document by `vector_id`.
- Returns `None` if not found.
- Vector resolution when `include_vector=True`:
  - Prefers payload `_abi_vector`, else `point.vector`, else empty `np.array([])`.

#### `update_vector(collection_name: str, vector_id: str, vector: np.ndarray | None = None, metadata: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> None`
- Updates vector and/or payload:
  - If `vector` is provided: calls `client.update_vectors(...)`.
  - If any of `vector`, `metadata`, `payload` are provided: calls `client.set_payload(...)` with:
    - `_abi_id`: `vector_id`
    - `_abi_vector`: only if `vector` is provided
    - `payload`: only if `payload` is provided
    - plus metadata keys (if provided)

#### `delete_vectors(collection_name: str, vector_ids: list[str]) -> None`
- Deletes multiple vectors by id (mapped to Qdrant point IDs internally).

#### `count_vectors(collection_name: str) -> int`
- Returns `points_count` from collection info (defaults to `0` if missing).

#### `list_vectors(collection_name: str, limit: int = 100, cursor: str | None = None, include_vectors: bool = False) -> VectorPage`
- Scrolls documents in point-id order.
- `cursor` is the Qdrant scroll offset (a point id).
- Always requests `with_vectors=False`; if `include_vectors=True`, vectors are read from payload `_abi_vector`.
- Raises `ValueError` if `limit <= 0`.

#### `get_collection_info(collection_name: str) -> CollectionInfo`
- Returns `CollectionInfo` with:
  - `name`
  - `dimension` / `distance_metric` (when determinable from single-vector config)
  - `size` (`points_count`)

#### `close() -> None`
- Closes the underlying client and resets it to `None`.

## Configuration/Dependencies
- Python dependencies:
  - `qdrant_client`
  - `numpy`
- Initialization:
  - Call `initialize()` before any operation; otherwise `RuntimeError("Adapter not initialized")`.
- Storage modes:
  - `storage_path=":memory:"` uses embedded in-memory Qdrant.
  - Any other `storage_path` uses embedded persistent storage at that directory.

## Usage
```python
import numpy as np
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import QdrantInMemoryAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantInMemoryAdapter(storage_path=":memory:")
adapter.initialize()

adapter.create_collection("docs", dimension=3, distance_metric="cosine")

adapter.store_vectors("docs", [
    VectorDocument(id="doc-1", vector=np.array([1.0, 0.0, 0.0]), metadata={"type": "a"}, payload={"text": "hello"}),
    VectorDocument(id="doc-2", vector=np.array([0.0, 1.0, 0.0]), metadata={"type": "b"}, payload={"text": "world"}),
])

hits = adapter.search(
    "docs",
    query_vector=np.array([0.9, 0.1, 0.0]),
    k=1,
    filter={"type": "a"},
    include_vectors=False,
)

print(hits[0].id, hits[0].score, hits[0].payload)

adapter.close()
```

## Caveats
- You must call `initialize()` before using the adapter.
- IDs are mapped to Qdrant point IDs using deterministic UUIDv5 (`uuid5(NAMESPACE_URL, vector_id)`); changing the external id changes the stored point id.
- Filters are exact-match only (`MatchValue`); no range/fuzzy/full-text filtering is implemented.
- `update_vector(...)` sets provided payload keys but does not remove previously stored keys that are omitted in later updates.
- `list_vectors(..., include_vectors=True)` relies on vectors being present in payload under `_abi_vector` (vectors are not requested from Qdrant during scroll).
