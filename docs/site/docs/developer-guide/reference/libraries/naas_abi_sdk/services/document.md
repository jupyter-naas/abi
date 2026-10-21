# DocumentService

## What it is
An async service proxy for managing document collections and documents via the `document` domain RPC API. It provides CRUD operations, querying with pagination/cursors, and helpers for iteration and bulk actions.

## Public API

### Types
- `Predicate = tuple[str, str, Any]`
  - A single query predicate: `(field, operator, value)`.
- `OrderBy = tuple[str, str] | None`
  - Ordering specification: `(field, direction)` or `None`.

### Class: `DocumentService(ServiceProxy)`
- `domain = "document"`

#### Properties
- `namespace: str`
  - Returns the underlying client namespace (`self._client.namespace`).
- `rpc`
  - Low-level escape hatch to the underlying RPC client (retains this module’s namespace expectations).

#### Methods
- `ensure_collection(spec: CollectionSpec) -> None`
  - Create/ensure a collection exists using a `CollectionSpec` (fields and uniqueness groups).
- `drop_collection(collection: str) -> None`
  - Drop a collection by name.
- `collections() -> list[str]`
  - List available collection names.
- `put(collection: str, id: str, data: dict[str, Any], *, if_version: int | None = None) -> Document`
  - Upsert a document by id; optionally enforce optimistic concurrency with `if_version`.
- `get(collection: str, id: str) -> Document`
  - Fetch a document by id.
- `exists(collection: str, id: str) -> bool`
  - Returns `False` if `get()` raises `DocumentNotFound`, otherwise `True`.
- `delete(collection: str, id: str, *, if_version: int | None = None) -> None`
  - Delete a document by id; optionally enforce `if_version`.
- `find(collection: str, *, where: Iterable[Predicate] = (), order_by: OrderBy = None, limit: int = 100, cursor: str | None = None, max_bytes: int | None = None) -> Page`
  - Query documents with predicates, ordering, and cursor-based pagination.
  - Validations:
    - `limit` must be an `int` in `[1, 1000]`.
    - `max_bytes` must be a positive `int` or `None`.
- `iterate(collection: str, *, where: Iterable[Predicate] = (), order_by: OrderBy = None, batch: int = 500, max_bytes: int | None = None) -> AsyncIterator[Document]`
  - Async generator that repeatedly calls `find()` following cursors until exhausted.
- `find_one(collection: str, where: Iterable[Predicate]) -> Document | None`
  - Returns the first matching document or `None` (internally uses `find(limit=1)`).
- `count(collection: str, where: Iterable[Predicate] = ()) -> int`
  - Count documents matching predicates.
- `put_many(collection: str, items: Mapping[str, dict[str, Any]]) -> list[Document]`
  - Convenience loop over `put()` for multiple `(id -> data)` pairs.
- `delete_many(collection: str, where: Iterable[Predicate]) -> int`
  - Iterates matching documents and deletes each using `if_version=doc.version`; returns number deleted.

## Configuration/Dependencies
- Depends on:
  - Protobuf messages from `naas_abi_proto.document.v1.document_pb2`.
  - Encoding/decoding helpers: `encode_data`, `decode_data`, `encode_value`.
  - Models: `CollectionSpec`, `Document`, `Page`.
  - Error mapping via `domain_error`; `DocumentNotFound` for existence checks.
  - Transport exception: `RPCError` (converted to domain errors by `_call()`).
- Requires an underlying async RPC client attached as `self._client` (provided by `ServiceProxy`).

## Usage
Minimal async usage (assuming you already have a configured `DocumentService` instance):

```python
import asyncio

async def main(documents):  # documents: DocumentService
    await documents.put("users", "u1", {"name": "Ada"})
    doc = await documents.get("users", "u1")
    print(doc.id, doc.data)

    page = await documents.find(
        "users",
        where=[("name", "==", "Ada")],
        order_by=("name", "asc"),
        limit=10,
    )
    for d in page.items:
        print(d.id)

    async for d in documents.iterate("users", batch=100):
        print("iter", d.id)

# asyncio.run(main(documents))
```

## Caveats
- `find()` pagination:
  - A “short page” is **not** guaranteed to be the end; follow `Page.cursor` until it becomes `None`.
- `limit` is restricted to `1..1000`; invalid values raise `ValueError`.
- `max_bytes` must be a positive integer when provided; otherwise `ValueError`.
- `delete_many()` performs per-document deletes and enforces version via `if_version=doc.version` (may fail if versions changed concurrently).
