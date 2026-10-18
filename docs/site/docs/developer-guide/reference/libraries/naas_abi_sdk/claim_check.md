# claim_check

## What it is
Claim-check support for NATS JetStream messages that exceed the broker/client `max_payload`. Oversized payloads are stored in a JetStream Object Store and the published message body is replaced with an empty body plus reference headers. Receivers can “resolve” the reference back to the original payload.

## Public API
- **Constants**
  - `BUCKET = "abi_claim_checks"`: JetStream Object Store bucket name.
  - `HEADER = "Abi-Claim-Check"`: Header key storing the object name/reference.
  - `SIZE_HEADER = "Abi-Claim-Check-Size"`: Header key storing original payload size (string).
  - `MAX_VALUE_BYTES = 256 * 1024 * 1024`: Hard limit for storing a payload via claim-check.
  - `TTL_SECONDS = 7 * 24 * 3600`: Object Store TTL; stored payloads expire after this time.

- **Exceptions**
  - `ClaimCheckTooLarge(ValueError)`: Raised when `len(payload) > MAX_VALUE_BYTES`.

- **Functions**
  - `stream_header_reserve(stream: str) -> int`  
    Returns estimated bytes added by JetStream publish for `Nats-Expected-Stream` for the given stream name.
  - `ensure_bucket(nc) -> Any`  
    Ensures the claim-check Object Store exists (creates if missing) and returns it.
  - `prepare(nc, payload: bytes, headers: dict[str, str] | None = None, *, reserve: int = 0) -> tuple[bytes, dict[str, str] | None]`  
    - If the message (payload + headers) fits within `nc.max_payload` (plus `reserve`), returns `(payload, headers)` unchanged.
    - Otherwise stores `payload` in the Object Store and returns `(b"", headers_with_reference)` where headers include `HEADER` and `SIZE_HEADER`.
  - `carries_reference(msg) -> bool`  
    Returns `True` if `msg.headers` contains the claim-check `HEADER`.
  - `resolve(nc, msg) -> bytes`  
    Returns the actual payload: `msg.data` if not a claim-check message, otherwise fetches from the Object Store using the reference header.
  - `resolve_in_place(nc, msg) -> Any`  
    Resolves and assigns `msg.data` to the actual payload, then returns `msg`.

## Configuration/Dependencies
- Requires a NATS client connection `nc` that provides:
  - `nc.max_payload` (int)
  - `nc.jetstream()` returning a JetStream context with:
    - `object_store(name)` and `create_object_store(name, config=...)`
- Uses JetStream Object Store with:
  - Bucket: `abi_claim_checks`
  - TTL: `TTL_SECONDS`
  - Chunk size set per stored object to `min(128KiB, nc.max_payload // 2)`
- Depends on:
  - `nats.js.api` for Object Store config/meta
  - `nats.js.errors.NotFoundError`, `BadRequestError`
  - `naas_abi_sdk.messages.message_size` to compute message size
  - `naas_abi_sdk.streams.REFUSED` and `naas_abi_sdk.streams.not_created` for permission/creation error handling

## Usage
```python
import asyncio
from nats.aio.client import Client as NATS

from naas_abi_sdk.claim_check import prepare, resolve, carries_reference

async def main():
    nc = NATS()
    await nc.connect("nats://127.0.0.1:4222")

    payload = b"x" * (nc.max_payload + 1024)  # force claim-check
    body, headers = await prepare(nc, payload, headers={"foo": "bar"})

    # Publish using your preferred JetStream/core publish method; headers must be sent.
    await nc.publish("subject", body, headers=headers)

    msg = await nc.subscribe("subject").next_msg(timeout=1)
    if carries_reference(msg):
        data = await resolve(nc, msg)
    else:
        data = msg.data

    assert data == payload
    await nc.close()

asyncio.run(main())
```

## Caveats
- Stored payloads expire after `TTL_SECONDS`; queued/scheduled messages must be resolved before expiration.
- Payloads larger than `MAX_VALUE_BYTES` raise `ClaimCheckTooLarge` (use an external storage reference instead).
- Object store creation may be refused for restricted users; `ensure_bucket()`/internal creation can raise an error via `not_created(...)`.
- `resolve()` assumes the referenced object exists; missing/expired objects will surface underlying Object Store/NATS errors.
