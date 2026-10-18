# QdrantAdapter

## What it is
- A Qdrant-backed implementation of `IVectorStorePort`.
- Manages collections and vector documents in Qdrant, mapping between Qdrant points and the project models:
  - `VectorDocument`, `SearchResult`, `VectorPage`, `CollectionInfo`.

## Public API

### Class: `QdrantAdapter(IVectorStorePort)`
Qdrant adapter that wraps `qdrant_client.QdrantClient`.

#### `__init__(host="localhost", port=6333, api_key=None, https=False, timeout=300)`
- Stores connection parameters; does not create the client until `initialize()`.

#### `initialize() -> None`
- Creates `QdrantClient` if not already initialized.

#### `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
- Creates a collection with a single vector config:
  - `VectorParams(size=dimension, distance=<mapped>)`
- `distance_metric` mapping:
  - `"cosine"`, `"euclidean"`, `"dot"`; defaults to cosine if unknown.

#### `delete_collection(collection_name: str) -> None`
- Deletes the collection.

#### `list_collections() -> list[str]`
- Returns collection names.

#### `store_vectors(collection_name: str, documents: list[VectorDocument]) -> None`
- Upserts documents as Qdrant points (`PointStruct`):
  - `id = doc.id`
  - `vector = doc.vector.tolist()`
  - payload:
    - merges `doc.metadata` at top-level
    - stores `doc.payload` under reserved key `"payload"`
- Raises `RuntimeError` if Qdrant update status is not `COMPLETED`.

#### `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: dict[str, Any] | None = None, include_vectors: bool = False, include_metadata: bool = True) -> list[SearchResult]`
- Executes `query_points`:
  - `query = query_vector.tolist()`
  - `limit = k`
  - optional exact-match filter:
    - builds `Filter(must=[FieldCondition(key=..., match=MatchValue(value=...)), ...])`
  - `with_vectors = include_vectors`
  - `with_payload = include_metadata`
- Maps hits into `SearchResult`:
  - `id = str(hit.id)`
  - `score = hit.score`
  - `vector = np.array(hit.vector)` if present, else `None`
  - `metadata = dict(hit.payload)` if payload present and `include_metadata=True`, else `None`
  - `payload = hit.payload.get("payload")` if present, else `None`

#### `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> VectorDocument | None`
- Retrieves a single point by ID via `retrieve(ids=[vector_id])`.
- Always requests payload; vector inclusion controlled by `include_vector`.
- Returns `None` if not found.
- Metadata/payload mapping:
  - `metadata` = payload entries excluding `"payload"`
  - `payload` = payload `"payload"` (if present)
  - if no vector is returned, `vector` is `np.array([])`.

#### `update_vector(collection_name: str, vector_id: str, vector: np.ndarray | None = None, metadata: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> None`
- If `vector` is provided: updates vector via `update_vectors([PointVectors(...)])`.
- If `metadata` and/or `payload` provided: sets payload via `set_payload`:
  - merges `metadata` at top-level
  - stores `payload` under `"payload"`.

#### `delete_vectors(collection_name: str, vector_ids: list) -> None`
- Deletes points by IDs using `PointIdsList(points=<casted ids>)`.

#### `count_vectors(collection_name: str) -> int`
- Returns `collection_info.indexed_vectors_count` or `0`.

#### `list_vectors(collection_name: str, limit: int = 100, cursor: str | None = None, include_vectors: bool = False) -> VectorPage`
- Scrolls points in point-id order using `client.scroll`.
- Cursor semantics:
  - cursor is a point id as text; if it is digit-only, it is converted to `int`, otherwise left as `str`.
- Always includes payload; vectors are included only if `include_vectors=True`.
- Returns `VectorPage(documents=[...], next_cursor=<next_offset as str or None>)`.
- Raises `ValueError` if `limit <= 0`.

#### `get_collection_info(collection_name: str) -> CollectionInfo`
- Fetches Qdrant collection info and returns:
  - name, dimension, distance_metric (string), size (`points_count`).
- Intended for single-vector collections; named vectors are not handled explicitly.

#### `close() -> None`
- Closes the underlying client (if any) and resets it to `None`.

## Configuration/Dependencies
- Dependencies:
  - `qdrant-client`
  - `numpy`
- Connection parameters:
  - `host`, `port`, `api_key`, `https`, `timeout`
- All operations require prior `initialize()`; otherwise `RuntimeError("Adapter not initialized")`.

## Usage
```python
import numpy as np
from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantAdapter(host="localhost", port=6333)
adapter.initialize()

adapter.create_collection("docs", dimension=3, distance_metric="cosine")

adapter.store_vectors(
    "docs",
    [
        VectorDocument(
            id="doc-1",
            vector=np.array([0.1, 0.2, 0.3], dtype=float),
            metadata={"source": "demo"},
            payload={"text": "hello"},
        )
    ],
)

hits = adapter.search(
    "docs",
    query_vector=np.array([0.1, 0.2, 0.25], dtype=float),
    k=5,
    filter={"source": "demo"},
)
print([(h.id, h.score, h.payload) for h in hits])

page = adapter.list_vectors("docs", limit=10, include_vectors=False)
print([d.id for d in page.documents], page.next_cursor)

adapter.close()
```

## Caveats
- Reserved payload key: `"payload"`
  - `VectorDocument.payload` is stored under `"payload"`.
  - all other stored payload keys are treated as `metadata` on read.
- `search(include_metadata=False)` disables payload retrieval; `SearchResult.payload`/`metadata` will be `None` even if stored.
- `count_vectors()` uses `indexed_vectors_count` (may differ from total points depending on Qdrant state/indexing).
- When a vector is not returned (e.g., `include_vector=False`), `get_vector()` and `list_vectors()` set `vector` to `np.array([])`.
