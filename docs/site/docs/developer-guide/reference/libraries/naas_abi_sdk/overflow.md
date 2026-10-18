# overflow

## What it is
Utilities for handling protobuf RPC payloads that exceed the broker’s message size limit by moving the data through `transfer/v1` frames (“RPC overflow”). Used by protobuf RPC clients to:
- **Upload** oversized requests before making an RPC call.
- **Download** oversized replies that are “parked” by the service.

## Public API
- `class OverflowRefused(RuntimeError)`
  - Raised when a value cannot be overflowed (e.g., too large or mismatched announced size).
  - Attributes:
    - `code: str` (e.g., `"PAYLOAD_TOO_LARGE"`, `"INTERNAL"`)

- `def chunk_size(max_payload: int) -> int`
  - Computes transfer chunk size given a broker limit:
    - At most **1 MiB**
    - At most **half** of `max_payload`

- `def possible(max_payload: int) -> bool`
  - Returns whether overflow transfer is feasible for a given broker limit (chunk size must be ≥ 1024 bytes).

- `async def upload(call: Call, payload: bytes, *, chunk_bytes: int) -> str`
  - Uploads a serialized request payload via transfer frames.
  - Returns a `transfer_id` to be sent with the subsequent RPC call.
  - Notes:
    - Enforces a hard limit of `MAX_VALUE_BYTES` (256 MiB).
    - Leaves the transfer session open for the service to read; the caller should close it after the RPC call (or rely on later cleanup).

- `async def download(call: Call, transfer_id: str, size: int) -> bytes`
  - Downloads a parked reply of exactly `size` bytes using `transfer_id`, then releases it.
  - Validates the downloaded size matches the announced `size`; otherwise raises `OverflowRefused`.

- `async def close(call: Call, transfer_id: str) -> None`
  - Attempts to release a transfer session.
  - Errors are logged as warnings and suppressed (cleanup should not override the main RPC outcome).

### Constants (used by callers)
- `PREFIX = "abi.rpc.overflow"`
- Header names:
  - `ACCEPT_HEADER = "Abi-Overflow"`
  - `REPLY_HEADER = "Abi-Overflow-Reply"`
  - `SIZE_HEADER = "Abi-Overflow-Size"`
  - `REQUEST_HEADER = "Abi-Overflow-Request"`
- Limits:
  - `MAX_VALUE_BYTES = 256 * 1024 * 1024`
  - `CHUNK_BYTES = 1024 * 1024`
  - `MIN_CHUNK_BYTES = 1024`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_proto.transfer.v1.transfer_pb2` (`OpenRequest/Response`, `CloseRequest/Response`)
  - `naas_abi_sdk.transfer.Transfer` and `naas_abi_sdk.transfer.transfer_subject`
- Requires a `call` callable with signature:
  - `call(subject: str, request: Any, response_type: Any) -> Awaitable[Any]`

## Usage
Minimal example showing request upload and cleanup (the actual RPC call and headers are transport-specific):

```python
from naas_abi_sdk.overflow import upload, close, chunk_size

async def do_rpc_with_overflow(call, max_payload: int, payload: bytes):
    transfer_id = await upload(call, payload, chunk_bytes=chunk_size(max_payload))
    try:
        # Make your actual RPC call here with an empty body and include
        # the REQUEST_HEADER pointing to `transfer_id` (handled by your transport).
        # response = await call("some.rpc.subject", request_obj, ResponseType)
        pass
    finally:
        await close(call, transfer_id)
```

Downloading an overflowed reply once you have the transfer id and expected size:

```python
from naas_abi_sdk.overflow import download

async def read_overflow_reply(call, transfer_id: str, size: int) -> bytes:
    return await download(call, transfer_id, size)
```

## Caveats
- Maximum overflow value size is **256 MiB** (`MAX_VALUE_BYTES`); larger values raise `OverflowRefused("PAYLOAD_TOO_LARGE", ...)`.
- `download()` enforces exact size matching; if the received bytes differ from the announced `size`, it raises `OverflowRefused("INTERNAL", ...)`.
- `close()` suppresses exceptions; if cleanup fails, sessions rely on idle expiry.
