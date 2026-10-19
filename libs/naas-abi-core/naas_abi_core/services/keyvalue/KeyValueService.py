import os
import random
import time
from collections.abc import Iterator
from contextlib import contextmanager

from naas_abi_core import logger
from naas_abi_core.services.iam.enforcement import ResourceGuard, scan_allowed
from naas_abi_core.services.keyvalue.iam_catalog import CATALOG, KEY
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVKeyPage,
    KVLockTimeoutError,
    KVNotFoundError,
    check_page_limit,
)
from naas_abi_core.services.keyvalue.ontologies.modules.KeyValueEventOntology import (
    KeyValueDeleted,
    KeyValueError,
    KeyValueSet,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class KeyValueService(ServiceBase):
    """Bytes by key. Wired into an engine, every operation is authorized on
    ``key/<key>`` (RFC §6.4): a key the caller may not see is missing
    (``KVNotFoundError``, ``exists`` False), and ``list_keys`` returns only the
    keys the caller may list."""

    __adapter: IKeyValueAdapter

    def __init__(self, adapter: IKeyValueAdapter):
        super().__init__()
        self.__adapter = adapter
        self._guard = ResourceGuard.of(CATALOG, self)

    def __require(self, action: str, key: str) -> None:
        self._guard.require(action, KEY, key, not_found=lambda: KVNotFoundError(key))

    @property
    def adapter(self) -> IKeyValueAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self.__adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.emit(event)
        except Exception as exc:  # noqa: BLE001
            # KV store is the source of truth; event logging must never break it.
            logger.warning(f"KeyValueService: failed to publish event: {exc}")

    def get(self, key: str) -> bytes:
        self.__require("Get", key)
        return self.__adapter.get(key)

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self.__require("Set", key)
        try:
            result = self.__adapter.set(key, value, ttl)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(key=key, operation="set", message=str(exc))
            )
            raise
        self.__publish_event(
            KeyValueSet(key=key, size_bytes=len(value), ttl_seconds=ttl)
        )
        return result

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        self.__require("SetIfNotExists", key)
        try:
            wrote = self.__adapter.set_if_not_exists(key, value, ttl)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(key=key, operation="set_if_not_exists", message=str(exc))
            )
            raise
        if wrote:
            self.__publish_event(
                KeyValueSet(key=key, size_bytes=len(value), ttl_seconds=ttl)
            )
        return wrote

    def delete(self, key: str) -> None:
        self.__require("Delete", key)
        try:
            result = self.__adapter.delete(key)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(key=key, operation="delete", message=str(exc))
            )
            raise
        self.__publish_event(KeyValueDeleted(key=key))
        return result

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        self.__require("DeleteIfValueMatches", key)
        try:
            deleted = self.__adapter.delete_if_value_matches(key, value)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(
                    key=key,
                    operation="delete_if_value_matches",
                    message=str(exc),
                )
            )
            raise
        if deleted:
            self.__publish_event(KeyValueDeleted(key=key))
        return deleted

    def exists(self, key: str) -> bool:
        try:
            self.__require("Exists", key)
        except KVNotFoundError:
            return False
        return self.__adapter.exists(key)

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> KVKeyPage:
        """A page of live keys, ascending; pass ``page.next_after`` as ``after``.

        Only the keys the caller may list, paged after filtering (RFC §5.5).
        """
        check_page_limit(limit)
        if self._guard.iam is None or self._guard.allows_every("ListKeys", KEY):
            return self.__adapter.list_keys(prefix, limit=limit, after=after)

        def fetch(scan: str, size: int, cursor: str | None):
            page = self.__adapter.list_keys(scan, limit=size, after=cursor)
            return page.keys, page.next_after

        keys, next_after = scan_allowed(
            self._guard, "ListKeys", KEY, prefix, limit, after, fetch
        )
        return KVKeyPage(tuple(keys), next_after)

    def get_ttl(self, key: str) -> int | None:
        """Seconds before ``key`` expires, ``None`` if never. Raises KVNotFoundError."""
        self.__require("GetTtl", key)
        return self.__adapter.get_ttl(key)

    @contextmanager
    def lock(
        self,
        key: str,
        *,
        ttl: int = 30,
        timeout: float = 10.0,
        retry_delay: float = 0.05,
    ) -> Iterator[None]:
        """Hold an exclusive lock on ``key`` for the duration of the ``with`` block.

        Acquire is ``set_if_not_exists`` with a unique token; release is
        ``delete_if_value_matches`` so only the holder can unlock. ``ttl``
        (seconds) must outlast the critical section so a crashed holder cannot
        block writers forever. Across processes this is only as atomic as the
        adapter (Redis, or PythonAdapter with a shared SQLite file).
        """
        if ttl <= 0:
            raise ValueError("lock ttl must be positive")
        if timeout < 0:
            raise ValueError("lock timeout must be >= 0")
        if retry_delay < 0:
            raise ValueError("lock retry_delay must be >= 0")

        token = os.urandom(16)
        deadline = time.monotonic() + timeout
        acquired = False
        attempts = 0
        while True:
            attempts += 1
            if self.set_if_not_exists(key, token, ttl=ttl):
                acquired = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            delay = min(retry_delay * (2 ** (attempts - 1)), remaining, 1.0)
            jitter = random.uniform(0, min(0.05, remaining))
            time.sleep(delay + jitter)

        if not acquired:
            raise KVLockTimeoutError(key=key, attempts=attempts, timeout=timeout)

        try:
            yield
        finally:
            self.delete_if_value_matches(key, token)
