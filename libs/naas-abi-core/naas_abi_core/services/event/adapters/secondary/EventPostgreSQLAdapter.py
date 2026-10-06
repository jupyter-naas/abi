"""PostgreSQL-backed durable event log, shared by every engine.

The same model as ``EventSQLiteAdapter``, in its own schema: an ``events`` table
for the log and a ``consumer_cursors`` table for read positions, plus a one-row
``event_sequence`` counter.

Ordering: an append increments the counter and inserts in one transaction. The
counter row stays locked until commit, so the sequence is gapless and events
become visible in sequence order whatever the number of writers or engines: a
reader that pages or advances a cursor by ``seq`` never misses an event
committed late. Numbers are never reused, even once old events are archived.

Old events move to the Dataset Service hourly (``EventPostgreSQLArchive``),
offered to the engine through ``job_owners``.

Payloads are kept byte for byte (``BYTEA``). When a payload is JSON, a ``JSONB``
copy serves ``json_filter``; other payloads never match a filter. Timestamps stay
the caller's ISO strings and compare as text, as with SQLite.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from naas_abi_core.services.event.EventFilter import FilterError, path_parts
from naas_abi_core.services.event.EventPort import (
    EventTypeSummary,
    IEventAdapter,
    StoredEvent,
)

_SCHEMA_RE = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_NUMBER_RE = r"^\s*[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]+)?\s*$"
_COLUMNS = "id, event_type, seq, timestamp, payload"
_REMOVE_CHUNK = 10_000


@dataclass(frozen=True)
class ArchiveBoundary:
    """How far the log may be archived, and the idle consumers that will not
    read the events archived below their cursor."""

    through: int
    idle_consumers: list[tuple[str, str]] = field(default_factory=list)


def _lock_id(name: str) -> int:
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], signed=True)


def _json_body(payload: bytes) -> Any:
    """The payload as JSON for filters, or None when it is not JSON PostgreSQL
    can store (not UTF-8, not JSON, or holding a NUL character)."""
    if b"\\u0000" in payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _like(value: Any) -> str:
    """``value`` as a literal LIKE pattern (wildcards escaped)."""
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _param(value: Any) -> Any:
    """A scalar as the text ``#>>`` extracts: JSON booleans read true/false."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return None if value is None else str(value)


def build_where(filter: dict[str, Any], column: str = "body") -> tuple[str, list]:
    """An EventBridge-style filter as a PostgreSQL WHERE fragment over ``column``
    (JSONB), with the semantics of ``EventFilter.build_where`` for SQLite: values
    compare as extracted text, ranges numerically."""
    clauses: list[str] = []
    params: list[Any] = []
    for key, value in (filter or {}).items():
        path = path_parts(key)
        text = f"({column} #>> %s)"

        def emit(sql: str, *values: Any, path: list[str] = path) -> None:
            clauses.append(sql)
            params.extend([path, *values])

        if isinstance(value, dict):
            for op, operand in value.items():
                if op in ("gt", "gte", "lt", "lte"):
                    symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
                    # Values that are not numbers never match, as in memory.
                    emit(
                        f"(CASE WHEN {text} ~ '{_NUMBER_RE}' "
                        f"THEN ({column} #>> %s)::float8 END) {symbol} %s",
                        path,
                        float(operand),
                    )
                elif op == "eq":
                    emit(f"{text} = %s", _param(operand))
                elif op == "ne":
                    emit(f"{text} <> %s", _param(operand))
                elif op == "in":
                    if not isinstance(operand, list) or not operand:
                        clauses.append("FALSE")
                    else:
                        emit(f"{text} = ANY(%s)", [str(v) for v in operand])
                elif op == "prefix":
                    emit(f"{text} LIKE %s ESCAPE '\\'", f"{_like(operand)}%")
                elif op == "suffix":
                    emit(f"{text} LIKE %s ESCAPE '\\'", f"%{_like(operand)}")
                elif op == "contains":
                    emit(f"{text} LIKE %s ESCAPE '\\'", f"%{_like(operand)}%")
                elif op == "exists":
                    emit(f"{text} IS {'NOT ' if operand else ''}NULL")
                else:
                    raise FilterError(f"Unknown filter operator: {op!r}")
        elif isinstance(value, list):
            if not value:
                clauses.append("FALSE")
            else:
                emit(f"{text} = ANY(%s)", [str(v) for v in value])
        elif value is None:
            emit(f"{text} IS NULL")
        else:
            emit(f"{text} = %s", _param(value))
    return " AND ".join(clauses), params


def _stored(row: tuple) -> StoredEvent:
    return StoredEvent(
        id=row[0],
        event_type=row[1],
        seq=row[2],
        timestamp=row[3],
        payload=bytes(row[4]),
    )


class EventPostgreSQLAdapter(IEventAdapter):
    def __init__(
        self,
        dsn: str,
        schema: str = "abi_event",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
        pool_max_size: int = 10,
        pool_timeout: float = 5.0,
        archive_after_days: float | None = 7.0,
        archive_batch_rows: int = 10_000,
    ):
        """``archive_after_days``: how long events stay here before the archive
        job moves them to the Dataset Service; None keeps them."""
        if not _SCHEMA_RE.fullmatch(schema):
            raise ValueError(
                "schema must be a lowercase PostgreSQL identifier (max 63 bytes)"
            )
        if (
            not dsn
            or connect_timeout <= 0
            or statement_timeout <= 0
            or pool_max_size < 1
            or pool_timeout <= 0
            or not math.isfinite(pool_timeout)
        ):
            raise ValueError("dsn must be nonempty and timeouts must be positive")
        if archive_after_days is not None and not (
            math.isfinite(archive_after_days) and archive_after_days > 0
        ):
            raise ValueError("archive_after_days must be a positive number of days")
        if archive_batch_rows < 1:
            raise ValueError("archive_batch_rows must be at least 1")
        self._schema = schema
        self._events = f'"{schema}".events'
        self._cursors = f'"{schema}".consumer_cursors'
        self._sequence = f'"{schema}".event_sequence'
        self.archive_after_days = archive_after_days
        self.archive_batch_rows = archive_batch_rows
        self._statement_timeout = statement_timeout
        self._pool = ConnectionPool(
            dsn,
            kwargs={"connect_timeout": connect_timeout},
            min_size=1,
            max_size=pool_max_size,
            timeout=pool_timeout,
            open=False,
        )
        try:
            self._pool.open(wait=True, timeout=pool_timeout)
            self._initialize()
        except BaseException:
            self._pool.close()
            raise

    def _initialize(self) -> None:
        with self._transaction() as conn:
            # Serialize first-boot DDL across processes using this schema.
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_lock_id(f"abi-event-ddl:{self._schema}"),),
            )
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}"')
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._events} ("
                "seq BIGINT PRIMARY KEY, "
                'id TEXT COLLATE "C" NOT NULL UNIQUE, '
                'event_type TEXT COLLATE "C" NOT NULL, '
                'timestamp TEXT COLLATE "C" NOT NULL, '
                "payload BYTEA NOT NULL, "
                "body JSONB)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS events_type_seq "
                f"ON {self._events} (event_type, seq)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS events_timestamp "
                f"ON {self._events} (timestamp)"
            )
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._cursors} ("
                'consumer_id TEXT COLLATE "C" NOT NULL, '
                'event_type TEXT COLLATE "C" NOT NULL, '
                "last_seq BIGINT NOT NULL DEFAULT 0, "
                "updated_at TIMESTAMPTZ NOT NULL, "
                "PRIMARY KEY (consumer_id, event_type))"
            )
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._sequence} ("
                "id SMALLINT PRIMARY KEY CHECK (id = 1), last_seq BIGINT NOT NULL)"
            )
            conn.execute(
                f"INSERT INTO {self._sequence} (id, last_seq) "
                f"SELECT 1, COALESCE(MAX(seq), 0) FROM {self._events} "
                "ON CONFLICT (id) DO NOTHING"
            )

    @contextmanager
    def _transaction(self) -> Iterator[psycopg.Connection[Any]]:
        with self._pool.connection() as conn:
            conn.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (str(self._statement_timeout),),
            )
            yield conn

    def close(self) -> None:
        self._pool.close()

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
        body = _json_body(payload)
        with self._transaction() as conn:
            # The counter row stays locked until commit: numbering and
            # visibility follow one order, and a failed insert gives its number back.
            row = conn.execute(
                f"UPDATE {self._sequence} SET last_seq = last_seq + 1 "
                "WHERE id = 1 RETURNING last_seq"
            ).fetchone()
            assert row is not None
            seq = int(row[0])
            conn.execute(
                f"INSERT INTO {self._events} "
                "(seq, id, event_type, timestamp, payload, body) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    seq,
                    event_id,
                    event_type,
                    timestamp,
                    payload,
                    None if body is None else Jsonb(body),
                ),
            )
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
        newest_first: bool = False,
        search: str | None = None,
    ) -> list[StoredEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(event_type)
        if since_seq is not None:
            clauses.append("seq > %s")
            params.append(since_seq)
        if until_seq is not None:
            clauses.append("seq <= %s")
            params.append(until_seq)
        if since_timestamp is not None:
            clauses.append("timestamp >= %s")
            params.append(since_timestamp)
        if until_timestamp is not None:
            clauses.append("timestamp <= %s")
            params.append(until_timestamp)
        if json_filter:
            where_sql, where_params = build_where(json_filter)
            if where_sql:
                clauses.append(where_sql)
                params.extend(where_params)
        if search:
            # The raw payload text, case-insensitively; a payload that is not
            # UTF-8 JSON is read with byte escapes instead of failing the query.
            clauses.append(
                "(CASE WHEN body IS NOT NULL THEN convert_from(payload, 'UTF8') "
                "ELSE encode(payload, 'escape') END) ILIKE %s ESCAPE '\\'"
            )
            params.append(f"%{_like(search)}%")

        sql = f"SELECT {_COLUMNS} FROM {self._events}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq DESC" if newest_first else " ORDER BY seq ASC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        with self._transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_stored(row) for row in rows]

    def max_seq(self, event_type: str | None = None) -> int:
        with self._transaction() as conn:
            if event_type is None:
                row = conn.execute(
                    f"SELECT COALESCE(MAX(seq), 0) FROM {self._events}"
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT COALESCE(MAX(seq), 0) FROM {self._events} "
                    "WHERE event_type = %s",
                    (event_type,),
                ).fetchone()
        return int(row[0]) if row else 0

    def list_event_types(self) -> list[EventTypeSummary]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT t.event_type, t.n, t.last_seq, e.timestamp FROM ("
                "SELECT event_type, COUNT(*) AS n, MAX(seq) AS last_seq "
                f"FROM {self._events} GROUP BY event_type) t "
                f"JOIN {self._events} e ON e.seq = t.last_seq "
                "ORDER BY t.event_type"
            ).fetchall()
        return [
            EventTypeSummary(
                event_type=row[0],
                count=int(row[1]),
                last_seq=int(row[2]),
                last_timestamp=row[3],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # cursor / per-consumer
    # ------------------------------------------------------------------

    def get_cursor(self, consumer_id: str, event_type: str) -> int:
        with self._transaction() as conn:
            row = conn.execute(
                f"SELECT last_seq FROM {self._cursors} "
                "WHERE consumer_id = %s AND event_type = %s",
                (consumer_id, event_type),
            ).fetchone()
        return int(row[0]) if row else 0

    def set_cursor(self, consumer_id: str, event_type: str, last_seq: int) -> None:
        if last_seq < 0:
            raise ValueError(f"last_seq must be >= 0, got {last_seq}")
        with self._transaction() as conn:
            conn.execute(
                f"INSERT INTO {self._cursors} "
                "(consumer_id, event_type, last_seq, updated_at) "
                "VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (consumer_id, event_type) DO UPDATE SET "
                "last_seq = excluded.last_seq, updated_at = excluded.updated_at",
                (consumer_id, event_type, last_seq),
            )

    def query_for_consumer(
        self,
        consumer_id: str,
        event_type: str,
        limit: int | None = None,
        json_filter: dict | None = None,
    ) -> list[StoredEvent]:
        # Compiled first: a malformed filter fails without opening a transaction.
        # The cursor advances to the last *matching* seq (see IEventAdapter).
        where_sql, where_params = build_where(json_filter or {})
        with self._transaction() as conn:
            # Lock the cursor row (created if new) so two readers of one consumer
            # cannot both deliver the same events.
            conn.execute(
                f"INSERT INTO {self._cursors} "
                "(consumer_id, event_type, last_seq, updated_at) "
                "VALUES (%s, %s, 0, now()) ON CONFLICT DO NOTHING",
                (consumer_id, event_type),
            )
            row = conn.execute(
                f"SELECT last_seq FROM {self._cursors} "
                "WHERE consumer_id = %s AND event_type = %s FOR UPDATE",
                (consumer_id, event_type),
            ).fetchone()
            last_seq = int(row[0]) if row else 0
            sql = (
                f"SELECT {_COLUMNS} FROM {self._events} "
                "WHERE event_type = %s AND seq > %s"
            )
            params: list[Any] = [event_type, last_seq]
            if where_sql:
                sql += " AND " + where_sql
                params.extend(where_params)
            sql += " ORDER BY seq ASC"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            if rows:
                conn.execute(
                    f"UPDATE {self._cursors} SET last_seq = %s, updated_at = now() "
                    "WHERE consumer_id = %s AND event_type = %s",
                    (rows[-1][2], consumer_id, event_type),
                )
        return [_stored(row) for row in rows]

    # ------------------------------------------------------------------
    # archiving (EventPostgreSQLArchive)
    # ------------------------------------------------------------------

    def archivable_through(
        self, older_than: str, *, consumers_active_since: datetime
    ) -> ArchiveBoundary:
        """The highest ``seq`` that may be archived: every event up to it is older
        than ``older_than`` (an ISO timestamp), and no consumer that read since
        ``consumers_active_since`` still needs it."""
        with self._transaction() as conn:
            first_recent = conn.execute(
                f"SELECT MIN(seq) FROM {self._events} WHERE timestamp >= %s",
                (older_than,),
            ).fetchone()
            newest = conn.execute(f"SELECT MAX(seq) FROM {self._events}").fetchone()
            if first_recent and first_recent[0] is not None:
                through = int(first_recent[0]) - 1
            else:
                through = int(newest[0]) if newest and newest[0] is not None else 0
            active = conn.execute(
                f"SELECT MIN(last_seq) FROM {self._cursors} WHERE updated_at >= %s",
                (consumers_active_since,),
            ).fetchone()
            if active and active[0] is not None:
                through = min(through, int(active[0]))
            idle = conn.execute(
                f"SELECT consumer_id, event_type FROM {self._cursors} "
                "WHERE updated_at < %s AND last_seq < %s "
                "ORDER BY consumer_id, event_type",
                (consumers_active_since, through),
            ).fetchall()
        return ArchiveBoundary(through, [(row[0], row[1]) for row in idle])

    def remove_through(self, seq: int) -> int:
        """Delete the events numbered up to ``seq`` (already archived), a chunk
        per transaction; returns how many. Their numbers are never reused."""
        removed = 0
        while True:
            with self._transaction() as conn:
                deleted = conn.execute(
                    f"DELETE FROM {self._events} WHERE seq IN ("
                    f"SELECT seq FROM {self._events} WHERE seq <= %s "
                    "ORDER BY seq LIMIT %s)",
                    (seq, _REMOVE_CHUNK),
                ).rowcount
            removed += deleted
            if deleted < _REMOVE_CHUNK:
                return removed

    def job_owners(self, services: Any) -> dict[str, Any]:
        """The archive job, when archiving is on and the engine has datasets
        (``Engine.job_owners`` collects these from service adapters)."""
        if self.archive_after_days is None or not services.dataset_available():
            return {}
        from datetime import timedelta

        from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLArchive import (
            EVENT_ARCHIVE_OWNER,
            EventArchiveJobs,
        )

        return {
            EVENT_ARCHIVE_OWNER: EventArchiveJobs(
                self,
                services.dataset,
                namespace=self._schema,
                retain=timedelta(days=self.archive_after_days),
                batch_rows=self.archive_batch_rows,
            )
        }
