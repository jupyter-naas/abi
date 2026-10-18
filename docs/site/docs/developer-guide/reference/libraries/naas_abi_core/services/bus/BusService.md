# BusService

## What it is
- `BusService` is a service wrapper around an `IBusAdapter` transport.
- Provides pub/sub (`publish`/`subscribe`) and work-queue (`enqueue`/`dequeue`) operations.
- Optionally emits telemetry events (`BusMessagePublished`, `BusMessageEnqueued`) for each message (off by default); always emits `BusError` on failures when an event service is available.
- Includes a recursion guard for `"evt.*"` topics to avoid infinite loops when the event system itself uses the bus.

## Public API
- **Class `BusService(adapter: IBusAdapter, emit_message_events: bool = False)`**
  - Wraps a bus adapter.
  - `emit_message_events` controls per-message event-log telemetry (default `False`).

- **Property `emit_message_events -> bool`**
  - Returns whether message telemetry is enabled.

- **Property `adapter -> IBusAdapter`**
  - Exposes the owned transport adapter (for composition/shutdown outside this module).

- **`publish(topic: str, routing_key: str, payload: bytes) -> None`**
  - Pub/sub publish.
  - On adapter exception: emits `BusError(operation="publish")` (if events service is wired/available) and re-raises.
  - If telemetry enabled: emits `BusMessagePublished`.
  - If `topic` starts with `"evt."`: bypasses telemetry to avoid recursion and delegates directly to the adapter.

- **`publish_many(topic: str, messages: Sequence[tuple[str, bytes]]) -> None`**
  - Batch pub/sub publish for `(routing_key, payload)` pairs.
  - No-op if `messages` is empty.
  - On adapter exception: emits `BusError(operation="publish_many")` using the first message routing key, then re-raises.
  - If telemetry enabled: emits `BusMessagePublished` per message.
  - If `topic` starts with `"evt."`: bypasses telemetry and delegates directly to the adapter.

- **`subscribe(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread`**
  - Pub/sub consume; delegates to `IBusAdapter.subscribe(...)`.
  - Returns the `Thread` created/managed by the adapter.

- **`enqueue(topic: str, routing_key: str, payload: bytes) -> None`**
  - Work-queue publish (durable queue semantics are adapter-defined).
  - On adapter exception: emits `BusError(operation="enqueue")` and re-raises.
  - If telemetry enabled: emits `BusMessageEnqueued`.
  - If `topic` starts with `"evt."`: bypasses telemetry and delegates directly to the adapter.

- **`dequeue(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread`**
  - Work-queue consume; delegates to `IBusAdapter.dequeue(...)`.
  - Returns the `Thread` created/managed by the adapter.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter` (required; provides `publish`, `publish_many`, `subscribe`, `enqueue`, `dequeue`).
  - `naas_abi_core.services.ServiceBase.ServiceBase` (used for wiring/accessing `self.services` and `services_wired`).
  - Event ontology types:
    - `BusError`, `BusMessagePublished`, `BusMessageEnqueued`
  - `naas_abi_core.logger` (warnings when event publishing fails)
- Telemetry/event emission requires:
  - `services_wired` is true, and
  - `self.services.events_available()` returns true, and
  - `self.services.events.publish(event)` succeeds (failures are swallowed with a warning).

## Usage
```python
from threading import Thread
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.BusPorts import IBusAdapter

class DummyAdapter(IBusAdapter):
    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        print("publish:", topic, routing_key, payload)

    def publish_many(self, topic: str, messages):
        for rk, payload in messages:
            self.publish(topic, rk, payload)

    def subscribe(self, topic: str, routing_key: str, callback):
        t = Thread(target=lambda: callback(b"hello"), daemon=True)
        t.start()
        return t

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        print("enqueue:", topic, routing_key, payload)

    def dequeue(self, topic: str, routing_key: str, callback):
        t = Thread(target=lambda: callback(b"job"), daemon=True)
        t.start()
        return t

bus = BusService(adapter=DummyAdapter(), emit_message_events=False)

bus.publish("events", "user.created", b'{"id": 1}')
bus.publish_many("events", [("user.updated", b"u1"), ("user.deleted", b"d1")])

sub_t = bus.subscribe("events", "user.*", lambda b: print("received:", b))
job_t = bus.dequeue("jobs", "reindex", lambda b: print("job:", b))
sub_t.join()
job_t.join()
```

## Caveats
- `"evt.*"` topics bypass telemetry emission to prevent recursion with the event service.
- `emit_message_events=True` can generate very high event-log volume (one durable event per bus message).
- Thread lifecycle, shutdown, delivery guarantees, and batching behavior are adapter-defined.
- Payloads are raw `bytes`; serialization/deserialization is caller responsibility.
