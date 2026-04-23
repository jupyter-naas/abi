import hashlib
import json
import os
import tempfile
import threading

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    ICacheAdapter,
)


class CacheFSAdapter(ICacheAdapter):
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self._lock = threading.RLock()

        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def __entry_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, self.__key_to_sha256(key))

    def __key_to_sha256(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, key: str) -> CachedData:
        path = self.__entry_path(key)
        with self._lock:
            if not os.path.exists(path):
                raise CacheNotFoundError(f"Cache file not found: {key}")

            with open(path, "r", encoding="utf-8") as f:
                return CachedData(**json.load(f))

    def set(self, key: str, value: CachedData) -> None:
        path = self.__entry_path(key)
        payload = json.dumps(value.model_dump(), indent=4)
        with self._lock:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.cache_dir,
                delete=False,
            ) as temp_file:
                temp_file.write(payload)
                temp_path = temp_file.name
            os.replace(temp_path, path)

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        path = self.__entry_path(key)
        payload = json.dumps(value.model_dump(), indent=4)
        with self._lock:
            if os.path.exists(path):
                return False
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.cache_dir,
                delete=False,
            ) as temp_file:
                temp_file.write(payload)
                temp_path = temp_file.name
            os.replace(temp_path, path)
            return True

    def delete(self, key: str) -> None:
        path = self.__entry_path(key)
        with self._lock:
            if not os.path.exists(path):
                raise CacheNotFoundError(f"Cache file not found: {key}")
            os.remove(path)

    def exists(self, key: str) -> bool:
        path = self.__entry_path(key)
        with self._lock:
            return os.path.exists(path)
