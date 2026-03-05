# IVectorStorePort

## What it is
- An abstract interface (port) for a vector store backend.
- Defines the required operations for managing collections, storing vectors, searching, and lifecycle management.
- Includes simple data models for input (`VectorDocument`) and output (`SearchResult`).

## Public API

### Data classes

- `VectorDocument`
  - Purpose: Represents a vector record to store or retrieve.
  - Fields:
    - `id: str`
    - `vector: np.ndarray`
    - `metadata: Dict[str, Any]`
    - `payload: Optional[Dict[str, Any]] = None`

- `SearchResult`
  - Purpose: Represents a single search hit.
  - Fields:
    - `id: str`
    - `score: float`
    - `vector: Optional[np.ndarray] = None`
    - `metadata: Optional[Dict[str, Any]] = None`
    - `payload: Optional[Dict[str, Any]] = None`

### Abstract class: `IVectorStorePort`
Implementations must provide:

- `initialize() -> None`
  - Initialize/connect the vector store.

- `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
  - Create a collection/index with a fixed vector dimension and a distance metric.

- `delete_collection(collection_name: str) -> None`
  - Remove an existing collection.

- `list_collections() -> List[str]`
  - List available collection names.

- `store_vectors(collection_name: str, documents: List[VectorDocument]) -> None`
  - Insert/upsert documents into a collection.

- `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False, include_metadata: bool = True) -> List[SearchResult]`
  - Search for nearest vectors.
  - Parameters:
    - `k`: number of results
    - `filter`: optional filtering criteria (backend-defined)
    - `include_vectors`: whether to include vectors in results
    - `include_metadata`: whether to include metadata in results

- `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]`
  - Fetch a single vector record by id.

- `update_vector(collection_name: str, vector_id: str, vector: Optional[np.ndarray] = None, metadata: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> None`
  - Update parts of an existing record (vector and/or metadata and/or payload).

- `delete_vectors(collection_name: str, vector_ids: List[str]) -> None`
  - Delete multiple vectors by id.

- `count_vectors(collection_name: str) -> int`
  - Return the number of vectors in a collection.

- `close() -> None`
  - Close/release resources.

## Configuration/Dependencies
- Depends on:
  - `numpy` (`np.ndarray` for vectors)
  - Standard library: `abc`, `dataclasses`, `typing`

## Usage

Minimal example showing how to define an implementation and call the interface:

```python
import numpy as np
from typing import List, Dict, Any, Optional
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort, VectorDocument, SearchResult
)

class InMemoryVectorStore(IVectorStorePort):
    def __init__(self):
        self._collections = {}

    def initialize(self) -> None:
        pass

    def create_collection(self, collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None:
        self._collections[collection_name] = {"dim": dimension, "docs": {}}

    def delete_collection(self, collection_name: str) -> None:
        self._collections.pop(collection_name, None)

    def list_collections(self) -> List[str]:
        return list(self._collections.keys())

    def store_vectors(self, collection_name: str, documents: List[VectorDocument]) -> None:
        for d in documents:
            self._collections[collection_name]["docs"][d.id] = d

    def search(self, collection_name: str, query_vector: np.ndarray, k: int = 10,
               filter: Optional[Dict[str, Any]] = None, include_vectors: bool = False,
               include_metadata: bool = True) -> List[SearchResult]:
        return []  # backend-specific

    def get_vector(self, collection_name: str, vector_id: str, include_vector: bool = True) -> Optional[VectorDocument]:
        doc = self._collections[collection_name]["docs"].get(vector_id)
        if doc and not include_vector:
            return VectorDocument(id=doc.id, vector=np.array([]), metadata=doc.metadata, payload=doc.payload)
        return doc

    def update_vector(self, collection_name: str, vector_id: str,
                      vector: Optional[np.ndarray] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      payload: Optional[Dict[str, Any]] = None) -> None:
        doc = self._collections[collection_name]["docs"][vector_id]
        self._collections[collection_name]["docs"][vector_id] = VectorDocument(
            id=doc.id,
            vector=doc.vector if vector is None else vector,
            metadata=doc.metadata if metadata is None else metadata,
            payload=doc.payload if payload is None else payload,
        )

    def delete_vectors(self, collection_name: str, vector_ids: List[str]) -> None:
        for vid in vector_ids:
            self._collections[collection_name]["docs"].pop(vid, None)

    def count_vectors(self, collection_name: str) -> int:
        return len(self._collections[collection_name]["docs"])

    def close(self) -> None:
        pass

store = InMemoryVectorStore()
store.initialize()
store.create_collection("my_collection", dimension=3)
store.store_vectors("my_collection", [
    VectorDocument(id="a", vector=np.array([1.0, 0.0, 0.0]), metadata={"type": "demo"})
])
print(store.count_vectors("my_collection"))
```

## Caveats
- `IVectorStorePort` is an abstract interface; it provides no concrete storage/search behavior.
- The meaning/format of `distance_metric`, `filter`, and `**kwargs` is implementation-defined.
