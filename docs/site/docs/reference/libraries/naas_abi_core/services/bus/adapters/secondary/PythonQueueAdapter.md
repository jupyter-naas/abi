# PythonQueueAdapter

## What it is
- A process-local bus adapter implementing `IBusAdapter` using SQLite as a durable queue.
- Provides **at-least-once** delivery:
  - Messages are persisted before `topic_publish` returns.
  - Messages can be replayed after restart when using a file-backed SQLite database.

## Public API
- `class PythonQueueAdapter(IBusAdapter)`
  - `__init__(persistence_path: str | None = None, journal_mode: str = "WAL", busy_timeout_ms: int = 5000, poll_interval_seconds: float = 0.05, lock_timeout_seconds: float = 1.0)`
    - Creates/opens a SQLite database and ensures the `bus_messages` table exists.
    - `persistence_path=None` uses a shared in-memory SQLite URI.
  - `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
    - Persists a message to the queue.
  - `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
    - Starts a daemon thread that polls for matching messages and invokes `callback(payload)`.
    - Acknowledges messages on successful callback completion.
    - If `callback` raises `StopIteration`, the message is acknowledged and the consumer stops.

## Configuration/Dependencies
- Dependencies:
  - Standard library: `sqlite3`, `threading`, `time`, `os`.
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter`.
- SQLite pragmas configured on init:
  - `busy_timeout` (from `busy_timeout_ms`)
  - `journal_mode` (default `"WAL"`)
  - `synchronous=NORMAL`
- Persistence:
  - `persistence_path=None` → shared in-memory DB (`file:python_queue_adapter?mode=memory&cache=shared`, `uri=True`).
  - `persistence_path="path/to/db.sqlite"` → file-backed DB; parent directory is created if needed.

## Usage
```python
import time
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import PythonQueueAdapter

adapter = PythonQueueAdapter(persistence_path="queue.sqlite")

def on_message(payload: bytes) -> None:
    print("got:", payload.decode())

adapter.topic_consume(topic="orders.*", routing_key="created.#", callback=on_message)

adapter.topic_publish(topic="orders.eu", routing_key="created.web", payload=b"hello")
time.sleep(0.2)  # allow background consumer to process
```

## Caveats
- Delivery is **at-least-once**:
  - If the callback raises an exception (other than `StopIteration`), the message is **released** (unlock) and will be retried; the consumer thread re-raises the exception.
- Routing key matching supports:
  - `*` matches exactly one dot-separated token.
  - `#` matches zero or more tokens (when at end, matches the remainder).
- `topic_consume(...)` returns a daemon `Thread` but does not expose the internal stop event; stopping is only supported by raising `StopIteration` inside the callback.
