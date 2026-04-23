# QdrantAdapter

## What it is
- A Qdrant-backed implementation of `IVectorStorePort` for creating collections, storing vectors, searching, retrieving, updating, deleting, and counting vector documents.
- Wraps `qdrant_client.QdrantClient` and translates between Qdrant points and the project’s `VectorDocument` / `SearchResult` models.

## Public API
### Class: `QdrantAdapter(IVectorStorePort)`
#### `__init__(host="localhost", port=6333, api_key=None, https=False, timeout=300)`
- Configures connection parameters; does **not** connect until `initialize()` is called.

#### `initialize() -> None`
- Creates a `QdrantClient` if not already created.

#### `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
- Creates a Qdrant collection with a single vector configuration:
  - `size=dimension`
  - `distance` mapped from `distance_metric` (`cosine`, `euclidean`, `dot`; defaults to cosine on unknown values).

#### `delete_collection(collection_name: str) -> None`
- Deletes a collection.

#### `list_collections() -> List[str]`
- Returns collection names.

#### `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`
- Upserts points built from `VectorDocument`:
  - `id` from `doc.id`
  - `vector` from `doc.vector.tolist()`
  - payload merges:
    - `doc.metadata` (top-level keys)
    - `doc.payload` stored under key `"payload"` if provided
- Raises `RuntimeError` if the upsert status is not `COMPLETED`.

#### `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
- Executes a nearest-neighbor query with optional exact-match filtering:
  - `filter` is converted into Qdrant `Filter(must=[FieldCondition(key=..., match=MatchValue(value=...))...])`
- Controls returned fields:
  - `include_vectors` toggles `with_vectors`
  - `include_metadata` toggles `with_payload`
- Builds `SearchResult`:
  - `id` as `str(hit.id)`
  - `score` from Qdrant
  - `vector` as `np.array(hit.vector)` if present
  - `metadata` as `dict(hit.payload)` when payload is present and `include_metadata=True`
  - `payload` extracted from `hit.payload["payload"]` when present

#### `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
- Retrieves a single point by id.
- Always requests payload (`with_payload=True`); vector is optional via `include_vector`.
- Returns `None` if not found.
- Maps payload:
  - `metadata` = payload entries excluding `"payload"`
  - `payload` = payload entry `"payload"` (if present)

#### `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
- If `vector` is provided: updates vector via `update_vectors`.
- If `metadata` and/or `payload` is provided: sets payload via `set_payload`:
  - merges `metadata` keys at top-level
  - stores `payload` under `"payload"`

#### `delete_vectors(collection_name: str, vector_ids: List) -> None`
- Deletes points by id list via `PointIdsList`.
- Accepts ids castable to `List[Union[int, str, UUID]]`.

#### `count_vectors(collection_name: str) -> int`
- Returns `collection_info.indexed_vectors_count` or `0`.

#### `close() -> None`
- Closes the underlying Qdrant client and resets it to `None`.

## Configuration/Dependencies
- Requires:
  - `qdrant-client`
  - `numpy`
- Connection parameters:
  - `host`, `port`, `api_key`, `https`, `timeout`
- Must call `initialize()` before any operation; otherwise raises `RuntimeError("Adapter not initialized")`.

## Usage
```python
import numpy as np
from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantAdapter(host="localhost", port=6333)
adapter.initialize()

adapter.create_collection(collection_name="docs", dimension=3, distance_metric="cosine")

docs = [
    VectorDocument(
        id="doc-1",
        vector=np.array([0.1, 0.2, 0.3], dtype=float),
        metadata={"source": "demo"},
        payload={"text": "hello"},
    )
]
adapter.store_vectors("docs", docs)

results = adapter.search(
    "docs",
    query_vector=np.array([0.1, 0.2, 0.25], dtype=float),
    k=5,
    filter={"source": "demo"},
    include_vectors=False,
    include_metadata=True,
)
print([(r.id, r.score, r.payload) for r in results])

doc = adapter.get_vector("docs", "doc-1", include_vector=True)
print(doc.id, doc.metadata, doc.payload, doc.vector)

adapter.close()
```

## Caveats
- Payload handling reserves the `"payload"` key:
  - `VectorDocument.payload` is stored under `"payload"`.
  - All other payload keys are treated as metadata.
- `search(include_metadata=False)` disables returning any payload/metadata (and thus `SearchResult.payload` will be `None` even if stored).
- `count_vectors()` uses `indexed_vectors_count`, which may differ from total stored points depending on Qdrant indexing/state.
