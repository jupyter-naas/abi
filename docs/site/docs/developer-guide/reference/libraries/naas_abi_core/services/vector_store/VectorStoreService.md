# VectorStoreService

## What it is
- A service-layer wrapper around an `IVectorStorePort` adapter.
- Provides lifecycle management (`initialize`, `close`), input validation, and optional event publication around vector-store operations (collections, documents, search, paging/streaming).

## Public API

### Class: `VectorStoreService(adapter: IVectorStorePort)`
- **Purpose:** Offer a stable, validated interface to vector store operations while delegating storage/search behavior to the injected adapter.

#### Methods
- `initialize() -> None`
  - Initializes the underlying adapter once (idempotent).

- `ensure_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", recreate: bool = False, **kwargs) -> None`
  - Ensures a collection exists; optionally recreates it (delete then create).
  - Publishes `CollectionEnsured` on success; publishes `VectorStoreError` on exceptions.

- `add_documents(collection_name: str, ids: list[str], vectors: list[np.ndarray], metadata: list[dict[str, Any]] | None = None, payloads: list[dict[str, Any]] | None = None) -> None`
  - Validates input lengths and creates `VectorDocument` objects.
  - Delegates to `adapter.store_vectors`.
  - Publishes `DocumentsAdded` on success; publishes `VectorStoreError` on exceptions.

- `search_similar(collection_name: str, query_vector: np.ndarray, k: int = 10, filter: dict[str, Any] | None = None, score_threshold: float | None = None, include_vectors: bool = False, include_metadata: bool = True) -> list[SearchResult]`
  - Delegates k-NN search to `adapter.search`.
  - Optionally filters results by `score_threshold` (`r.score >= threshold`).

- `get_document(collection_name: str, document_id: str, include_vector: bool = True) -> VectorDocument | None`
  - Delegates to `adapter.get_vector`.

- `update_document(collection_name: str, document_id: str, vector: np.ndarray | None = None, metadata: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> None`
  - Requires at least one of `vector`, `metadata`, or `payload`.
  - Delegates to `adapter.update_vector`.
  - Publishes `DocumentUpdated` on success; publishes `VectorStoreError` on exceptions.

- `delete_documents(collection_name: str, document_ids: list[str]) -> None`
  - Requires `document_ids` non-empty.
  - Delegates to `adapter.delete_vectors`.
  - Publishes `DocumentsDeleted` on success; publishes `VectorStoreError` on exceptions.

- `get_collection_size(collection_name: str) -> int`
  - Delegates to `adapter.count_vectors`.

- `list_collections() -> list[str]`
  - Delegates to `adapter.list_collections`.

- `list_documents(collection_name: str, *, limit: int = 100, cursor: str | None = None, include_vectors: bool = False) -> VectorPage`
  - Paged listing in a stable order; pass `next_cursor` from the returned `VectorPage` back as `cursor`.
  - Validates `1 <= limit <= 10_000` (`MAX_PAGE_SIZE`).
  - Delegates to `adapter.list_vectors`.

- `list_documents_stream(collection_name: str, *, include_vectors: bool = False) -> contextmanager[Iterator[VectorDocument]]`
  - Context-managed lazy iterator over all documents in `list_documents` order.
  - Delegates to `adapter.list_vectors_stream`.

- `get_collection_info(collection_name: str) -> CollectionInfo`
  - Delegates to `adapter.get_collection_info`.

- `delete_collection(collection_name: str) -> None`
  - Delegates to `adapter.delete_collection`.
  - Publishes `CollectionDeleted` on success; publishes `VectorStoreError` on exceptions.

- `close() -> None`
  - Closes the underlying adapter if initialized and resets internal state.

## Configuration/Dependencies
- **Adapter (required):** `IVectorStorePort`
  - Must provide at least: `initialize`, `close`, `create_collection`, `delete_collection`, `list_collections`, `store_vectors`, `search`, `get_vector`, `update_vector`, `delete_vectors`, `count_vectors`, `list_vectors`, `list_vectors_stream`, `get_collection_info`.
- **Types used (from `IVectorStorePort` module):**
  - `VectorDocument`, `SearchResult`, `VectorPage`, `CollectionInfo`
- **Third-party:**
  - `numpy` (`np.ndarray`) for vectors.
- **Events (optional, via `ServiceBase` wiring):**
  - Publishes: `CollectionEnsured`, `DocumentsAdded`, `DocumentUpdated`, `DocumentsDeleted`, `CollectionDeleted`
  - On exceptions publishes: `VectorStoreError`
  - Event publication is best-effort; failures are logged and do not fail vector operations.

## Usage

```python
import numpy as np
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

adapter = ...  # must implement IVectorStorePort
svc = VectorStoreService(adapter)

svc.ensure_collection("docs", dimension=3)

svc.add_documents(
    "docs",
    ids=["a", "b"],
    vectors=[np.array([1, 0, 0]), np.array([0, 1, 0])],
    metadata=[{"type": "x"}, {"type": "y"}],
)

hits = svc.search_similar("docs", query_vector=np.array([1, 0, 0]), k=2)
doc = svc.get_document("docs", "a")

page = svc.list_documents("docs", limit=100)
with svc.list_documents_stream("docs") as it:
    for d in it:
        pass  # process VectorDocument

svc.close()
```

## Caveats
- `add_documents`:
  - `ids` and `vectors` must be non-empty and same length.
  - If provided, `metadata` and `payloads` lengths must match `ids`.
- `search_similar`: `k` must be `> 0`; `score_threshold` filtering is applied after adapter search.
- `list_documents`: `limit` must be `1..10_000`.
- `update_document`: at least one of `vector`, `metadata`, or `payload` must be provided.
- Semantics of search, filters, scoring, distance metric, and paging stability are defined by the adapter implementation.
