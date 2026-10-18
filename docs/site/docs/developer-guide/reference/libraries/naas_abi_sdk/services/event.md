# EventService

## What it is
- Portable event utilities for the NAAS ABI SDK.
- Provides:
  - A lightweight `Event` dataclass for publishing portable JSON payloads.
  - An `EventService` client to append/query events durably via RPC and optionally receive live broadcasts via a bus.

## Public API

### `Event` (dataclass)
Portable event payload container.
- Fields:
  - `event_type: str` — event class URI/type identifier.
  - `payload: dict[str, Any]` — JSON-serializable payload.
  - `id: str` — defaults to a UUID4 string.
  - `timestamp: str` — defaults to current UTC ISO-8601 timestamp.

### `EventService` (class)
Service proxy for event persistence and retrieval.

- `publish(event: Event) -> StoredEvent`
  - Appends an event durably (`append`) and then attempts a live bus broadcast.
  - Raises `TypeError` if `event` is not an `Event`.

- `query(..., event_class=None, ...) -> list[Any]`
  - Queries stored events (`query`) with optional bounds and filters.
  - `event_class` behavior:
    - If it’s a type: returns `[event_class.model_validate(item), ...]` using JSON-decoded payloads.
    - Otherwise: returns raw decoded JSON dicts.
  - Parameters:
    - `since_seq`, `until_seq`: integer sequence bounds.
    - `since_timestamp`, `until_timestamp`: timestamp bounds (string).
    - `filter`: dict passed as `json_filter`.
    - `limit`: max results.
    - `newest_first`: reverse order flag.
    - `search`: search string.

- `query_stream(..., event_class=None, ...) -> AsyncIterator[AsyncIterator[Any]]` (async context manager)
  - Streamed variant of `query` that restores results as frames arrive.
  - Pins the maximum sequence at entry (`max_seq`): events appended while reading are not included.
  - Raises `RPCError("UNAVAILABLE", "...")` if no engine provides streaming.

- `query_for_consumer(consumer_id: str, event_class, limit: int | None = None, filter: dict | None = None) -> list[Any]`
  - Queries events for a consumer cursor (`query_for_consumer`), restoring like `query`.

- `seek_consumer_to_end(consumer_id: str, event_class) -> dict[str, Any]`
  - Sets a consumer cursor to the current end (`max_seq` + `set_cursor`).
  - Returns `{"consumer_id": ..., "event_type": ..., "last_seq": ...}`.

- `subscribe(event_class, callback=None, filter=None)`
  - Subscribes to live broadcasts for an event type on the bus.
  - Only the async subscription is supported; `callback`/`filter` are rejected.
  - Raises `NotImplementedError` if `callback` or `filter` is provided.

## Configuration/Dependencies
- Requires:
  - An RPC client compatible with `ServiceProxy` (used via `self._request(...)`).
  - A bus object providing:
    - `publish(subject, key, payload)` for live broadcasts.
    - `subscribe(subject, wildcard)` for subscriptions.
- Streaming:
  - Uses `open_stream(self._client, TRANSFER_PREFIX, "query", ...)`.
  - Stream frames are protobuf `StoredEvents` messages (`naas_abi_proto.event.v1.event_pb2`).

## Usage

```python
import asyncio
from naas_abi_sdk.services.event import Event, EventService

async def main(client, bus):
    svc = EventService(client, bus)

    # Publish
    stored = await svc.publish(Event(event_type="com.example.MyEvent", payload={"x": 1}))
    print(stored)

    # Query (raw dicts)
    events = await svc.query(event_class="com.example.MyEvent", limit=10)
    print(events)

    # Stream query
    async with svc.query_stream(event_class="com.example.MyEvent") as it:
        async for evt in it:
            print(evt)

# asyncio.run(main(client, bus))
```

## Caveats
- `publish` requires an `Event` instance (not a plain dict).
- Live bus broadcast failures do **not** fail the publish; they are logged after the durable append.
- `subscribe` does not support `callback`/`filter` adapters; consume the returned async subscription directly.
- `query_stream` may raise `RPCError("UNAVAILABLE", ...)` if the engine does not provide streamed results.
