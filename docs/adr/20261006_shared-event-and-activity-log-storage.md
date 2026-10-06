# Shared storage for the event log and the activity log

## Status
Accepted.

## Date
2026-10-06

## Context
A deploy with a rollout id hands over between engines without downtime, which
requires every service the engine owns to keep its data on a shared backend
(`20261006_single-serving-engine.md`). The event log and the activity log only
had SQLite adapters, so every such deploy was refused.

- The **activity log** records per-actor events and pages them by `seq`. All of
  its queries are top-level equality and range filters, which the Document
  Service supports with indexes.
- The **event log** needs things the Document Service lacks: a global sequence
  assigned atomically, filters on nested paths, prefixes and substrings, search
  over the raw payload, and per-type counts. Every service write (key-value,
  cache, object storage, and others) publishes an event, so appends are frequent.

## Decision

### The activity log in the Document Service
`ActivityLogDocumentAdapter` stores the log in the namespace
`naas_abi_core.services.activity_log`:

- an `events` collection with one document per event, id
  `<actor_id>#<seq, 20 digits>`, and indexed `actor_id`, `seq`, `event_type` and
  `timestamp`;
- an `actors` collection with one document per actor, written the first time an
  actor appears.

Each actor's `seq` is the next number after its newest event, written
create-only. A writer only picks n + 1 once event n is stored, so a reader paging
by `seq` never misses an event stored late. On a conflict (another engine
recorded first), the writer reads the newest `seq` again and retries. An engine
keeps each actor's newest `seq` in memory, so a record costs one write.

The adapter gets the engine's Document Service through `set_services`, as cache
tiers do. In NATS mode this is the NATS facade, following the network-boundaries
rule. `adapter: document` takes no config and is now the default. Its data is
shared exactly when the Document Service is: PostgreSQL yes, SQLite no.

### The event log on PostgreSQL
`EventPostgreSQLAdapter` keeps the SQLite model in its own schema (default
`abi_event`): an `events` table and a `consumer_cursors` table.

- **Ordering.** An append increments a one-row counter and inserts in one
  transaction. The counter row stays locked until commit, so the sequence is
  gapless, and events become visible in sequence order whatever the number of
  writers or engines: cursors and snapshots never skip an event committed late.
  A PostgreSQL sequence would hand out numbers before commit and break this.
  (The first version numbered `MAX(seq) + 1` under an advisory lock; the counter
  replaced it so that archiving cannot make numbers restart,
  `20261006_event-log-archive.md`.)
- **Payloads** are kept byte for byte (`BYTEA`). When a payload is UTF-8 JSON
  without NUL, a `JSONB` copy serves `json_filter`. Other payloads never match a
  filter.
- **Filters** follow the SQLite semantics: values compare as extracted text, and
  lists mean "one of". Two differences are deliberate:
  - numeric ranges ignore values that are not numbers, where SQLite casts them
    to 0;
  - prefix, suffix and contains match LIKE wildcards literally.
- **Search** is a case-insensitive substring of the raw payload text. A payload
  that is not UTF-8 is read with byte escapes, so it cannot fail the query.
- **Timestamps** stay the caller's ISO strings and compare as text, as with
  SQLite. Type summaries sort by byte order.
- **Consumers.** `query_for_consumer` locks the cursor row (`FOR UPDATE`, created
  if new) for the read and the advance, so two readers of one consumer never
  deliver the same events.

Config (`adapter: postgresql`): `dsn`, `schema`, and the same timeouts and pool
settings as the Document Service's PostgreSQL adapter. The DSN never appears in
`repr` or validation errors. `EventFactory.EventServicePostgreSQL` builds the
service. The default event adapter stays SQLite for development.

## Consequences
- With PostgreSQL documents and the PostgreSQL event log, a deploy with a rollout
  id passes the shared-backend check.
- **Existing activity logs are not migrated.** Engines on the new default start
  with an empty activity log in documents; the per-actor SQLite files under
  `storage/activity_log` stay on disk. An installation that needs the history
  keeps `adapter: sqlite` until it is copied.
- **Event throughput.** Appends are serialized by the advisory lock: one short
  transaction each, a few milliseconds on PostgreSQL, against well under a
  millisecond on local SQLite. Every service write that publishes an event pays
  that latency.
- The PostgreSQL event log keeps 7 days; older events move to the Dataset
  Service hourly (`20261006_event-log-archive.md`). The SQLite log still grows
  without bound.
- **Tests:**
  - The SQLite event adapter's behaviour tests moved, unchanged, into a storage
    contract (`EventStorageContract`) that both event stores run. The NATS
    client keeps the base contract.
  - The activity log's generic contract runs on SQLite and PostgreSQL documents.
  - CI runs both on PostgreSQL (`make test-event-core` in `pull_request.yml`,
    with `EVENT_TEST_POSTGRES_DSN` and `DOCUMENT_TEST_POSTGRES_DSN`).
