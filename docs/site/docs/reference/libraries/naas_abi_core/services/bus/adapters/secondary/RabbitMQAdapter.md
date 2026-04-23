# RabbitMQAdapter

## What it is
- A RabbitMQ-backed implementation of `IBusAdapter` using `pika`.
- Supports:
  - Publishing messages to a durable *topic* exchange.
  - Consuming messages from a durable, non-exclusive, non-auto-deleted queue bound to a topic/routing key.
- Provides basic connection management for publishing (reuses a channel and reconnects once on failure).

## Public API
- `class RabbitMQAdapter(IBusAdapter)`
  - `__init__(rabbitmq_url: str)`
    - Store RabbitMQ connection URL.
  - Context manager:
    - `__enter__() -> RabbitMQAdapter`
    - `__exit__(exc_type, exc, tb) -> bool` (calls `close()`, does not suppress exceptions)
  - `close() -> None`
    - Closes the internal publish connection/channel and clears cached exchange declarations.
  - `topic_publish(topic: str, routing_key: str, payload: bytes) -> None`
    - Publishes `payload` to a durable topic exchange named `topic` with routing key `routing_key`.
    - If publish fails, drops the cached connection and retries once, then raises `ConnectionError` on failure.
  - `topic_consume(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> threading.Thread`
    - Starts a daemon thread that:
      - Declares a durable topic exchange named `topic`.
      - Declares a durable queue whose name is derived from `topic` and `routing_key` via SHA-256.
      - Binds the queue to the exchange with `routing_key`.
      - Consumes messages and calls `callback(body)`.
    - Acknowledgement behavior:
      - On success: `basic_ack`.
      - If `callback` raises `StopIteration`: `basic_ack` then stop consuming.
      - On other exceptions: `basic_nack(requeue=True)` and re-raise (terminates the consumer loop with an error).

## Configuration/Dependencies
- Requires `pika`.
- Requires a RabbitMQ URL string compatible with `pika.URLParameters`, e.g.:
  - `amqp://guest:guest@localhost:5672/%2F`
- Declares exchanges as:
  - `exchange_type="topic"`, `durable=True`
- Publish message properties:
  - `delivery_mode=2` (persistent)

## Usage
```python
import time
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import RabbitMQAdapter

RABBIT_URL = "amqp://guest:guest@localhost:5672/%2F"

def on_message(body: bytes) -> None:
    print("got:", body.decode())
    # Stop after first message:
    raise StopIteration

with RabbitMQAdapter(RABBIT_URL) as bus:
    bus.topic_publish("my.topic", "demo.key", b"hello")
    t = bus.topic_consume("my.topic", "demo.key", on_message)
    time.sleep(1)  # allow consumer thread to run
```

## Caveats
- `topic_consume(...)` runs in a daemon thread; exceptions inside the consumer loop will terminate that thread.
- The consuming queue name is deterministic per `(topic, routing_key)` (SHA-256); multiple consumers using the same pair will share the same queue.
- Stopping consumption is done by raising `StopIteration` from the callback (acks the message, then stops).
