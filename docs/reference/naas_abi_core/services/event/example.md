# EventService — end-to-end example

A complete, runnable example of the `EventService` accessed via the engine. Covers TTL ontology definition, engine bootstrap, live subscription, publishing, eager and streaming queries, and durable consumer catch-up.

## 1. Define an event type in TTL

`my_app/events.ttl`:

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix abi:  <http://ontology.naas.ai/abi/> .
@prefix ex:   <http://example.org/> .

ex:UserAuthenticated a owl:Class ;
    rdfs:label "user authenticated"@en ;
    rdfs:subClassOf abi:LogProcess .

ex:userId a owl:DatatypeProperty ;
    rdfs:domain ex:UserAuthenticated ;
    rdfs:range  xsd:string .

ex:method a owl:DatatypeProperty ;
    rdfs:domain ex:UserAuthenticated ;
    rdfs:range  xsd:string .
```

Generate the Python module:

```bash
python -m naas_abi_core.utils.onto2py my_app/events.ttl my_app/events.py
```

## 2. Bootstrap and use via the engine

```python
"""End-to-end example of the EventService via the engine."""

from __future__ import annotations

import datetime
import time

from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)
from naas_abi_core.services.event.EventFactory import EventFactory

from my_app.events import UserAuthenticated


# ---------------------------------------------------------------------------
# 1. Bootstrap the engine
# ---------------------------------------------------------------------------

# In-process bus for this example. In production you'd use RabbitMQAdapter.
bus = BusService(PythonQueueAdapter())

# SQLite event log under <project>/storage/events/events.sqlite (auto-created).
events = EventFactory.EventSQLite_find_storage(bus=bus)

# Engine container — exposes services as engine.services.events, .bus, etc.
services = IEngine.Services(bus=bus, events=events)
services.wire_services()


# ---------------------------------------------------------------------------
# 2. Subscribe to live events (live-only — no history replay)
# ---------------------------------------------------------------------------

def on_user_auth(evt: UserAuthenticated) -> None:
    print(f"[live] {evt.user_id} via {evt.method} at {evt.created_at}")

services.events.subscribe(UserAuthenticated, on_user_auth)


# ---------------------------------------------------------------------------
# 3. Publish events
# ---------------------------------------------------------------------------

services.events.publish(UserAuthenticated(user_id="alice", method="oauth_google"))
services.events.publish(UserAuthenticated(user_id="bob",   method="password"))
services.events.publish(UserAuthenticated(user_id="carol", method="oauth_google"))

# Give the in-process bus thread a moment to deliver before we move on.
time.sleep(0.05)


# ---------------------------------------------------------------------------
# 4. Eager historical query
# ---------------------------------------------------------------------------

print("\n--- query (eager, first 2) ---")
for evt in services.events.query(event_class=UserAuthenticated, limit=2):
    print(
        f"  {evt.user_id:6}  method={evt.method:14}  "
        f"created_at={evt.created_at.isoformat()}  seq={evt._seq}"
    )


# ---------------------------------------------------------------------------
# 5. Streaming query with snapshot semantics — no pagination boilerplate
# ---------------------------------------------------------------------------

print("\n--- iter_query (snapshot, batched) ---")
for evt in services.events.iter_query(
    event_class=UserAuthenticated,
    batch_size=2,   # SQL fetch size; not visible to caller
):
    print(f"  seq={evt._seq}  {evt.user_id} ({evt.method})")
# New events published during this loop are NOT included — snapshot at start.


# ---------------------------------------------------------------------------
# 6. Durable consumer with auto-advancing cursor (catch-up)
# ---------------------------------------------------------------------------

print("\n--- iter_query_for_consumer (worker first run) ---")
for evt in services.events.iter_query_for_consumer(
    consumer_id="analytics-worker",
    event_class=UserAuthenticated,
    batch_size=10,
):
    print(f"  processing seq={evt._seq}  user={evt.user_id}")

# Publish more after the first drain
services.events.publish(UserAuthenticated(user_id="dave", method="passkey"))
time.sleep(0.05)

print("\n--- iter_query_for_consumer (worker second run, only new events) ---")
for evt in services.events.iter_query_for_consumer(
    "analytics-worker", UserAuthenticated
):
    print(f"  processing seq={evt._seq}  user={evt.user_id}")
# Cursor for ("analytics-worker", UserAuthenticated) persists in SQLite —
# survives restarts.


# ---------------------------------------------------------------------------
# 7. Filtered / bounded query — useful for exports
# ---------------------------------------------------------------------------

since = (datetime.datetime.now() - datetime.timedelta(minutes=10)).isoformat()

print("\n--- iter_query (last 10 min, max 50 events) ---")
for evt in services.events.iter_query(
    event_class=UserAuthenticated,
    since_timestamp=since,
    limit=50,
):
    print(f"  {evt._stored_at}  {evt.user_id}")
```

## 3. Expected output

```text
[live] alice via oauth_google at 2026-05-22 ...
[live] bob via password at 2026-05-22 ...
[live] carol via oauth_google at 2026-05-22 ...

--- query (eager, first 2) ---
  alice   method=oauth_google   created_at=2026-05-22T...  seq=1
  bob     method=password       created_at=2026-05-22T...  seq=2

--- iter_query (snapshot, batched) ---
  seq=1  alice (oauth_google)
  seq=2  bob (password)
  seq=3  carol (oauth_google)

--- iter_query_for_consumer (worker first run) ---
  processing seq=1  user=alice
  processing seq=2  user=bob
  processing seq=3  user=carol

[live] dave via passkey at 2026-05-22 ...

--- iter_query_for_consumer (worker second run, only new events) ---
  processing seq=4  user=dave

--- iter_query (last 10 min, max 50 events) ---
  2026-05-22T...  alice
  2026-05-22T...  bob
  2026-05-22T...  carol
  2026-05-22T...  dave
```

## 4. Mental model recap

| Access pattern | API |
|---|---|
| Engine handle | `services.events` (typed `EventService`) |
| Persist + broadcast | `services.events.publish(evt)` |
| Listen live | `services.events.subscribe(UserAuthenticated, cb)` |
| Browse history (eager) | `services.events.query(...)` |
| Browse history (streaming, snapshot) | `services.events.iter_query(...)` |
| Durable worker, one batch | `services.events.query_for_consumer(...)` |
| Durable worker, drain all pending | `services.events.iter_query_for_consumer(...)` |

Every method returns instances of your `LogProcess` subclass (`UserAuthenticated` here), with `created_at` always populated and storage metadata (`_seq`, `_stored_at`) attached.
