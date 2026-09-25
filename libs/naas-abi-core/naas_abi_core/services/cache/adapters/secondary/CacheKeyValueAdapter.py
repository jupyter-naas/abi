"""Cache entries stored through the key-value service port, including NATS clients."""

import hashlib

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    ICacheAdapter,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError
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
