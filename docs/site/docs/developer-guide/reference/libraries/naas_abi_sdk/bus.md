# BusClient (NATS/JetStream bus)

## What it is
- A NATS/JetStream-backed message bus client.
- Wire-compatible with the engine’s `NATSJetStreamAdapter`.
- Transparently supports “claim check” payloads:
  - If a message exceeds broker limits, the payload is stored elsewhere and a claim check is sent.
  - Subscribers/dequeuers see the full payload because it is resolved before the message is yielded/returned.
- Queue (JetStream) delivery is **at-least-once**: dequeued messages must be explicitly `ack()`ed or `nak()`ed.

## Public API

### `class BusClient`
Constructed with a `Transport` and provides pub/sub and enqueue/dequeue operations.

- `BusClient(transport: Transport)`
  - Holds transport settings (connection + timeout).

- `stream_name(topic: str) -> str` *(static)*
  - Derives a deterministic JetStream stream name from a topic (SHA-256 based).

- `consumer_name(topic: str, routing_key: str) -> str` *(static)*
  - Derives a deterministic durable consumer name from `(topic, routing_key)` (SHA-256 based).

- `subject(topic: str, routing_key: str) -> str` *(static)*
  - Maps `(topic, routing_key)` to a NATS subject.
  - Validates:
    - `topic` and `routing_key` must be non-empty.
    - Only **trailing** `#` wildcards are allowed (mapped to NATS `>`).
  - Examples:
    - `routing_key="a.b"` → `topic.a.b`
    - `routing_key="a.#"` → `topic.a.>`

- `publish(topic: str, routing_key: str, payload: bytes) -> None` *(async)*
  - Publishes a message on core NATS.
  - Applies claim-check preparation before sending.
  - Uses `Transport.timeout` via `asyncio.wait_for`.

- `publish_many(topic: str, messages: Sequence[tuple[str, bytes]]) -> None` *(async)*
  - Publishes multiple messages in order.
  - Partial failures are **not** retried or rolled back.

- `subscribe(topic: str, routing_key: str) -> ClaimCheckedSubscription` *(async)*
  - Creates a core NATS subscription.
  - Returned subscription resolves claim-check payloads before returning messages.

- `enqueue(topic: str, routing_key: str, payload: bytes) -> None` *(async)*
  - Publishes into a JetStream stream for the topic (creating/ensuring it exists).
  - Applies claim-check preparation, reserving space for stream-specific headers.

- `dequeue(topic: str, routing_key: str) -> ClaimCheckedPullSubscription` *(async)*
  - Returns a **durable** JetStream pull subscription.
  - Use `fetch()`, then `msg.ack()`/`msg.nak()` on each message.

### `class ClaimCheckedSubscription`
Wrapper around a `nats-py` `Subscription` that resolves claim-check payloads.

- `next_msg(timeout: float = 1.0) -> Any` *(async)*
  - Awaits the next message and resolves payload in-place.

- `messages` *(async property / async generator)*
  - Iterates subscription messages, resolving payloads in-place.

- `__getattr__(name: str) -> Any`
  - Delegates other attributes/methods to the underlying subscription.

### `class ClaimCheckedPullSubscription`
Wrapper around a JetStream pull subscription that resolves claim-check payloads.

- `fetch(batch: int = 1, timeout: float | None = 5, **kwargs) -> Any` *(async)*
  - Fetches a batch of messages and resolves payloads in-place, then returns the messages.

- `__getattr__(name: str) -> Any`
  - Delegates other attributes/methods to the underlying pull subscription.

## Configuration/Dependencies
- Depends on:
  - `nats-py` (core NATS + JetStream): `nats.aio.subscription.Subscription`, JetStream APIs, and errors (`BadRequestError`, `NotFoundError`).
  - `naas_abi_sdk.transport.Transport` for connection management and timeout.
  - `naas_abi_sdk.claim_check` for payload preparation and resolution.
  - `naas_abi_sdk.streams` for:
    - `REFUSED` (raised when stream creation is refused by broker policy/user permissions)
    - `not_created(...)` helper to raise a stream-not-created error.
- Timeouts:
  - `publish()` and `subscribe()` are wrapped in `asyncio.wait_for(..., transport.timeout)`.
  - Stream creation/lookup uses `nc.jetstream(timeout=max(0.1, transport.timeout/2))`.

## Usage

### Publish/Subscribe (core NATS)
```python
import asyncio
from naas_abi_sdk.bus import BusClient
from naas_abi_sdk.transport import Transport

async def main():
    bus = BusClient(Transport(...))  # provide your Transport configuration

    sub = await bus.subscribe("orders", "created.#")
    await bus.publish("orders", "created.eu", b"hello")

    msg = await sub.next_msg(timeout=1.0)
    try:
        print(msg.data)  # claim-check resolved before you see it
    finally:
        # core NATS messages are not JetStream-acked here
        pass

asyncio.run(main())
```

### Enqueue/Dequeue (JetStream pull consumer)
```python
import asyncio
from naas_abi_sdk.bus import BusClient
from naas_abi_sdk.transport import Transport

async def main():
    bus = BusClient(Transport(...))

    await bus.enqueue("tasks", "image.resize", b"do work")

    pull = await bus.dequeue("tasks", "image.*")
    msgs = await pull.fetch(batch=1, timeout=5)
    for msg in msgs:
        try:
            print(msg.data)  # claim-check resolved in-place
            await msg.ack()
        except Exception:
            await msg.nak()

asyncio.run(main())
```

## Caveats
- `subject(topic, routing_key)` rejects:
  - empty `topic` or `routing_key`
  - non-trailing `#` wildcards (only trailing `#` is supported; mapped to `>`).
- JetStream stream compatibility:
  - The stream (derived from `topic`) must have subjects exactly `[f"{topic}.>"]`; otherwise `ValueError("Existing stream has incompatible subjects")`.
- Queue processing is **at-least-once**:
  - You must `ack()` after successful processing or `nak()` on failure to control redelivery.
