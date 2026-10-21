# EventSQLiteAdapter

## What it is
SQLite-backed `IEventAdapter`. Single file, WAL mode, two tables:
- `events` — durable append-only log with a global monotonic `seq` (autoincrement primary key).
- `consumer_cursors` — per-(consumer_id, event_type) read position used by `query_for_consumer`.

## Schema
```sql
CREATE TABLE events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX idx_events_type_seq  ON events(event_type, seq);
CREATE INDEX idx_events_timestamp ON events(timestamp);

CREATE TABLE consumer_cursors (
    consumer_id TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    last_seq    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (consumer_id, event_type)
);
```

## Public API

### `class EventSQLiteAdapter(IEventAdapter)`
- `__init__(db_path: str)`
  - Opens (and creates if missing) the SQLite file at `db_path`. Parent directories are created.
  - Sets `journal_mode=WAL` and `synchronous=NORMAL`.
- `close() -> None`
- `append(event_id, event_type, timestamp, payload) -> StoredEvent`
- `query(event_type=None, since_seq=None, since_timestamp=None, until_timestamp=None, limit=None) -> list[StoredEvent]`
- `get_cursor(consumer_id, event_type) -> int`
- `query_for_consumer(consumer_id, event_type, limit=None) -> list[StoredEvent]`
  - Atomic: read + cursor advance happen inside `BEGIN IMMEDIATE`.

## Configuration/Dependencies
- Standard library: `sqlite3`, `threading`, `os`, `datetime`.

## Caveats
- One file, one writer at a time (WAL allows concurrent readers). Heavy multi-process write contention may require splitting (not v1).
- `append` raises `sqlite3.IntegrityError` if `event_id` already exists. Caller (the service layer) is expected to use unique instance IRIs.
- `query_for_consumer` is **at-most-once on read**: the cursor advances before the caller processes. There is no ack/nack in v1.
