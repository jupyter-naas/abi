import hashlib
import json
import os
import re
import tempfile
import threading

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheKeyPage,
    CacheNotFoundError,
    ICacheAdapter,
    check_page_limit,
    paginate_keys,
)

# Entry files are named by the SHA-256 of their key; temp files never match.
_ENTRY_NAME = re.compile(r"[0-9a-f]{64}")
_KEY_FIELD = re.compile(r'\s*\{\s*"key"\s*:\s*')
_HEAD_BYTES = 4096


class CacheFSAdapter(ICacheAdapter):
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self._lock = threading.RLock()

        os.makedirs(self.cache_dir, exist_ok=True)

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

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        """Reads each entry's ``key`` from the head of its file (entries are
        written key first), so large values are not loaded. O(entries)."""
        check_page_limit(limit)
        with self._lock:
            names = [n for n in os.listdir(self.cache_dir) if _ENTRY_NAME.fullmatch(n)]
        keys = (self.__read_key(os.path.join(self.cache_dir, n)) for n in names)
        return paginate_keys((k for k in keys if k is not None), prefix, limit, after)

    @staticmethod
    def __read_key(path: str) -> str | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                head = f.read(_HEAD_BYTES)
                match = _KEY_FIELD.match(head)
                if match:
                    try:
                        key, _ = json.JSONDecoder().raw_decode(head, match.end())
                        if isinstance(key, str):
                            return key
                    except json.JSONDecodeError:
                        pass  # a key longer than the head: read the whole entry
                f.seek(0)
                key = json.load(f).get("key")
                return key if isinstance(key, str) else None
        except FileNotFoundError:
            return None  # deleted while listing
