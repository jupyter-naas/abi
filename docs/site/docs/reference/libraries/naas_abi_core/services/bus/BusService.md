# BusService

## What it is
- `BusService` is a thin service wrapper around an `IBusAdapter`.
- It exposes topic-based publish/consume operations and delegates all work to the injected adapter.

## Public API
- **Class `BusService(adapter: IBusAdapter)`**
  - Initializes the service with a bus adapter implementation.

- **`topic_publish(topic: str, routing_key: str, payload: bytes) -> None`**
  - Publishes `payload` to a `topic` using the given `routing_key`.
  - Delegates to `IBusAdapter.topic_publish(...)`.

- **`topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread`**
  - Starts consuming messages for `topic`/`routing_key`.
  - Invokes `callback(payload_bytes)` for each received message.
  - Returns a `threading.Thread` created/managed by the adapter via `IBusAdapter.topic_consume(...)`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter` (must be provided).
  - `naas_abi_core.services.ServiceBase.ServiceBase` (base class).
- No configuration is defined in this module; behavior is determined by the provided adapter.

## Usage
```python
from threading import Thread
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.BusPorts import IBusAdapter

class DummyAdapter(IBusAdapter):
    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        print("publish", topic, routing_key, payload)

    def topic_consume(self, topic: str, routing_key: str, callback):
        def run():
            callback(b"example-message")
        t = Thread(target=run, daemon=True)
        t.start()
        return t

bus = BusService(adapter=DummyAdapter())

bus.topic_publish("events", "user.created", b'{"id": 1}')

t = bus.topic_consume("events", "user.*", lambda b: print("received", b))
t.join()
```

## Caveats
- `topic_consume(...)` returns a `Thread` produced by the adapter; thread lifecycle (daemon/non-daemon, stopping, error handling) is adapter-defined.
- `payload` is `bytes`; any serialization/deserialization is the caller’s responsibility.
