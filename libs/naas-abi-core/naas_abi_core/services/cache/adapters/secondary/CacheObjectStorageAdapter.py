import hashlib
import json
from pathlib import PurePosixPath

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    ICacheAdapter,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class CacheObjectStorageAdapter(ICacheAdapter):
    def __init__(self, object_storage: ObjectStorageService, prefix: str = "cache"):
        self.object_storage = object_storage
        self.prefix = prefix.strip("/")

    @staticmethod
    def __key_to_sha256(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def __entry_prefix(self) -> str:
        return PurePosixPath(self.prefix, "entries").as_posix()

    def __entry_key(self, key: str) -> str:
        digest = self.__key_to_sha256(key)
        return f"{digest}.json"

    def __read_entry(self, key: str) -> CachedData:
        try:
            payload = self.object_storage.get_object(
                self.__entry_prefix(), self.__entry_key(key)
            )
        except Exceptions.ObjectNotFound as exc:
            raise CacheNotFoundError(f"Cache not found: {key}") from exc
        return CachedData(**json.loads(payload.decode("utf-8")))

    def get(self, key: str) -> CachedData:
        return self.__read_entry(key)

    def set(self, key: str, value: CachedData) -> None:
        payload = json.dumps(value.model_dump()).encode("utf-8")
        self.object_storage.put_object(
            self.__entry_prefix(), self.__entry_key(key), payload
        )

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        """Best-effort conditional write.

        Object storage does not expose an atomic compare-and-set primitive, so
        this method is inherently subject to a check-then-act race under
        concurrent callers.  For the embedding-cache use case this is safe:
        the cache key is derived deterministically from the file content +
        model + dimension, so two racing writers always produce identical
        content.  The last writer wins, but the result is always valid.

        Returns True if this call was the one that wrote the entry, False if
        the entry already existed at the time of the existence check.
        """
        if self.exists(key):
            return False
        self.set(key, value)
        return True

    def delete(self, key: str) -> None:
        try:
            self.object_storage.delete_object(
                self.__entry_prefix(), self.__entry_key(key)
            )
        except Exceptions.ObjectNotFound as exc:
            raise CacheNotFoundError(f"Cache not found: {key}") from exc

    def exists(self, key: str) -> bool:
        try:
            self.object_storage.get_object(self.__entry_prefix(), self.__entry_key(key))
            return True
        except Exceptions.ObjectNotFound:
            return False
