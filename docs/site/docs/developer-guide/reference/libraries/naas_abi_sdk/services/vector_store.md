# VectorStoreService

## What it is
An async client-side service proxy for a remote vector store engine. It provides CRUD operations for vector documents, collection management, similarity search, and both paged and streamed listing of documents.

## Public API

### Class: `VectorStoreService(ServiceProxy)`
- `domain = "vector_store"`: service domain used by the underlying proxy.

#### Methods
- `initialize() -> None`
  - Initializes the remote vector store service.

- `ensure_collection(collection_name: str, dimension: int, distance_metric: str = "cosine", recreate: bool = False, **kwargs) -> None`
  - Ensures a collection exists with the requested configuration.
  - If `recreate=True` and the collection exists, deletes and re-creates it.
  - Raises `NotImplementedError` if any backend-specific `kwargs` are provided.

- `add_documents(collection_name: str, ids: list[str], vectors, metadata: list[dict[str, Any]] | None = None, payloads: list[dict[str, Any]] | None = None) -> None`
  - Stores multiple vectors/documents in a collection.
  - Validates that `ids` and `vectors` have matching nonzero lengths and that `metadata`/`payloads` lengths match `ids` when provided.

- `search_similar(collection_name: str, query_vector, k: int = 10, filter: dict[str, Any] | None = None, score_threshold: float | None = None, include_vectors: bool = False, include_metadata: bool = True) -> list[SearchResult]`
  - Performs vector similarity search.
  - Converts `query_vector` values to `float`.
  - Applies `score_threshold` client-side by filtering returned results.

- `get_document(collection_name: str, document_id: str, include_vector: bool = True) -> VectorDocument | None`
  - Fetches a single document by ID.

- `update_document(collection_name: str, document_id: str, vector=None, metadata: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> None`
  - Updates an existing document’s vector, metadata, and/or payload.

- `delete_documents(collection_name: str, document_ids: list[str]) -> None`
  - Deletes documents by ID.

- `list_documents(collection_name: str, *, limit: int = 100, cursor: str | None = None, include_vectors: bool = False) -> VectorPage`
  - Returns a single page of documents plus pagination cursoring.
  - Validate `limit` is within `1..MAX_PAGE_SIZE` (where `MAX_PAGE_SIZE = 10_000`).
  - Follow `VectorPage.next_cursor` until it becomes `None` to read the full collection.

- `list_documents_stream(collection_name: str, *, include_vectors: bool = False) -> AsyncContextManager[AsyncIterator[VectorDocument]]`
  - Streams *all* documents of a collection in the engine’s `list_vectors` order.
  - Must be consumed within the `async with` block; leaving closes the stream.
  - Raises `RPCError("UNAVAILABLE", ...)` if the engine does not support streaming listings.

- `get_collection_info(collection_name: str) -> CollectionInfo`
  - Returns collection dimension, distance metric (may be `None` when unknown), and size.

- `get_collection_size(collection_name: str) -> int`
  - Returns the number of vectors in the collection.

- `list_collections() -> list[str]`
  - Lists available collection names.

- `delete_collection(collection_name: str) -> None`
  - Deletes a collection.

- `close() -> None`
  - Always raises `NotImplementedError` (administrative shutdown is not exposed via this service).

### Internal helper
- `_documents(frames: AsyncIterator[bytes]) -> AsyncIterator[VectorDocument]`
  - Decodes streamed `VectorPage` frames into individual `VectorDocument` items.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.services._codec.ServiceProxy` and `decode`
  - `naas_abi_sdk.services._streams.open_stream` for streamed listings
  - `naas_abi_proto.vector_store.v1.vector_store_pb2` message types
  - Model types from `naas_abi_sdk.services.models`: `CollectionInfo`, `SearchResult`, `VectorDocument`, `VectorPage`
  - `naas_abi_sdk.transport.RPCError`
- Stream transfer settings:
  - `TRANSFER_PREFIX = "abi.svc.vector_store.v1.transfer"`
- Page size limit:
  - `MAX_PAGE_SIZE = 10_000`

## Usage

```python
import asyncio
from naas_abi_sdk.services.vector_store import VectorStoreService

async def main():
    svc = VectorStoreService(...)  # provided by your SDK/client wiring

    await svc.ensure_collection("my_collection", dimension=3, recreate=True)

    await svc.add_documents(
        "my_collection",
        ids=["a", "b"],
        vectors=[[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]],
        metadata=[{"kind": "x"}, {"kind": "y"}],
    )

    results = await svc.search_similar(
        "my_collection",
        query_vector=[0.0, 0.9, 0.1],
        k=5,
        score_threshold=0.0,
    )
    for r in results:
        print(r)

    page = await svc.list_documents("my_collection", limit=100)
    print(page)

    async with svc.list_documents_stream("my_collection") as docs:
        async for doc in docs:
            print(doc)

asyncio.run(main())
```

## Caveats
- `ensure_collection(..., **kwargs)` rejects backend-specific options (`NotImplementedError`) because there is no remote contract for them.
- `add_documents` enforces strict length checks for `ids`, `vectors`, and optional `metadata`/`payloads`.
- `list_documents` enforces `1 <= limit <= 10_000` (`ValueError` otherwise).
- `list_documents_stream` requires engine support for streaming; otherwise raises `RPCError("UNAVAILABLE", ...)`.
- `close()` is not supported by this service and always raises `NotImplementedError`.
