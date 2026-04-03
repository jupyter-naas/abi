# QdrantInMemoryAdapter

## What it is
- An in-memory implementation of `IVectorStorePort` that mimics basic Qdrant-like collection/vector operations.
- Stores vectors and associated metadata/payload in Python memory and supports similarity search with simple filtering.

## Public API
### Class: `QdrantInMemoryAdapter(IVectorStorePort)`
- `__init__()`: Creates an adapter instance (not initialized).
- `initialize() -> None`: Marks the adapter as ready; must be called before other operations.
- `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`  
  - Creates a new in-memory collection with fixed vector dimension and distance metric.
- `delete_collection(collection_name: str) -> None`  
  - Deletes an existing collection.
- `list_collections() -> List[str]`  
  - Returns all collection names.
- `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`  
  - Inserts or overwrites documents by `id`. Validates vector dimension.
- `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`  
  - Returns top-`k` results sorted by descending score.
  - Optional exact-match filter over merged `metadata` and `payload` (payload is exposed under key `"payload"` for filtering).
  - Can include stored vectors and/or metadata/payload in results.
- `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`  
  - Returns a stored document or `None` if not found.
  - If `include_vector` is `False`, returns an empty numpy array for `vector`.
- `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`  
  - Updates vector and/or metadata and/or payload for an existing document.
  - Validates vector dimension when updating the vector.
- `delete_vectors(collection_name: str, vector_ids: List) -> None`  
  - Deletes documents by id (missing ids are ignored).
- `count_vectors(collection_name: str) -> int`  
  - Returns number of stored documents in the collection.
- `close() -> None`  
  - Marks adapter as closed/uninitialized.

## Configuration/Dependencies
- Depends on `numpy`.
- Uses:
  - `VectorDocument` and `SearchResult` types from `..IVectorStorePort`.
- Distance metrics:
  - `"euclidean"`: score is negative Euclidean distance (`-||q - v||`).
  - `"dot"`: score is dot product.
  - Any other value (default `"cosine"`): cosine similarity; returns `0.0` if either vector has zero norm.

## Usage
```python
import numpy as np

from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument

adapter = QdrantInMemoryAdapter()
adapter.initialize()

adapter.create_collection("docs", dimension=3, distance_metric="cosine")

adapter.store_vectors(
    "docs",
    [
        VectorDocument(id="a", vector=np.array([1, 0, 0]), metadata={"type": "x"}, payload={"text": "A"}),
        VectorDocument(id="b", vector=np.array([0, 1, 0]), metadata={"type": "y"}, payload={"text": "B"}),
    ],
)

results = adapter.search(
    "docs",
    query_vector=np.array([1, 0, 0]),
    k=1,
    filter={"type": "x"},
    include_vectors=False,
    include_metadata=True,
)

print(results[0].id, results[0].score, results[0].metadata, results[0].payload)

adapter.close()
```

## Caveats
- Must call `initialize()` before any operation; otherwise raises `RuntimeError("Adapter not initialized")`.
- Collection vector dimension is enforced; mismatches raise `ValueError`.
- Filtering is strict equality on keys/values; filter keys are checked against:
  - document `metadata`
  - plus `"payload"` (the entire payload dict) when payload is present.
- `store_vectors()` overwrites existing documents with the same `id`.
- In-memory only: data is lost when the process ends or after `close()`/reinitialization.
