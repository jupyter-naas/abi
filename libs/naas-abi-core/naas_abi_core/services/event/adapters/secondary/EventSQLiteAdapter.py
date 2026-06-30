"""SQLite-backed durable event log.

Single-file SQLite database in WAL mode. One `events` table for the durable
log and one `consumer_cursors` table for per-(consumer_id, event_type) read
positions used by `query_for_consumer`.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import threading

from naas_abi_core.services.event.EventFilter import build_where
from naas_abi_core.services.event.EventPort import IEventAdapter, StoredEvent


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    payload    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_type_seq  ON events(event_type, seq);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

CREATE TABLE IF NOT EXISTS consumer_cursors (
    consumer_id TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    last_seq    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (consumer_id, event_type)
);
"""


class EventSQLiteAdapter(IEventAdapter):
    def __init__(self, db_path: str):
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._db_path = db_path
        # check_same_thread=False because the adapter may be called from
        # publisher and consumer threads; we serialize writes ourselves.
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # append
    # ------------------------------------------------------------------

    def append(
        self,
        event_id: str,
        event_type: str,
        timestamp: str,
        payload: bytes,
    ) -> StoredEvent:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (id, event_type, timestamp, payload) "
                "VALUES (?, ?, ?, ?)",
                (event_id, event_type, timestamp, payload),
            )
            seq = cur.lastrowid
        assert seq is not None, "sqlite did not assign a seq on INSERT"
        return StoredEvent(
            id=event_id,
            event_type=event_type,
            seq=seq,
            timestamp=timestamp,
            payload=payload,
        )

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    def query(
        self,
        event_type: str | None = None,
        since_seq: int | None = None,
        until_seq: int | None = None,
        since_timestamp: str | None = None,
        until_timestamp: str | None = None,
        json_filter: dict | None = None,
        limit: int | None = None,
    ) -> list[StoredEvent]:
        clauses: list[str] = []
        params: list[object] = []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if since_seq is not None:
            clauses.append("seq > ?")
            params.append(since_seq)
        if until_seq is not None:
            clauses.append("seq <= ?")
            params.append(until_seq)
        if since_timestamp is not None:
            clauses.append("timestamp >= ?")
            params.append(since_timestamp)
        if until_timestamp is not None:
            clauses.append("timestamp <= ?")
            params.append(until_timestamp)
        if json_filter:
            where_sql, where_params = build_where(json_filter, column="payload")
            if where_sql:
                clauses.append(where_sql)
                params.extend(where_params)

        sql = "SELECT id, event_type, seq, timestamp, payload FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            StoredEvent(id=r[0], event_type=r[1], seq=r[2], timestamp=r[3], payload=r[4])
            for r in rows
        ]

    def max_seq(self, event_type: str | None = None) -> int:
        if event_type is None:
            sql = "SELECT COALESCE(MAX(seq), 0) FROM events"
            params: tuple = ()
        else:
            sql = "SELECT COALESCE(MAX(seq), 0) FROM events WHERE event_type = ?"
            params = (event_type,)
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # cursor / per-consumer
    # ------------------------------------------------------------------

    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_seq FROM consumer_cursors "
                "WHERE consumer_id = ? AND event_type = ?",
                (consumer_id, event_type),
            ).fetchone()
        return int(row[0]) if row else 0

    def query_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
        json_filter: dict | None = None,
    ) -> list[StoredEvent]:
        # Translate the filter BEFORE BEGIN IMMEDIATE: build_where is pure
        # string work that can raise FilterError on a malformed filter, and we
        # don't want a bad filter to abort a transaction or hold the write lock
        # — it should fail fast as a plain caller error.
        #
        # Pushdown payload filter (EventBridge-style) so the per-tick `limit`
        # budget and the cursor advance only over events the consumer wants.
        # CURSOR SEMANTICS: the cursor advances to the last *matching* seq read,
        # so ANY non-matching event whose seq is below a matching one — interior
        # or not — is skipped *permanently* for this consumer (the cursor never
        # moves backward). Only non-matching events ABOVE the last match stay
        # pending. The filter predicate is an unindexed JSON extraction
        # (`payload ->> '$.path'`), so a long trailing run of non-matching
        # events is fully re-scanned on every tick until a matching event
        # advances the cursor past them — not free. And because the cursor key
        # is (consumer_id, event_type) and does NOT include the filter, a
        # consumer_id MUST use a stable filter for its lifetime; draining it
        # with a different filter (or none) permanently drops whatever an
        # earlier filter skipped.
        where_sql = ""
        where_params: list[object] = []
        if json_filter:
            where_sql, where_params = build_where(json_filter, column="payload")

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT last_seq FROM consumer_cursors "
                    "WHERE consumer_id = ? AND event_type = ?",
                    (consumer_id, event_type),
                ).fetchone()
                last_seq = int(row[0]) if row else 0

                sql = (
                    "SELECT id, event_type, seq, timestamp, payload FROM events "
                    "WHERE event_type = ? AND seq > ?"
                )
                params: list[object] = [event_type, last_seq]
                if where_sql:
                    sql += " AND " + where_sql
                    params.extend(where_params)
                sql += " ORDER BY seq ASC"
                if limit is not None:
                    sql += " LIMIT ?"
                    params.append(limit)
                rows = self._conn.execute(sql, params).fetchall()

                if rows:
                    new_seq = rows[-1][2]
                    self._conn.execute(
                        "INSERT INTO consumer_cursors (consumer_id, event_type, last_seq, updated_at) "
                        "VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(consumer_id, event_type) DO UPDATE SET "
                        "  last_seq = excluded.last_seq, "
                        "  updated_at = excluded.updated_at",
                        (
                            consumer_id,
                            event_type,
                            new_seq,
                            datetime.datetime.now().isoformat(),
                        ),
                    )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return [
            StoredEvent(id=r[0], event_type=r[1], seq=r[2], timestamp=r[3], payload=r[4])
            for r in rows
        ]
