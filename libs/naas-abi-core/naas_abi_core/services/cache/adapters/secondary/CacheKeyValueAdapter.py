"""Cache entries stored through the key-value service port, including NATS clients."""

import hashlib
import re

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheKeyPage,
    CacheNotFoundError,
    ICacheAdapter,
    check_page_limit,
    paginate_keys,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    MAX_KEYS_PER_PAGE,
    KVNotFoundError,
)

_DIGEST = re.compile(r"[0-9a-f]{64}")
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


class CacheKeyValueAdapter(ICacheAdapter):
    def __init__(self, keyvalue: KeyValueService, prefix: str = "cache") -> None:
        self.keyvalue = keyvalue
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{hashlib.sha256(key.encode()).hexdigest()}"

    def get(self, key: str) -> CachedData:
        try:
            return CachedData.model_validate_json(self.keyvalue.get(self._key(key)))
        except KVNotFoundError as exc:
            raise CacheNotFoundError(key) from exc

    def set(self, key: str, value: CachedData) -> None:
        self.keyvalue.set(self._key(key), value.model_dump_json().encode())

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        return self.keyvalue.set_if_not_exists(
            self._key(key), value.model_dump_json().encode()
        )

    def exists(self, key: str) -> bool:
        return self.keyvalue.exists(self._key(key))

    def delete(self, key: str) -> None:
        try:
            self.keyvalue.delete(self._key(key))
        except KVNotFoundError as exc:
            raise CacheNotFoundError(key) from exc

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        """Lists every ``<prefix>:<sha256>`` entry and reads its key: O(entries)."""
        check_page_limit(limit)
        storage_prefix = f"{self.prefix}:"
        keys: list[str] = []
        cursor: str | None = None
        while True:
            page = self.keyvalue.list_keys(
                storage_prefix, limit=MAX_KEYS_PER_PAGE, after=cursor
            )
            for stored in page.keys:
                if not _DIGEST.fullmatch(stored[len(storage_prefix) :]):
                    continue
                try:
                    keys.append(
                        CachedData.model_validate_json(self.keyvalue.get(stored)).key
                    )
                except KVNotFoundError:
                    continue  # deleted while listing
            if page.next_after is None:
                break
            cursor = page.next_after
        return paginate_keys(keys, prefix, limit, after)
