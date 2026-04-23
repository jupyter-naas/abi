# VectorStoreService

## What it is
- A service wrapper around an `IVectorStorePort` adapter that manages vector-store collections and documents.
- Provides initialization/cleanup and input validation before delegating operations to the underlying adapter.

## Public API

### Class: `VectorStoreService(adapter: IVectorStorePort)`
- **Purpose:** High-level operations for vector collections and vector documents using a pluggable adapter.

#### Methods
- `initialize() -> None`
  - Initializes the underlying adapter once (idempotent).
- `ensure_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", recreate: bool = False, **kwargs) -> None`
  - Creates a collection if missing; optionally recreates (delete + create) if it already exists.
- `add_documents(collection_name: str, ids: List[str], vectors: List[np.ndarray], metadata: Optional[List[Dict[str, Any]]] = None, payloads: Optional[List[Dict[str, Any]]] = None) -> None`
  - Validates input lengths and stores vectors as `VectorDocument` entries via the adapter.
- `search_similar(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
  - Performs k-NN search via the adapter; optionally filters results by `score_threshold`.
- `get_document(collection_name: str, document_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
  - Retrieves a single document via the adapter.
- `update_document(collection_name: str, document_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
  - Updates an existing document; requires at least one of `vector`, `metadata`, or `payload`.
- `delete_documents(collection_name: str, document_ids: List[str]) -> None`
  - Deletes documents by ID list (must be non-empty).
- `get_collection_size(collection_name: str) -> int`
  - Returns vector count in a collection.
- `list_collections() -> List[str]`
  - Lists available collections.
- `delete_collection(collection_name: str) -> None`
  - Deletes a collection.
- `close() -> None`
  - Closes the adapter if initialized and resets internal state.

## Configuration/Dependencies
- **Adapter required:** `IVectorStorePort`
  - Must provide methods used here: `initialize`, `close`, `create_collection`, `delete_collection`, `list_collections`, `store_vectors`, `search`, `get_vector`, `update_vector`, `delete_vectors`, `count_vectors`.
- **Data structures (from `.IVectorStorePort`):**
  - `VectorDocument`, `SearchResult`
- **Third-party:**
  - `numpy` for vector representations (`np.ndarray`).
- **Logging:**
  - Uses Python `logging` (`logger = logging.getLogger(__name__)`).

## Usage

```python
import numpy as np
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

# adapter must implement IVectorStorePort
adapter = ...  # provide a concrete adapter
svc = VectorStoreService(adapter)

svc.ensure_collection("docs", dimension=3)

svc.add_documents(
    collection_name="docs",
    ids=["a", "b"],
    vectors=[np.array([1, 0, 0]), np.array([0, 1, 0])],
    metadata=[{"type": "x"}, {"type": "y"}],
)

results = svc.search_similar("docs", query_vector=np.array([1, 0, 0]), k=2)
doc = svc.get_document("docs", "a")

svc.close()
```

## Caveats
- `add_documents` requires:
  - `ids` and `vectors` are non-empty
  - `len(ids) == len(vectors)`
  - If provided, `metadata` and `payloads` lengths must match `ids`
- `search_similar` requires `k > 0`.
- `update_document` requires at least one of `vector`, `metadata`, or `payload`.
- `delete_documents` requires a non-empty `document_ids` list.
- Actual search semantics (distance metric behavior, filtering support, score meaning) are defined by the adapter implementation.
