# BusService

## What it is
- A thin service wrapper around an `IBusAdapter` that exposes topic-based publish/consume operations.
- Delegates all work to the provided adapter implementation.

## Public API
- **Class `BusService(adapter: IBusAdapter)`**
  - `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
    - Publish a `payload` to a `topic` using a `routing_key`.
  - `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
    - Start consuming messages for a `topic` and `routing_key`, invoking `callback(payload)` for each message.
    - Returns the `Thread` used by the adapter to run consumption.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter` (must provide `topic_publish` and `topic_consume`)
  - `naas_abi_core.services.ServiceBase.ServiceBase` (base class)
- Standard library:
  - `threading.Thread`
  - `typing.Callable`

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
            callback(b"hello")
        t = Thread(target=run, daemon=True)
        t.start()
        return t

bus = BusService(DummyAdapter())
bus.topic_publish("events", "user.created", b'{"id": 1}')

def on_message(payload: bytes) -> None:
    print("received", payload)

t = bus.topic_consume("events", "user.*", on_message)
t.join()
```

## Caveats
- No validation or error handling is implemented in `BusService`; behavior and threading model are determined by the adapter.
- `topic_consume` returns a `Thread`; lifecycle management (e.g., stopping the consumer) is adapter-specific and not defined here.
