# transfer

## What it is
Caller-owned, chunked transfer utilities for ABI services. Provides an async `Transfer` abstraction plus context managers to open/close a transfer over a transport, with explicit sequencing and no automatic retries or replay.

## Public API

- `transfer_subject(prefix: str, operation: str, transfer_id: str = "") -> str`
  - Build the subject/topic used for transfer RPC calls.
  - If `transfer_id` contains an owner prefix (`"{owner}:{rest}"`), validates owner as 32 lowercase hex characters and includes it in the subject.

- `read_legacy_upload(stream: BinaryIO, limit: int) -> bytes`
  - Reads an entire binary stream into memory up to `limit` bytes.
  - Raises `ValueError` if the stream exceeds `limit`.
  - Uses bounded reads to handle streams that return short reads.

- `class Transfer`
  - Chunked read/write transfer state machine (sequence tracked client-side).
  - Methods:
    - `await write(data: bytes) -> None`
      - Sends `data` in chunks of `chunk_bytes` using sequential `WriteRequest`s.
    - `await start() -> None`
      - Signals the server to start processing via `StartRequest`.
    - `async fragments()`
      - Async generator yielding `(data: bytes, frame_end: bool)` from `ReadResponse`.
      - Enforces sequence matching; polls when `pending` is set.
    - `async frames()`
      - Async generator yielding complete `bytes` frames assembled from fragments.
      - Raises `ValueError` if the transfer ends mid-frame.

- `open_transfer(transport, prefix: str, operation: str, metadata: bytes = b"")`
  - Async context manager yielding a `Transfer`.
  - Wraps the whole transfer in a telemetry span (`transfer_span`) and passes it to transport calls.

- `_open_transfer(transport, call, prefix: str, operation: str, metadata: bytes = b"")`
  - Internal async context manager that:
    - Connects (`await transport.connect()`),
    - Opens the transfer (`{prefix}.open`),
    - Yields a `Transfer`,
    - Closes the transfer in `finally` (best-effort; logs warnings on failure).

- `async model_frames(client, operation, request)`
  - Convenience async generator for model-registry transfers:
    - Opens transfer with prefix `"abi.svc.model_registry.v1.transfer"`,
    - Writes the serialized request,
    - Starts transfer,
    - Yields response frames as `bytes`.

- `class AsyncObjectReader`
  - Async reader/iterator wrapper over `Transfer.fragments()` providing stream-like reads.
  - Methods:
    - `await prime() -> None` (reads one fragment into an internal buffer if available)
    - `await read(size: int = -1) -> bytes` (reads up to `size`, or all if `-1`)
    - Async iteration yields chunks of up to 64 KiB (`__anext__` uses `read(64 * 1024)`)

## Configuration/Dependencies
- Requires protobuf message types from: `naas_abi_proto.transfer.v1.transfer_pb2`:
  - `OpenRequest/Response`, `WriteRequest/Response`, `StartRequest/Response`, `ReadRequest/Response`, `CloseRequest/Response`.
- Requires telemetry helper: `naas_abi_sdk.telemetry.transfer_span`.
- Expects a `transport` object with:
  - `await transport.connect()` returning an object with `max_payload` attribute,
  - `await transport.call(subject, request, response_type, transfer=...)` (the `transfer=` kwarg is used by `open_transfer`).

## Usage

### Open a transfer, write request bytes, then read frames
```python
import asyncio
from naas_abi_sdk.transfer import open_transfer

async def run(transport):
    prefix = "abi.svc.model_registry.v1.transfer"
    operation = "some.operation"

    async with open_transfer(transport, prefix, operation) as t:
        await t.write(b"request-bytes")
        await t.start()
        async for frame in t.frames():
            print("frame:", frame)

# asyncio.run(run(transport))
```

### Use `AsyncObjectReader` to read fragment data like a stream
```python
from naas_abi_sdk.transfer import AsyncObjectReader

async def consume_fragments(transfer):
    reader = AsyncObjectReader(transfer)
    await reader.prime()
    data = await reader.read(1024)
    print(data)
```

## Caveats
- No retries and no implicit operation replay; callers must handle failures.
- Sequencing is enforced:
  - `Transfer.fragments()` raises `ValueError` on sequence mismatch.
  - `Transfer.frames()` raises `ValueError` if the transfer ends with a partial frame.
- `read_legacy_upload()` buffers the entire stream in memory and raises `ValueError` if it exceeds `limit` (meant for compatibility with unary size limits).
- Closing a transfer is best-effort; close failures are logged and do not override the original error.
