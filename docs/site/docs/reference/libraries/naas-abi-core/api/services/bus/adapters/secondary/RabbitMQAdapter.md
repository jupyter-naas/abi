# RabbitMQAdapter

## What it is
- A RabbitMQ-backed implementation of `IBusAdapter` using `pika`.
- Supports:
  - Publishing messages to a *topic* exchange.
  - Consuming messages from a durable queue bound to a topic exchange + routing key.
- Provides context-manager support for clean shutdown of the publishing connection.

## Public API
- `class RabbitMQAdapter(IBusAdapter)`
  - `__init__(rabbitmq_url: str)`
    - Store the RabbitMQ connection URL.
  - `__enter__() -> RabbitMQAdapter` / `__exit__(...)`
    - Enables `with RabbitMQAdapter(...) as bus: ...`; closes resources on exit.
  - `close() -> None`
    - Closes the internal publish channel/connection (consumer threads manage their own connections).
  - `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
    - Declares the `topic` exchange (type `topic`, durable) once per adapter instance.
    - Publishes `payload` with `delivery_mode=2` (persistent).
    - On failure: closes publish connection and raises `ConnectionError("RabbitMQ publish failed")`.
  - `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
    - Spawns a daemon thread that:
      - Connects to RabbitMQ, declares a durable topic exchange.
      - Declares a durable, non-exclusive, non-auto-delete queue with a deterministic name based on `(topic, routing_key)`.
      - Binds queue to exchange with the given routing key.
      - Consumes messages with manual ack/nack:
        - `callback(body)` success ⇒ `basic_ack`
        - `StopIteration` from callback ⇒ `basic_ack` and stops consuming (thread exits)
        - any other exception ⇒ `basic_nack(requeue=True)` then re-raises
    - On AMQP/OS error: raises `ConnectionError("RabbitMQ consume failed")` inside the thread.

## Configuration/Dependencies
- Requires `pika`.
- Requires a RabbitMQ URL suitable for `pika.URLParameters`, e.g.:
  - `amqp://user:pass@host:5672/vhost`
- Logging via `naas_abi_core.utils.Logger.logger` (used at debug level when starting consumption).

## Usage
```python
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import RabbitMQAdapter

RABBIT_URL = "amqp://guest:guest@localhost:5672/%2F"

def on_message(body: bytes) -> None:
    print("got:", body.decode("utf-8"))
    # raise StopIteration to stop the consumer thread after one message
    raise StopIteration

with RabbitMQAdapter(RABBIT_URL) as bus:
    bus.topic_publish("events", "user.created", b"hello")
    t = bus.topic_consume("events", "user.created", on_message)
    t.join(timeout=5)
```

## Caveats
- `topic_consume(...)` runs in a daemon thread; exceptions raised there will not be raised in the caller thread.
- Stopping consumption is only implemented via raising `StopIteration` from the callback.
- Queue names are derived from `sha256(f"{topic}:{routing_key}")`; different routing keys create different queues (no wildcards handled beyond RabbitMQ routing itself).
