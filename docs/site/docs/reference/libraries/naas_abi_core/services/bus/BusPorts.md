# BusPorts

## What it is
- Defines an abstract interface (`IBusAdapter`) for bus/messaging adapters.
- Establishes a minimal contract for publishing to, and consuming from, a topic-based bus.

## Public API
- **Class `IBusAdapter` (abstract)**
  - **`topic_publish(topic: str, routing_key: str, payload: bytes) -> None`**
    - Publish a `payload` (bytes) to a `topic` with a `routing_key`.
  - **`topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`**
    - Start consuming messages from a `topic` with a `routing_key`.
    - Invokes `callback(message_bytes)` for each message.
    - Returns a `Thread` associated with the consumer.

## Configuration/Dependencies
- Standard library:
  - `abc.ABC`, `abc.abstractmethod`
  - `threading.Thread`
- Typing:
  - `typing.Callable`

## Usage
Implement the interface in your bus adapter:

```python
from threading import Thread
from naas_abi_core.services.bus.BusPorts import IBusAdapter

class DummyBusAdapter(IBusAdapter):
    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        print(f"publish topic={topic} key={routing_key} payload={payload!r}")

    def topic_consume(self, topic: str, routing_key: str, callback):
        def run():
            callback(b"example message")
        t = Thread(target=run, daemon=True)
        t.start()
        return t

bus = DummyBusAdapter()
bus.topic_publish("events", "user.created", b'{"id": 1}')
bus.topic_consume("events", "user.*", lambda b: print("consumed:", b))
```

## Caveats
- This module defines an interface only; actual bus semantics (thread lifecycle, shutdown, routing behavior, delivery guarantees) depend on the concrete implementation.
