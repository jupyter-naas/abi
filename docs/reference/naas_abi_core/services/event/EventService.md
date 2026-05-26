# EventService

## What it is
A durable event log with live broadcast. Each `publish(event)` is:
1. **Persisted** to the secondary adapter (durability contract).
2. **Broadcast** on the `BusService` topic derived from the event's class IRI (live signaling).

Events are instances of `LogProcess` subclasses — Pydantic classes generated from TTL via `onto2py`. The class IRI (`_class_uri`) acts as the event type; the instance IRI (`_uri`) is the event id.

Subscriptions are live-only. Historical reads go through `query()` (filter-based) or `query_for_consumer()` (per-consumer cursor with auto-advance).

---

## Public API

### `class EventService(ServiceBase, IEventService)`

- `__init__(adapter: IEventAdapter, bus: BusService | None = None)`
  - Requires an adapter. A bus is optional but required for `subscribe()`.
- `publish(event: LogProcess) -> StoredEvent`
  - Persists via the adapter, then broadcasts on the bus topic `class_iri_to_topic(event._class_uri)`. If the bus broadcast fails, the event is still persisted (warning logged).
  - **Populates `event.created_at = datetime.now()` if the caller didn't set it**, before serializing — so the timestamp round-trips through `query`/`iter_query`.
  - Raises `InvalidEventError` if `event` is not a `LogProcess` subclass instance.
- `query(event_class=None, since_seq=None, until_seq=None, since_timestamp=None, until_timestamp=None, limit=None) -> list[LogProcess]`
  - Eager read. Reconstructs each row back into an instance of `event_class` (or `LogProcess` if no class hint is given). Use `since_seq` for stable seq-based pagination.
- `iter_query(event_class=None, since_seq=None, since_timestamp=None, until_timestamp=None, limit=None, batch_size=500) -> Iterator[LogProcess]`
  - Streaming read with **snapshot semantics**: captures the current `max(seq)` at the first call and stops once it has yielded everything up to that point. Events appended during iteration are not included — call again to pick them up. Caller does not have to manage pagination.
  - `limit` caps the total number of events yielded; `batch_size` is the per-round-trip SQL fetch size (defaults to 500).
- `query_for_consumer(consumer_id: str, event_class: type, limit=None) -> list[LogProcess]`
  - Eager. Returns undelivered events for `(consumer_id, event_class._class_uri)` and advances the cursor in the same transaction.
- `iter_query_for_consumer(consumer_id, event_class, limit=None, batch_size=500) -> Iterator[LogProcess]`
  - Drains pending events for `consumer_id` in batches, advancing the cursor per batch. Stops when caught up or when `limit` events have been yielded. The cursor only advances over events actually returned, so a stopped iteration leaves the remainder pending for the next call.
- `subscribe(event_class: type, callback: Callable[[LogProcess], None], routing_key: str = "#") -> Thread`
  - Subscribes to the bus topic for `event_class._class_uri`. The callback receives a reconstructed instance of `event_class`. Requires a `BusService`; raises `RuntimeError` otherwise.

### Module functions
- `class_iri_to_topic(class_iri: str) -> str`
  - Maps a class IRI to a bus-safe topic name: `"evt." + sha256(class_iri)[:32]`. Deterministic; avoids characters that RabbitMQ topic names dislike (`://`, `#`).

---

## Configuration/Dependencies
- `IEventAdapter` implementation (defaults: `EventSQLiteAdapter`).
- `BusService` for live broadcast and subscription (optional but required for `subscribe()`).
- `naas_abi_core.services.event.event_ontology.LogProcess` (generated from `services/event/event.ttl` via `onto2py`).
- Logging via `naas_abi_core.logger`.

---

## Usage

### Define an event type (TTL → onto2py)
```turtle
# my_events.ttl
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix ex:  <http://example.org/> .

ex:UserAuthenticated a owl:Class ;
    rdfs:subClassOf abi:LogProcess ;
    rdfs:label "user authenticated"@en .
```

Generate the Python module:
```bash
python -m naas_abi_core.utils.onto2py my_events.ttl my_events.py
```

### Publish, query, subscribe
```python
from naas_abi_core.services.event.EventFactory import EventFactory
from my_events import UserAuthenticated

events = EventFactory.EventSQLite_find_storage(bus=bus_service)

# Live subscriber (live-only, no history replay)
def on_user_auth(evt: UserAuthenticated) -> None:
    print("auth:", evt.user_id)
events.subscribe(UserAuthenticated, on_user_auth)

# Publish
events.publish(UserAuthenticated(user_id="alice"))

# Historical query (eager)
recent = events.query(event_class=UserAuthenticated, limit=100)

# Streaming over all history without managing pagination (snapshot)
for evt in events.iter_query(event_class=UserAuthenticated, batch_size=500):
    process(evt)

# Catch-up for a durable consumer (eager, one batch)
batch = events.query_for_consumer("worker-1", UserAuthenticated)

# Catch-up streaming until the consumer is up to date
for evt in events.iter_query_for_consumer("worker-1", UserAuthenticated):
    process(evt)
```

---

## Reconstructed events

`query`, `iter_query`, `query_for_consumer`, and `iter_query_for_consumer` all return **instances of the requested `event_class`** (a Pydantic model), not a wrapper. Domain fields you set at publish-time are populated; storage metadata is attached as private attributes:

```python
for evt in events.iter_query(event_class=UserAuthenticated):
    evt.user_id        # domain field set at publish-time
    evt.created_at     # always populated (auto-set by publish if unset)
    evt._uri           # original instance IRI
    evt._seq           # global monotonic sequence (storage metadata)
    evt._stored_at     # ISO timestamp persisted by the adapter
```

## Caveats
- **Live-only subscribe**: events published before a subscriber connects are not delivered to it. Use `query_for_consumer` for catch-up.
- **At-most-once cursor**: `query_for_consumer` advances on read, before the caller processes. If the caller crashes after return, those events will not be returned again.
- **Bus failure does not lose events**: persistence happens first; bus failures are logged and swallowed.
- **Reconstruction without hint class**: `query()` without an `event_class` returns instances of the most-specific Python class found by walking `LogProcess.__subclasses__()`. If the event's class is not imported anywhere in the running process, the row is reconstructed as a bare `LogProcess`.
