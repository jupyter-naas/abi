# Bus Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/bus/`. Canonical reference for agents.

## Purpose

Message broker exposing **two independent delivery models**:

- **Pub/sub** — fanout, ephemeral, routing-key matched. Every subscriber receives every matching message. No persistence.
- **Work queue** — durable, exactly-one-consumer per message. Survives restart.

Both models emit `BusMessagePublished` / `BusMessageEnqueued` / `BusError` events through the event service.

## Files

| File | Role |
|---|---|
| `BusPorts.py` | `IBusAdapter` interface |
| `BusService.py` | Public service (event-emitting delegator over adapter) |
| `adapters/secondary/PythonQueueAdapter.py` | SQLite-backed, process-local |
| `adapters/secondary/RabbitMQAdapter.py` | RabbitMQ broker |
| `tests/` | Service + generic adapter contract tests |
| `ontologies/` | Event classes (`BusMessagePublished`, `BusMessageEnqueued`, `BusError`) |

## Port (`BusPorts.py`)

```python
class IBusAdapter:
    # pub/sub
    def publish(topic: str, routing_key: str, payload: bytes) -> None
    def subscribe(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread

    # work queue
    def enqueue(topic: str, routing_key: str, payload: bytes) -> None
    def dequeue(topic: str, routing_key: str, callback: Callable[[bytes], None]) -> Thread
```

Callback contract:

- Receives `bytes` payload.
- Raise `StopIteration` to end the consumer loop.
- Raise any other exception in `dequeue` to trigger redelivery (work queue only).

## Service API (`BusService.py`)

```python
BusService(adapter: IBusAdapter)

publish(topic, routing_key, payload)             # → BusMessagePublished | BusError
subscribe(topic, routing_key, callback) -> Thread
enqueue(topic, routing_key, payload)             # → BusMessageEnqueued | BusError
dequeue(topic, routing_key, callback) -> Thread
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `PythonQueueAdapter` | SQLite (WAL), 60s broadcast retention, at-least-once delivery, in-memory or file persistence |
| `RabbitMQAdapter` | RabbitMQ topic exchanges, durable queues for work, exclusive ephemeral queues for pub/sub, auto-reconnect on stale publishes |

## Instantiation

No factory file:

```python
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import PythonQueueAdapter
from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import RabbitMQAdapter

bus = BusService(PythonQueueAdapter(persistence_path="bus.sqlite", journal_mode="WAL"))
bus = BusService(RabbitMQAdapter(rabbitmq_url="amqp://guest:guest@localhost/"))
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/bus/
uv run pytest libs/naas-abi-core/naas_abi_core/services/bus/tests/BusService_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/bus/tests/bus__secondary_adapter__generic_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/bus/adapters/secondary/PythonQueueAdapter_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/bus/adapters/secondary/RabbitMQAdapter_test.py
```

## Adding a new adapter

1. Implement `IBusAdapter` in `adapters/secondary/<Name>Adapter.py`. All four methods.
2. Respect the delivery contracts: pub/sub fanout vs. work-queue exactly-one-consumer.
3. Run the generic contract tests (`tests/bus__secondary_adapter__generic_test.py`) against the new adapter.
4. Document any backend-specific topic/routing-key syntax in a module docstring.
