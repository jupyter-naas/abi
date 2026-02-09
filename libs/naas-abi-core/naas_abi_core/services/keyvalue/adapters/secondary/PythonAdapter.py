import threading
import time
from dataclasses import dataclass
from typing import Optional

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
    _lock: threading.Lock

    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._lock = threading.Lock()

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
        return time.monotonic() + ttl

    def _purge_if_expired(self, key: str) -> None:
        entry = self._store.get(key)
        if entry is None:
            return
        if entry.expires_at is not None and entry.expires_at <= time.monotonic():
            del self._store[key]

    def get(self, key: str) -> bytes:
        with self._lock:
            self._purge_if_expired(key)
            entry = self._store.get(key)
            if entry is None:
                raise KVNotFoundError(f"Key not found: {key}")
            return entry.value

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        normalized = self._normalize_value(value)
        expires_at = self._compute_expiration(ttl)
        with self._lock:
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
            if key in self._store:
                return False
            self._store[key] = _Entry(value=normalized, expires_at=expires_at)
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._store:
                raise KVNotFoundError(f"Key not found: {key}")
            del self._store[key]

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        normalized = self._normalize_value(value)
        with self._lock:
            self._purge_if_expired(key)
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
            return key in self._store
        with self._lock:
            self._purge_if_expired(key)
            return key in self._store
