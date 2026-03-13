# PythonQueueAdapter

## What it is
- A **process-local message bus adapter** built on Python stdlib `queue.Queue`.
- Supports **topic + routing key** filtering with wildcard matching:
  - `*` matches exactly one dot-separated segment
  - `#` matches zero or more segments

## Public API
- `class PythonQueueAdapter(IBusAdapter)`
  - `__init__() -> None`
    - Initializes internal subscriber registry and lock.
  - `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
    - Publishes `payload` to all subscribers whose **topic pattern** matches `topic` and whose **routing_key pattern** matches `routing_key`.
  - `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread`
    - Registers a subscriber for a `topic` and `routing_key` pattern.
    - Starts a **daemon thread** that pulls messages from an internal queue and invokes `callback(payload)`.
    - Returns the started `Thread`.
  - `_match_routing_key(pattern: str, routing_key: str) -> bool` (static)
    - Implements dot-separated wildcard matching for topics and routing keys.

## Configuration/Dependencies
- No external dependencies; uses stdlib:
  - `queue.Queue`, `threading.Thread`, `threading.RLock`
- Depends on `naas_abi_core.services.bus.BusPorts.IBusAdapter` for interface conformance.

## Usage
```python
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import PythonQueueAdapter

bus = PythonQueueAdapter()

def on_message(payload: bytes) -> None:
    print("got:", payload.decode())

# Subscribe to topic "orders" and routing keys like "created.eu", "created.us", etc.
bus.topic_consume(topic="orders", routing_key="created.*", callback=on_message)

bus.topic_publish(topic="orders", routing_key="created.eu", payload=b"order-123")
```

## Caveats
- **In-process only**: no inter-process or network transport.
- `topic_consume(...)` runs callbacks on a **daemon thread**.
- To stop a consumer, the callback must raise `StopIteration` (breaks the consume loop).
- If the callback raises any other exception:
  - the payload is **re-queued** for that subscriber
  - the consumer thread then raises and exits (message may be redelivered if a new consumer is created).
