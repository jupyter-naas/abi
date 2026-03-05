# VectorStoreService

## What it is
- A service wrapper around an `IVectorStorePort` adapter that manages vector-collection lifecycle and CRUD/search operations.
- Provides input validation, initialization/teardown handling, and minimal logging.

## Public API
### Class: `VectorStoreService(ServiceBase)`
- **`__init__(adapter: IVectorStorePort)`**: Create the service with a concrete vector store adapter.
- **`initialize() -> None`**: Initialize the underlying adapter once (idempotent).
- **`ensure_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", recreate: bool = False, **kwargs) -> None`**
  - Ensure a collection exists; optionally recreate it.
  - Uses adapter `list_collections()`, `delete_collection()`, `create_collection()`.
- **`add_documents(collection_name: str, ids: List[str], vectors: List[np.ndarray], metadata: Optional[List[Dict[str, Any]]] = None, payloads: Optional[List[Dict[str, Any]]] = None) -> None`**
  - Validate lengths and store documents as `VectorDocument` via `adapter.store_vectors(...)`.
- **`search_similar(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`**
  - Perform similarity search via `adapter.search(...)`.
  - Optionally filters results by `score_threshold`.
- **`get_document(collection_name: str, document_id: str, include_vector: bool = True) -> Optional[VectorDocument]`**
  - Fetch a document via `adapter.get_vector(...)`.
- **`update_document(collection_name: str, document_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`**
  - Update fields via `adapter.update_vector(...)`.
  - Requires at least one of `vector`, `metadata`, or `payload`.
- **`delete_documents(collection_name: str, document_ids: List[str]) -> None`**
  - Delete documents via `adapter.delete_vectors(...)`.
- **`get_collection_size(collection_name: str) -> int`**
  - Count vectors via `adapter.count_vectors(...)`.
- **`list_collections() -> List[str]`**
  - List collections via `adapter.list_collections()`.
- **`delete_collection(collection_name: str) -> None`**
  - Delete a collection via `adapter.delete_collection(...)`.
- **`close() -> None`**
  - Close the adapter if initialized; resets internal initialized flag.

## Configuration/Dependencies
- **Adapter dependency:** requires an implementation of `IVectorStorePort`.
- **Types used:** `VectorDocument`, `SearchResult` imported from `.IVectorStorePort`.
- **Numerical vectors:** uses `numpy.ndarray` for vector representations.
- **Logging:** uses standard `logging` (`logger = logging.getLogger(__name__)`).

## Usage
```python
import numpy as np
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

# adapter must implement IVectorStorePort (not shown here)
adapter = ...  # provide a concrete adapter
svc = VectorStoreService(adapter)

svc.ensure_collection("my_collection", dimension=3, distance_metric="cosine")

svc.add_documents(
    "my_collection",
    ids=["doc1", "doc2"],
    vectors=[np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])],
    metadata=[{"tag": "a"}, {"tag": "b"}],
)

results = svc.search_similar(
    "my_collection",
    query_vector=np.array([1.0, 0.0, 0.0]),
    k=5,
    score_threshold=0.5,
)

doc = svc.get_document("my_collection", "doc1", include_vector=True)
svc.update_document("my_collection", "doc1", metadata={"tag": "updated"})
svc.delete_documents("my_collection", ["doc2"])

svc.close()
```

## Caveats
- `add_documents` enforces:
  - `ids` and `vectors` must be non-empty.
  - `len(ids) == len(vectors)`.
  - If provided, `metadata` and `payloads` must match `len(ids)`.
- `search_similar` requires `k > 0`.
- `update_document` requires at least one of `vector`, `metadata`, or `payload` to be provided.
- Initialization is lazy: most methods call `initialize()` internally; `close()` only closes if previously initialized.
