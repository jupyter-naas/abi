import os
import sqlite3
import time
import threading
from threading import Event, Thread
from typing import Callable

from naas_abi_core.services.bus.BusPorts import IBusAdapter


class PythonQueueAdapter(IBusAdapter):
    """Process-local durable queue using sqlite.

    The adapter provides at-least-once delivery semantics. Messages are persisted
    before publish returns and are replayed after restart when using a file path.
    """

    _SHARED_IN_MEMORY_URI = "file:python_queue_adapter?mode=memory&cache=shared"

    def __init__(
        self,
        persistence_path: str | None = None,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
        poll_interval_seconds: float = 0.05,
        lock_timeout_seconds: float = 1.0,
    ) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._lock_timeout_seconds = lock_timeout_seconds

        if persistence_path is None:
            db_target = self._SHARED_IN_MEMORY_URI
            uri = True
        else:
            os.makedirs(os.path.dirname(persistence_path) or ".", exist_ok=True)
            db_target = persistence_path
            uri = False

        self._conn = sqlite3.connect(
            db_target,
            uri=uri,
            timeout=max(0.0, busy_timeout_ms / 1000),
            check_same_thread=False,
        )
        self._conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        self._conn.execute(f"PRAGMA journal_mode={journal_mode}")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                routing_key TEXT NOT NULL,
                payload BLOB NOT NULL,
                locked_until REAL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()
        self._db_lock = threading.RLock()

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        with self._db_lock:
            self._conn.execute(
                "INSERT INTO bus_messages(topic, routing_key, payload, created_at) VALUES(?, ?, ?, ?)",
                (topic, routing_key, payload, time.time()),
            )
            self._conn.commit()

    def _claim_next(self, topic: str, routing_key: str) -> tuple[int, bytes] | None:
        now = time.time()
        lease_until = now + self._lock_timeout_seconds

        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT id, topic, routing_key, payload
                FROM bus_messages
                WHERE locked_until IS NULL OR locked_until <= ?
                ORDER BY id ASC
                """,
                (now,),
            ).fetchall()

            for row in rows:
                message_id = int(row[0])
                message_topic = str(row[1])
                message_routing_key = str(row[2])
                message_payload = bytes(row[3])

                if not self._match_routing_key(topic, message_topic):
                    continue
                if not self._match_routing_key(routing_key, message_routing_key):
                    continue

                updated = self._conn.execute(
                    """
                    UPDATE bus_messages
                    SET locked_until = ?, attempts = attempts + 1
                    WHERE id = ? AND (locked_until IS NULL OR locked_until <= ?)
                    """,
                    (lease_until, message_id, now),
                )
                if updated.rowcount > 0:
                    self._conn.commit()
                    return message_id, message_payload

            return None

    def _ack(self, message_id: int) -> None:
        with self._db_lock:
            self._conn.execute("DELETE FROM bus_messages WHERE id = ?", (message_id,))
            self._conn.commit()

    def _release(self, message_id: int) -> None:
        with self._db_lock:
            self._conn.execute(
                "UPDATE bus_messages SET locked_until = NULL WHERE id = ?",
                (message_id,),
            )
            self._conn.commit()

    def topic_consume(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        stop_event = Event()

        def _consume_loop() -> None:
            while not stop_event.is_set():
                claimed = self._claim_next(topic=topic, routing_key=routing_key)
                if claimed is None:
                    time.sleep(self._poll_interval_seconds)
                    continue

                message_id, payload = claimed
                try:
                    callback(payload)
                    self._ack(message_id)
                except StopIteration:
                    self._ack(message_id)
                    stop_event.set()
                except Exception:
                    self._release(message_id)
                    raise

        thread = Thread(target=_consume_loop, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _match_routing_key(pattern: str, routing_key: str) -> bool:
        pattern_parts = pattern.split(".") if pattern else [""]
        key_parts = routing_key.split(".") if routing_key else [""]

        def _match(p_index: int, k_index: int) -> bool:
            while True:
                if p_index >= len(pattern_parts):
                    return k_index >= len(key_parts)

                token = pattern_parts[p_index]
                if token == "#":
                    if p_index == len(pattern_parts) - 1:
                        return True
                    for next_index in range(k_index, len(key_parts) + 1):
                        if _match(p_index + 1, next_index):
                            return True
                    return False

                if k_index >= len(key_parts):
                    return False

                if token != "*" and token != key_parts[k_index]:
                    return False

                p_index += 1
                k_index += 1

        return _match(0, 0)
