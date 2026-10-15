# RabbitMQAdapter

> **Legacy.** Part of the `naas-abi-core[dagster]` / `[rabbitmq]` extras, for projects without NATS; removed in the next major. NATS projects use module jobs and the JetStream bus.

## What it is
- A RabbitMQ-backed implementation of `IBusAdapter` using `pika` (BlockingConnection).
- Provides two messaging patterns:
  - **Work queue** (`enqueue`/`dequeue`): durable *topic* exchange + shared durable queue per `(topic, routing_key)` for load-balanced processing.
  - **Pub/sub** (`publish`/`subscribe`): non-durable, auto-deleted topic exchange + per-subscriber exclusive auto-delete queue (best-effort fanout).

## Public API
- `class RabbitMQAdapter(IBusAdapter)`
  - `__init__(rabbitmq_url: str)`
    - Stores the RabbitMQ URL; initializes internal publish connection/channel cache and a lock.
  - Context manager:
    - `__enter__() -> Self`
    - `__exit__(exc_type, exc, tb) -> bool`
      - Calls `close()`; does **not** suppress exceptions.
  - `close() -> None`
    - Closes cached publish channel/connection and clears declared-exchange cache.

### Work queue (durable)
- `enqueue(topic: str, routing_key: str, payload: bytes) -> None`
  - Publishes persistent messages (`delivery_mode=2`) to a durable topic exchange named `topic`.
  - Reuses a cached publish channel; on failure, drops the cached connection and retries once.
  - Raises `ConnectionError("RabbitMQ publish failed")` if retry fails.
- `dequeue(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
  - Starts a **daemon** consumer thread that:
    - Declares durable topic exchange `topic`.
    - Declares a durable, non-exclusive, non-auto-deleted queue named `naas-abi.<sha256(topic:routing_key)>`.
    - Binds the queue to the exchange with `routing_key`.
    - Consumes with manual acks.
  - Callback/ack behavior:
    - Success: `basic_ack`
    - `StopIteration`: `basic_ack` then `stop_consuming()`
    - Other exceptions: `basic_nack(requeue=True)` then re-raise (thread terminates)
  - Connection/AMQP errors are wrapped as `ConnectionError("RabbitMQ consume failed")`.

### Pub/sub (ephemeral)
- `publish(topic: str, routing_key: str, payload: bytes) -> None`
  - Publishes to exchange `naas-abi.pubsub.<topic>` (`exchange_type="topic"`, `durable=False`, `auto_delete=True`).
  - Uses the cached publish channel (protected by a lock).
- `subscribe(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
  - Starts a **daemon** consumer thread that:
    - Declares exchange `naas-abi.pubsub.<topic>` (non-durable, auto-delete).
    - Declares a server-named queue (`queue=""`) that is `exclusive=True`, `auto_delete=True`, `durable=False`.
    - Binds the queue with `routing_key` (can be a RabbitMQ topic pattern).
  - Callback/ack behavior:
    - Success: `basic_ack`
    - `StopIteration`: `basic_ack` then `stop_consuming()`
    - Other exceptions: `basic_ack` and logs an exception (no requeue; subscriber continues)
  - Connection/AMQP errors are wrapped as `ConnectionError("RabbitMQ subscribe failed")`.

## Configuration/Dependencies
- Dependency: `pika` (import guarded; missing module triggers `raise_missing_extra(..., "The RabbitMQ bus adapter")`).
- Requires a RabbitMQ URL compatible with `pika.URLParameters`, e.g. `amqp://guest:guest@localhost:5672/%2F`.
- Thread-safety:
  - Publishing uses a shared cached `BlockingConnection`/channel protected by an `RLock` (BlockingConnection/Channel must not be used concurrently across threads).
  - Each `dequeue`/`subscribe` call creates its **own** connection/channel inside the consumer thread.

## Usage
```python
import time
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import RabbitMQAdapter

RABBIT_URL = "amqp://guest:guest@localhost:5672/%2F"

def work_handler(body: bytes) -> None:
    print("work:", body.decode())
    raise StopIteration  # stop after one message

def sub_handler(body: bytes) -> None:
    print("event:", body.decode())
    raise StopIteration  # stop after one message

with RabbitMQAdapter(RABBIT_URL) as bus:
    # Work queue (durable, load-balanced across consumers)
    bus.enqueue("jobs.topic", "jobs.key", b"do work")
    bus.dequeue("jobs.topic", "jobs.key", work_handler)

    # Pub/sub (ephemeral per-subscriber queues)
    bus.subscribe("events", "demo.*", sub_handler)
    bus.publish("events", "demo.one", b"hello")

    time.sleep(1)  # allow daemon threads to run
```

## Caveats
- `dequeue()`/`subscribe()` run in **daemon** threads; the process can exit before they finish unless you keep the main thread alive.
- Work-queue queue names are deterministic per `(topic, routing_key)` via SHA-256; multiple consumers with the same pair share the same queue and RabbitMQ load-balances messages.
- `dequeue()` requeues on callback exceptions (except `StopIteration`); `subscribe()` does **not** requeue on callback exceptions (it acks and logs).
