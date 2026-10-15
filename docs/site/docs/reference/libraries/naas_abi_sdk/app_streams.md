# app_streams

## What it is
Streaming of HTTP request/response bodies over NATS between Nexus and an app module (`abi.app.v1`). The body is transferred as a pull-based stream: the reader sends `BodyPull` messages and the holder replies with one `BodyChunk` per pull, providing end-to-end backpressure and keeping memory bounded to roughly one chunk per side.

## Public API

### Constants
- `INLINE_BYTES`: Maximum body size sent inline in an `HttpRequest/HttpResponse` (256 KiB).
- `CHUNK_BYTES`: Default maximum chunk size (256 KiB).
- `KEEPALIVE_SECONDS`: Holder returns an empty chunk if nothing new is available within this time (15 s).
- `PULL_TIMEOUT_SECONDS`: Default request timeout for a pull (30 s).
- `PULL_RETRIES`: Number of retries when a pull times out (3).
- `IDLE_SECONDS`: Holder considers the reader gone after this long without pulls (60 s).
- `LINGER_SECONDS`: After the last chunk, holder keeps answering repeated last pull for this long (35 s).

### Functions
- `chunk_bytes(max_payload: int) -> int`  
  Compute a chunk size that fits within the NATS broker max payload, leaving room for an envelope.

- `rechunk(pieces: AsyncIterable[bytes], size: int) -> AsyncIterator[bytes]`  
  Regroup an async stream of byte pieces into chunks of at most `size`.

- `pull_body(nc, inbox: str, *, max_bytes: int | None = None, timeout: float = PULL_TIMEOUT_SECONDS) -> AsyncIterator[bytes]`  
  Pull and iterate body chunks from a holder at `inbox`. Cancels the body automatically if iteration ends early.
  - Raises:
    - `naas_abi_sdk.transport.RPCError` on holder-reported errors, deadline exceeded, unavailable, or sequencing issues.
    - `BodyTooLarge` if `max_bytes` is exceeded.

- `cancel_body(nc, inbox: str) -> None`  
  Notify the holder that the reader left. Runs the publish in a separate shielded task so cancellation of the reader doesn’t prevent sending the cancel.

### Classes / Exceptions
- `class BodySource`  
  Holds a body and serves it over a private NATS inbox by answering `BodyPull` requests with `BodyChunk` replies.
  - Key attributes:
    - `inbox`: Subject to which pulls are sent (generated via `nc.new_inbox()`).
    - `gone`: `asyncio.Event` set when reader cancels or becomes idle.
    - `done`: `asyncio.Event` set when the end-of-body has been pulled.
    - `pulled`: True once a chunk has been delivered (body “committed”).
  - Public methods:
    - `start()`: Subscribe to inbox and begin serving pulls.
    - `put(data: bytes)`: Queue a chunk; waits until prior queued chunk is pulled (backpressure). Raises `ReaderGone` if reader left.
    - `finish()`: End stream successfully.
    - `fail(code: str, message: str)`: End stream with an RPC-style error.
    - `abort(code: str, message: str)`: End stream with an error immediately, dropping any not-yet-pulled queued chunk (unless `_END` was already queued).
    - `settled()`: Wait until reader has pulled the end, or reader left.
    - `close()`: Stop serving; unsubscribes and cancels internal tasks.
- `class BodyTooLarge(Exception)`  
  Raised by `pull_body` when accumulated bytes exceed `max_bytes`.
- `class ReaderGone(Exception)`  
  Raised by `BodySource.put()` when the reader cancels or stops pulling.

## Configuration/Dependencies
- Requires a NATS client (`nc`) providing (as used in code):
  - `new_inbox()`, `subscribe(subject, cb=...)`, `publish(subject, payload)`, `flush(...)`, `request(subject, payload, timeout=...)`.
- Uses protobuf messages from `naas_abi_proto.app.v1.app_pb2`:
  - `BodyPull`, `BodyChunk`.
- Error types:
  - `naas_abi_sdk.transport.RPCError`
  - `nats.errors.NoRespondersError`
  - `nats.errors.TimeoutError` (aliased as `NATSTimeoutError`)

## Usage

### Holder side (serve a body)
```python
import asyncio
from naas_abi_sdk.app_streams import BodySource, ReaderGone

async def serve_body(nc):
    src = BodySource(nc)
    await src.start()
    try:
        await src.put(b"hello ")
        await src.put(b"world")
        await src.finish()
        await src.settled()  # optional: wait until reader consumes end or leaves
    except ReaderGone:
        # Reader canceled or stopped pulling
        pass
    finally:
        await src.close()
    return src.inbox  # share this with the reader via your control channel
```

### Reader side (pull a body)
```python
from naas_abi_sdk.app_streams import pull_body

async def read_body(nc, inbox: str) -> bytes:
    out = bytearray()
    async for chunk in pull_body(nc, inbox, max_bytes=10_000_000):
        out += chunk
    return bytes(out)
```

## Caveats
- `BodySource.start()` must be called before the reader starts pulling; the inbox subject must be communicated out-of-band.
- `BodySource.put()` applies backpressure (queue size 1) and can raise `ReaderGone` if the reader stops pulling or cancels.
- `pull_body()` must be fully consumed or will send a cancel in `finally`; if you stop iterating early, the holder is notified.
- Chunk ordering is strictly enforced by sequence; out-of-sequence pulls/chunks result in `RPCError("INVALID_ARGUMENT", ...)`.
