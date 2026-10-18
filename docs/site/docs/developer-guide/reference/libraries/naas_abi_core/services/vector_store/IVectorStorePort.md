# IVectorStorePort

## What it is
- An abstract interface (port) for vector store backends.
- Defines common operations for:
  - Collection lifecycle (create/delete/list/info)
  - Vector document CRUD
  - Similarity search
  - Paging/streaming iteration over all vectors in a collection
- Provides shared data models used by implementations and callers.

## Public API

### Constants
- `STREAM_PAGE: int = 500`
  - Default page size used by `list_vectors_stream()` when iterating via `list_vectors()`.

### Data classes

- `VectorDocument`
  - Represents a stored vector item.
  - Fields:
    - `id: str`
    - `vector: np.ndarray`
    - `metadata: dict[str, Any]`
    - `payload: dict[str, Any] | None = None`

- `VectorPage`
  - One page of documents in a stable, adapter-defined order.
  - Fields:
    - `documents: list[VectorDocument]`
    - `next_cursor: str | None = None` (opaque cursor; `None` means last page)

- `CollectionInfo`
  - Collection metadata and size.
  - Fields:
    - `name: str`
    - `dimension: int | None`
    - `distance_metric: str | None`
    - `size: int`

- `SearchResult`
  - A similarity search hit.
  - Fields:
    - `id: str`
    - `score: float`
    - `vector: np.ndarray | None = None`
    - `metadata: dict[str, Any] | None = None`
    - `payload: dict[str, Any] | None = None`

### Abstract interface: `IVectorStorePort(ABC)`
Concrete adapters must implement the abstract methods below.

- `initialize() -> None`
  - Initialize client/resources.

- `create_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", **kwargs) -> None`
  - Create a collection with a fixed vector dimension and distance metric.

- `delete_collection(collection_name: str) -> None`
  - Delete a collection.

- `list_collections() -> list[str]`
  - List collection names.

- `store_vectors(collection_name: str, documents: list[VectorDocument]) -> None`
  - Insert/store multiple documents.

- `search(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: dict[str, Any] | None = None, include_vectors: bool = False, include_metadata: bool = True) -> list[SearchResult]`
  - Run a k-NN search with optional filtering and output controls.

- `get_vector(collection_name: str, vector_id: str, include_vector: bool = True) -> VectorDocument | None`
  - Retrieve a document by ID.

- `update_vector(collection_name: str, vector_id: str, vector: np.ndarray | None = None, metadata: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> None`
  - Update vector and/or metadata and/or payload.

- `delete_vectors(collection_name: str, vector_ids: list[str]) -> None`
  - Delete multiple documents by ID.

- `count_vectors(collection_name: str) -> int`
  - Return the number of documents in a collection.

- `list_vectors(collection_name: str, limit: int = 100, cursor: str | None = None, include_vectors: bool = False) -> VectorPage`
  - Page through documents (metadata and payload included).
  - Note: when `include_vectors=False`, each returned document’s `vector` is an empty array (per docstring).

- `list_vectors_stream(collection_name: str, *, include_vectors: bool = False) -> contextmanager[Iterator[VectorDocument]]`
  - Context-managed, lazy iteration over every document in `list_vectors()` order.
  - Default implementation repeatedly calls `list_vectors()` using pages of `STREAM_PAGE`.

- `get_collection_info(collection_name: str) -> CollectionInfo`
  - Return dimension and distance metric (`None` when unknown) and size.

- `close() -> None`
  - Release resources/close connections.

## Configuration/Dependencies
- Requires `numpy` (`np.ndarray` vectors).
- Uses standard library:
  - `abc` (abstract base class)
  - `dataclasses`
  - `contextlib.contextmanager`
  - `collections.abc.Iterator`
  - `typing.Any`

## Usage

```python
import numpy as np
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort, VectorDocument
)

store: IVectorStorePort = ...  # provide a concrete adapter

store.initialize()
store.create_collection("my_collection", dimension=3, distance_metric="cosine")

store.store_vectors(
    "my_collection",
    [
        VectorDocument(id="a", vector=np.array([1.0, 0.0, 0.0]), metadata={"tag": "x"}),
        VectorDocument(id="b", vector=np.array([0.0, 1.0, 0.0]), metadata={"tag": "y"}),
    ],
)

hits = store.search("my_collection", query_vector=np.array([1.0, 0.1, 0.0]), k=2)
for h in hits:
    print(h.id, h.score)

with store.list_vectors_stream("my_collection") as docs:
    for doc in docs:
        print(doc.id)

store.close()
```

## Caveats
- This file defines an interface plus a default `list_vectors_stream()` implementation; persistence, scoring semantics, filtering behavior, and supported distance metrics are adapter-specific.
- `VectorPage.next_cursor` is opaque and must be passed back unchanged to continue paging.
- `list_vectors(include_vectors=False)` returns documents with an empty `vector` array (as documented).
