# IVectorStorePort

## What it is
- An abstract interface (port) for a vector store backend.
- Defines common operations for managing collections and storing/searching vector documents.
- Includes two data models used by the interface: `VectorDocument` and `SearchResult`.

## Public API

### Data classes

- `VectorDocument`
  - Purpose: Represents a stored vector item.
  - Fields:
    - `id: str` — unique identifier.
    - `vector: np.ndarray` — embedding vector.
    - `metadata: Dict[str, Any]` — associated metadata.
    - `payload: Optional[Dict[str, Any]] = None` — optional extra payload.

- `SearchResult`
  - Purpose: Represents a similarity search hit.
  - Fields:
    - `id: str` — identifier of the matched item.
    - `score: float` — similarity/distance score (interpretation depends on implementation).
    - `vector: Optional[np.ndarray] = None` — optionally returned vector.
    - `metadata: Optional[Dict[str, Any]] = None` — optionally returned metadata.
    - `payload: Optional[Dict[str, Any]] = None` — optionally returned payload.

### Abstract interface: `IVectorStorePort(ABC)`
Implementations must provide:

- `initialize() -> None`
  - Initialize the vector store client/resources.

- `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
  - Create a named collection with a fixed vector dimension and distance metric.

- `delete_collection(collection_name: str) -> None`
  - Delete a collection.

- `list_collections() -> List[str]`
  - List existing collection names.

- `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`
  - Insert/store multiple vectors into a collection.

- `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
  - Run a k-NN search with optional filtering and output controls.

- `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
  - Fetch a vector document by ID.

- `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
  - Update an existing vector document (vector and/or metadata and/or payload).

- `delete_vectors(collection_name: str, vector_ids: List[str]) -> None`
  - Delete multiple vectors by ID.

- `count_vectors(collection_name: str) -> int`
  - Return the number of vectors in a collection.

- `close() -> None`
  - Release resources/close connections.

## Configuration/Dependencies
- Depends on:
  - `numpy` (`np.ndarray` for vectors)
  - Python standard library: `abc`, `dataclasses`, `typing`

## Usage

```python
import numpy as np
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort, VectorDocument
)

# You must provide an implementation of IVectorStorePort.
store: IVectorStorePort = ...  # e.g., adapter for a specific vector DB

store.initialize()
store.create_collection("my_collection", dimension=3, distance_metric="cosine")

docs = [
    VectorDocument(id="a", vector=np.array([1.0, 0.0, 0.0]), metadata={"type": "demo"}),
    VectorDocument(id="b", vector=np.array([0.0, 1.0, 0.0]), metadata={"type": "demo"}),
]
store.store_vectors("my_collection", docs)

results = store.search("my_collection", query_vector=np.array([1.0, 0.1, 0.0]), k=2)
for r in results:
    print(r.id, r.score)

store.close()
```

## Caveats
- This file defines an interface only; all behavior (persistence, scoring semantics, filtering rules, validation) is determined by the concrete implementation.
- `distance_metric` is passed as a string (default `"cosine"`); supported values (and how `score` is computed) are implementation-specific.
