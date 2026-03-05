import os
import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional
import time

from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVNotFoundError,
)


@dataclass(frozen=True)
class _Entry:
    value: bytes
    expires_at: Optional[float]


class PythonAdapter(IKeyValueAdapter):
    _store: dict[str, _Entry]
    _lock: threading.RLock

    def __init__(
        self,
        persistence_path: str | None = None,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        self._store: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

        if persistence_path is not None:
            os.makedirs(os.path.dirname(persistence_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(
                persistence_path,
                timeout=max(0.0, busy_timeout_ms / 1000),
                check_same_thread=False,
            )
            self._conn.execute(f"PRAGMA journal_mode={journal_mode}")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    expires_at REAL
                )
                """
            )
            self._conn.commit()

    @staticmethod
    def _normalize_value(value: bytes | str) -> bytes:
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, memoryview):
            return value.tobytes()
        return bytes(value)

    @staticmethod
    def _compute_expiration(ttl: int | None) -> Optional[float]:
        if ttl is None:
            return None
        return time.time() + ttl

    @staticmethod
    def _now() -> float:
        return time.time()

    def _purge_if_expired(self, key: str) -> None:
        if self._conn is not None:
            self._conn.execute(
                "DELETE FROM kv_store WHERE key = ? AND expires_at IS NOT NULL AND expires_at <= ?",
                (key, self._now()),
            )
            return

        entry = self._store.get(key)
        if entry is None:
            return
        if entry.expires_at is not None and entry.expires_at <= self._now():
            del self._store[key]

    def get(self, key: str) -> bytes:
        with self._lock:
            self._purge_if_expired(key)
            if self._conn is not None:
                row = self._conn.execute(
                    "SELECT value FROM kv_store WHERE key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise KVNotFoundError(f"Key not found: {key}")
                return bytes(row[0])

            entry = self._store.get(key)
            if entry is None:
                raise KVNotFoundError(f"Key not found: {key}")
            return entry.value

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        normalized = self._normalize_value(value)
        expires_at = self._compute_expiration(ttl)
        with self._lock:
            if self._conn is not None:
                self._conn.execute(
                    "INSERT OR REPLACE INTO kv_store(key, value, expires_at) VALUES(?, ?, ?)",
                    (key, normalized, expires_at),
                )
                self._conn.commit()
                return
            self._store[key] = _Entry(value=normalized, expires_at=expires_at)

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        normalized = self._normalize_value(value)
        expires_at = self._compute_expiration(ttl)
        with self._lock:
            self._purge_if_expired(key)
            if self._conn is not None:
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO kv_store(key, value, expires_at) VALUES(?, ?, ?)",
                    (key, normalized, expires_at),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            if key in self._store:
                return False
            self._store[key] = _Entry(value=normalized, expires_at=expires_at)
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._purge_if_expired(key)
            if self._conn is not None:
                cursor = self._conn.execute(
                    "DELETE FROM kv_store WHERE key = ?",
                    (key,),
                )
                self._conn.commit()
                if cursor.rowcount == 0:
                    raise KVNotFoundError(f"Key not found: {key}")
                return
            if key not in self._store:
                raise KVNotFoundError(f"Key not found: {key}")
            del self._store[key]

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        normalized = self._normalize_value(value)
        with self._lock:
            self._purge_if_expired(key)
            if self._conn is not None:
                cursor = self._conn.execute(
                    "DELETE FROM kv_store WHERE key = ? AND value = ?",
                    (key, normalized),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.value != normalized:
                return False
            del self._store[key]
            return True

    def exists(self, key: str) -> bool:
        with self._lock:
            self._purge_if_expired(key)
            if self._conn is not None:
                row = self._conn.execute(
                    "SELECT 1 FROM kv_store WHERE key = ? LIMIT 1",
                    (key,),
                ).fetchone()
                return row is not None
            return key in self._store
