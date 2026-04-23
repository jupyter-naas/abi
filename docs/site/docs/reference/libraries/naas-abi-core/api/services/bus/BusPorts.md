# BusPorts

## What it is
- Defines a minimal **port/adapter interface** for a message bus with **topic-based publish/consume** operations.
- Intended to be implemented by concrete bus adapters (e.g., RabbitMQ, NATS, etc.) while keeping callers decoupled from the transport.

## Public API
### `class IBusAdapter(ABC)`
Abstract base class for bus adapters.

- `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
  - Publish a `payload` (raw bytes) to a `topic` using a `routing_key`.

- `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread`
  - Start consuming messages from a `topic` with a `routing_key`.
  - For each received message, invoke `callback(payload: bytes)`.
  - Returns a `threading.Thread` (presumably running the consumer loop).

## Configuration/Dependencies
- Standard library only:
  - `abc.ABC`, `abc.abstractmethod`
  - `threading.Thread`
  - `typing.Callable`

## Usage
Minimal example implementing the interface:

```python
from threading import Thread
from naas_abi_core.services.bus.BusPorts import IBusAdapter

class DummyBusAdapter(IBusAdapter):
    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        print(f"publish topic={topic} routing_key={routing_key} payload={payload!r}")

    def topic_consume(self, topic: str, routing_key: str, callback):
        def run():
            callback(b"example message")
        t = Thread(target=run, daemon=True)
        t.start()
        return t

def on_message(payload: bytes) -> None:
    print("received:", payload)

bus = DummyBusAdapter()
bus.topic_publish("events", "user.created", b'{"id": 1}')
t = bus.topic_consume("events", "user.*", on_message)
t.join()
```

## Caveats
- This file specifies **only an interface**; it does not provide any concrete bus behavior.
- Message payloads are **bytes**; serialization/deserialization is the responsibility of the caller/implementation.
- No lifecycle/stop mechanism for the returned consumer thread is defined in the interface.
