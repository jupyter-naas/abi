import json
import os
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote, unquote

from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
)


_DB_SUFFIX = ".sqlite"


class ActivityLogSqliteAdapter(IActivityLogAdapter):
    """One SQLite database file per actor, in WAL mode.

    File layout: ``{data_dir}/actor=<urlencoded(actor_id)>.sqlite``

    Per-actor isolation: writes on different actors never contend; writes
    on the same actor serialize on a per-actor ``threading.Lock``. An LRU
    cache caps the number of simultaneously open connections.
    """

    def __init__(
        self,
        data_dir: str,
        synchronous: Literal["FULL", "NORMAL", "OFF"] = "NORMAL",
        journal_mode: Literal["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"] = "WAL",
        max_open_connections: int = 200,
        busy_timeout_ms: int = 5000,
    ) -> None:
        self._data_dir = data_dir
        self._synchronous = synchronous
        self._journal_mode = journal_mode
        self._max_open_connections = max_open_connections
        self._busy_timeout_ms = busy_timeout_ms

        os.makedirs(self._data_dir, exist_ok=True)

        self._connections: OrderedDict[str, sqlite3.Connection] = OrderedDict()
        self._actor_locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    @staticmethod
    def _encode_actor(actor_id: str) -> str:
        # quote() with safe="" escapes slashes too. Result is a safe single
        # filename segment for every OS.
        return quote(actor_id, safe="")

    @staticmethod
    def _decode_actor(encoded: str) -> str:
        return unquote(encoded)

    def _path_for(self, actor_id: str) -> str:
        return os.path.join(
            self._data_dir, f"actor={self._encode_actor(actor_id)}{_DB_SUFFIX}"
        )

    def _lock_for(self, actor_id: str) -> threading.Lock:
        with self._registry_lock:
            lock = self._actor_locks.get(actor_id)
            if lock is None:
                lock = threading.Lock()
                self._actor_locks[actor_id] = lock
            return lock

    def _get_connection(self, actor_id: str) -> sqlite3.Connection:
        with self._registry_lock:
            conn = self._connections.get(actor_id)
            if conn is not None:
                self._connections.move_to_end(actor_id)
                return conn

            conn = sqlite3.connect(
                self._path_for(actor_id),
                timeout=max(0.0, self._busy_timeout_ms / 1000),
                check_same_thread=False,
                isolation_level=None,  # autocommit; we manage transactions explicitly
            )
            conn.execute(f"PRAGMA journal_mode={self._journal_mode}")
            conn.execute(f"PRAGMA synchronous={self._synchronous}")
            conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL,
                    event_type      TEXT NOT NULL,
                    correlation_id  TEXT,
                    attributes      TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )

            self._connections[actor_id] = conn
            self._evict_if_needed_locked()
            return conn

    def _evict_if_needed_locked(self) -> None:
        # Caller must hold self._registry_lock.
        while len(self._connections) > self._max_open_connections:
            _, victim = self._connections.popitem(last=False)
            try:
                victim.close()
            except sqlite3.Error:
                pass

    @staticmethod
    def _format_ts(ts: datetime) -> str:
        # Always store in UTC ISO8601 so lexicographic ordering matches
        # chronological ordering.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        return ts.isoformat()

    @staticmethod
    def _parse_ts(value: str) -> datetime:
        return datetime.fromisoformat(value)

    def record(self, event: ActivityEvent) -> None:
        conn = self._get_connection(event.actor_id)
        lock = self._lock_for(event.actor_id)
        with lock:
            conn.execute(
                "INSERT INTO events(timestamp, event_type, correlation_id, attributes) "
                "VALUES(?, ?, ?, ?)",
                (
                    self._format_ts(event.timestamp),
                    event.event_type,
                    event.correlation_id,
                    json.dumps(event.attributes),
                ),
            )

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        # If the file doesn't exist yet, the actor has no events. Opening
        # would create an empty DB on disk for nothing.
        if not os.path.exists(self._path_for(actor_id)):
            return []

        conn = self._get_connection(actor_id)
        sql = "SELECT timestamp, event_type, correlation_id, attributes FROM events"
        params: list[object] = []
        clauses: list[str] = []

        if query is not None:
            if query.event_type is not None:
                clauses.append("event_type = ?")
                params.append(query.event_type)
            if query.since is not None:
                clauses.append("timestamp >= ?")
                params.append(self._format_ts(query.since))
            if query.until is not None:
                clauses.append("timestamp <= ?")
                params.append(self._format_ts(query.until))

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id ASC"
        if query is not None and query.limit is not None:
            sql += " LIMIT ?"
            params.append(query.limit)

        lock = self._lock_for(actor_id)
        with lock:
            rows = conn.execute(sql, params).fetchall()

        return [
            ActivityEvent(
                actor_id=actor_id,
                event_type=row[1],
                timestamp=self._parse_ts(row[0]),
                correlation_id=row[2],
                attributes=json.loads(row[3]),
            )
            for row in rows
        ]

    def list_actors(self) -> list[str]:
        if not os.path.isdir(self._data_dir):
            return []
        actors: list[str] = []
        for name in os.listdir(self._data_dir):
            if not name.endswith(_DB_SUFFIX):
                continue
            if not name.startswith("actor="):
                continue
            encoded = name[len("actor=") : -len(_DB_SUFFIX)]
            actors.append(self._decode_actor(encoded))
        return actors

    def shutdown(self) -> None:
        with self._registry_lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._connections.clear()
