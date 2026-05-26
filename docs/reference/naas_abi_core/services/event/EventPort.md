# EventPort

## What it is
Interface (port) definitions for a durable event log with live broadcast:
- A `StoredEvent` record returned by the durable log.
- An adapter interface (`IEventAdapter`) for storage backends.
- A service interface (`IEventService`) for higher-level event operations (publish, query, query-for-consumer, subscribe).
- Event-related exceptions (`EventNotFoundError`, `InvalidEventError`).

Events themselves are not modeled in this port: a published event must be an instance of a `LogProcess` subclass (an `onto2py`-generated Pydantic class whose class IRI identifies the event type).

## Public API

### Exceptions
- `EventNotFoundError`: missing event lookup.
- `InvalidEventError`: raised when `publish()` receives an object that is not a `LogProcess` subclass instance.

### Models
- `StoredEvent(dataclass, frozen=True)`
  - Fields:
    - `id: str` — instance IRI (the `LogProcess` instance's `_uri`).
    - `event_type: str` — class IRI (the `LogProcess` subclass's `_class_uri`).
    - `seq: int` — global monotonic sequence assigned by the adapter on append.
    - `timestamp: str` — ISO 8601 timestamp.
    - `payload: bytes` — serialized RDF graph (n-triples).

### Interfaces

#### `IEventAdapter` (secondary port — durable log)
- `append(event_id, event_type, timestamp, payload) -> StoredEvent` — persist one event; returns the stored record with its assigned `seq`.
- `query(event_type=None, since_seq=None, until_seq=None, since_timestamp=None, until_timestamp=None, limit=None) -> list[StoredEvent]` — filtered read, ordered by `seq` ascending.
- `max_seq(event_type=None) -> int` — highest stored `seq` (0 if empty). Used by iterators to capture a snapshot upper bound.
- `get_cursor(consumer_id, event_type) -> int` — return last delivered `seq` for `(consumer_id, event_type)`; `0` if unset.
- `query_for_consumer(consumer_id, event_type, limit=None) -> list[StoredEvent]` — return events with `seq > cursor` and advance the cursor atomically in the same transaction.

#### `IEventService` (primary port)
- `publish(event) -> StoredEvent` — persist a `LogProcess` subclass instance and broadcast it on the bus. Raises `InvalidEventError` if `event` is not a `LogProcess` subclass instance.
- `query(event_class=None, since_seq=None, until_seq=None, since_timestamp=None, until_timestamp=None, limit=None) -> list` — eager read. Return reconstructed event instances matching the filters.
- `iter_query(event_class=None, since_seq=None, since_timestamp=None, until_timestamp=None, batch_size=500) -> Iterator` — streaming read with snapshot semantics; caller doesn't manage pagination.
- `query_for_consumer(consumer_id, event_class, limit=None) -> list` — eager. Return undelivered events for `consumer_id` and advance the cursor.
- `iter_query_for_consumer(consumer_id, event_class, batch_size=500) -> Iterator` — drain all pending events for `consumer_id` across batches, advancing the cursor each batch.
- `subscribe(event_class, callback, routing_key="#") -> Thread` — subscribe to live events via the bus. **Live-only — does not replay history.** Use `query_for_consumer` / `iter_query_for_consumer` for catch-up.

## Configuration/Dependencies
- Standard library: `abc`, `dataclasses`, `threading`, `typing`.
- No runtime configuration is defined in this module.

## Usage

```python
from naas_abi_core.services.event.EventPort import IEventService
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess

def emit(svc: IEventService, evt: LogProcess) -> None:
    svc.publish(evt)
```

## Caveats
- `subscribe(...)` is **live-only**: subscribers who are not connected at publish time will not receive the event. Late or restarted subscribers must catch up via `query_for_consumer`.
- The cursor in `query_for_consumer` advances **on read**, before processing. A consumer that crashes after the call returns but before processing the events will not see those events again — this is at-most-once semantics by design (v1).
