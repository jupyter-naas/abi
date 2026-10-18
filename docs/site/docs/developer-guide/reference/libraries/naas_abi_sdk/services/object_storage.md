# ObjectStorageService

## What it is
An async client-side service proxy for object storage operations (get/put/delete/list), with support for both unary RPC and streamed transfer (with automatic fallback when streaming is not available).

## Public API

### `class ObjectStorageService(ServiceProxy)`
Object storage service wrapper. Uses `domain = "object_storage"`.

- `async get_object(prefix: str, key: str) -> bytes`
  - Download an object and return its full content as `bytes`.
  - Internally uses `get_object_stream()` and reads it fully.

- `async put_object(prefix: str, key: str, content: bytes) -> None`
  - Upload object content from in-memory `bytes`.
  - Uses unary upload when payload is small enough; otherwise uploads via `put_object_stream()`.

- `async delete_object(prefix: str, key: str) -> None`
  - Delete an object.

- `async list_objects(prefix: str = "", queue: Queue | None = None) -> list[str]`
  - List object keys under `prefix`.
  - If `queue` is provided, each key is also pushed via `queue.put_nowait(key)`.

- `async list_objects_recursive(prefix: str = "", queue: Queue | None = None) -> list[str]`
  - Recursively list object keys under `prefix`.
  - If `queue` is provided, each key is also pushed via `queue.put_nowait(key)`.

- `async get_object_metadata(prefix: str, key: str) -> ObjectMetaData`
  - Fetch object metadata.

- `get_object_stream(prefix: str, key: str)` *(async context manager)*
  - Yields an async reader for downloading the object:
    - Preferred path: streamed transfer via `open_transfer(..., "get", ...)` and `AsyncObjectReader`.
    - Fallback path (when there are no responders for transfer): unary `get_object` and a legacy async reader.
  - Errors from transport are mapped via `domain_error()`.

- `async put_object_stream(prefix: str, key: str, stream: BinaryIO | AsyncIterable[bytes]) -> None`
  - Upload from:
    - a binary file object (`BinaryIO`), or
    - an async iterable of chunks (`AsyncIterable[bytes]`).
  - Preferred path: streamed transfer via `open_transfer(..., "put", ...)`.
  - Fallback path (when there are no responders for transfer): reads entire content into memory and uploads via unary `put_object` (bounded by the unary payload limit).

### Internal helpers (not part of the public API)
- `async _read_legacy_chunks(stream: AsyncIterable[bytes], limit: int) -> bytes`
- `class _LegacyReader`

## Configuration/Dependencies
- Requires an initialized `ServiceProxy` client with a transport that can:
  - connect to NATS (`self._client._transport.connect()`), and
  - perform RPC requests (`self._request(...)`), and
  - optionally support streamed transfers (`open_transfer`).
- Uses:
  - `naas_abi_proto.object_storage.v1.object_storage_pb2.GetObjectRequest` for transfer metadata serialization
  - NATS `max_payload` to decide unary vs streamed upload
  - Error mapping via `domain_error` and `RPCError`

## Usage

```python
import asyncio
from io import BytesIO

async def main(svc):
    # Put small content (may use unary)
    await svc.put_object("my-prefix", "hello.txt", b"hello")

    # Get content
    data = await svc.get_object("my-prefix", "hello.txt")
    print(data.decode())

    # Stream upload from file-like object
    await svc.put_object_stream("my-prefix", "big.bin", BytesIO(b"x" * 200_000))

    # Stream download
    async with svc.get_object_stream("my-prefix", "big.bin") as reader:
        chunk = await reader.read(1024)
        print(len(chunk))

    # List
    keys = await svc.list_objects("my-prefix")
    print(keys)

    # Delete
    await svc.delete_object("my-prefix", "hello.txt")

# main() requires an already-constructed ObjectStorageService instance:
# asyncio.run(main(object_storage_service))
```

## Caveats
- When streamed transfers are unavailable (`NoRespondersError`), `put_object_stream()` falls back to unary upload by buffering the entire stream into memory and is limited by `nc.max_payload`. If exceeded for async streams, it raises:
  - `ValueError("Owner upgrade required for streamed uploads above the unary limit")`.
- The service chooses unary vs streamed upload in `put_object()` based on `min(64*1024, nc.max_payload // 2)`; larger payloads use streaming.
