# QdrantAdapter

## What it is
- An `IVectorStorePort` implementation backed by [Qdrant](https://qdrant.tech/) via `qdrant-client`.
- Manages collection lifecycle and CRUD/search operations for vector documents.

## Public API
### Class: `QdrantAdapter(IVectorStorePort)`
#### Constructor
- `__init__(host="localhost", port=6333, api_key=None, https=False, timeout=300)`
  - Stores connection parameters; does not connect until `initialize()`.

#### Connection lifecycle
- `initialize() -> None`
  - Creates an internal `QdrantClient` if not already created.
- `close() -> None`
  - Closes the underlying client and clears it.

#### Collections
- `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
  - Creates a Qdrant collection with a single vector field of given `dimension` and metric (`cosine`, `euclidean`, `dot`; defaults to cosine).
- `delete_collection(collection_name: str) -> None`
  - Deletes the collection.
- `list_collections() -> List[str]`
  - Returns all collection names.

#### Vectors / documents
- `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`
  - Upserts points into the collection.
  - Stores:
    - `doc.metadata` as top-level payload fields (if provided)
    - `doc.payload` under payload key `"payload"` (if provided)
  - Raises `RuntimeError` if Qdrant upsert does not complete.

- `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
  - Executes a vector similarity search.
  - Optional `filter` is translated into Qdrant `Filter(must=[FieldCondition(...), ...])` with exact `MatchValue`.
  - Controls:
    - `include_vectors`: returns vectors in results when `True`
    - `include_metadata`: returns payload as `metadata` when `True`
  - Also extracts `payload` from the stored `"payload"` key (if present).

- `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
  - Retrieves a single point by id.
  - Returns `None` if not found.
  - Separates `"payload"` from other payload keys:
    - `VectorDocument.metadata` = payload without `"payload"`
    - `VectorDocument.payload` = payload["payload"] (if present)

- `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
  - Updates vector values when `vector` is provided.
  - Updates payload when `metadata` and/or `payload` are provided:
    - `metadata` merged into payload
    - `payload` stored under `"payload"` key

- `delete_vectors(collection_name: str, vector_ids: List) -> None`
  - Deletes multiple points by id.

- `count_vectors(collection_name: str) -> int`
  - Returns `indexed_vectors_count` for the collection (or `0` if missing).

## Configuration/Dependencies
- Requires:
  - `qdrant-client`
  - `numpy`
- Connection parameters:
  - `host`, `port`, optional `api_key`, `https`, `timeout`
- Must call `initialize()` before any operation; otherwise methods raise `RuntimeError("Adapter not initialized")`.

## Usage
```python
import numpy as np
from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantAdapter(host="localhost", port=6333)
adapter.initialize()

collection = "example"
dim = 3
adapter.create_collection(collection_name=collection, dimension=dim, distance_metric="cosine")

docs = [
    VectorDocument(id="1", vector=np.array([0.1, 0.2, 0.3]), metadata={"type": "a"}, payload={"text": "hello"}),
    VectorDocument(id="2", vector=np.array([0.0, 0.1, 0.0]), metadata={"type": "b"}, payload={"text": "world"}),
]
adapter.store_vectors(collection, docs)

results = adapter.search(
    collection_name=collection,
    query_vector=np.array([0.1, 0.2, 0.25]),
    k=2,
    filter={"type": "a"},
    include_vectors=False,
    include_metadata=True,
)
print([(r.id, r.score, r.metadata, r.payload) for r in results])

doc = adapter.get_vector(collection, "1", include_vector=True)
print(doc.id, doc.vector.tolist(), doc.metadata, doc.payload)

adapter.close()
```

## Caveats
- Filtering only supports exact-match constraints via `MatchValue` for each `filter` entry; no range/complex filters are implemented here.
- `count_vectors()` uses `indexed_vectors_count`, which may differ from total points depending on Qdrant indexing/state.
- `get_vector(..., include_vector=False)` returns an empty `np.array([])` for the vector field (because the adapter constructs it from missing data).
