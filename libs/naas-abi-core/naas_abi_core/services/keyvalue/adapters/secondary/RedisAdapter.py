import re
from typing import cast

import redis
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVKeyPage,
    KVNotFoundError,
    check_page_limit,
    paginate_keys,
)

# Redis MATCH is a glob: escape its metacharacters so a prefix matches literally.
_GLOB_SPECIAL = re.compile(r"([\\*?\[\]])")


def glob_escape(text: str) -> str:
    return _GLOB_SPECIAL.sub(r"\\\1", text)


class RedisAdapter(IKeyValueAdapter):
    _COMPARE_AND_DELETE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(
        self,
        redis_url: str,
        socket_timeout: float | None = None,
    ):
        if redis is None:
            raise ModuleNotFoundError(
                "redis package is required to use RedisAdapter. "
                "Install with `pip install redis`."
            )

        if not redis_url:
            raise ValueError("redis_url is required to initialize RedisAdapter.")

        self._client = redis.Redis.from_url(
            redis_url,
            socket_timeout=socket_timeout,
            decode_responses=False,
        )

    @staticmethod
    def _normalize_value(value: bytes | str | bytearray | memoryview) -> bytes:
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, memoryview):
            return value.tobytes()
        if isinstance(value, bytearray):
            return bytes(value)
        return value

    def get(self, key: str) -> bytes:
        value = cast(bytes | str | bytearray | memoryview | None, self._client.get(key))
        if value is None:
            raise KVNotFoundError(f"Key not found: {key}")
        return self._normalize_value(value)

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        normalized = self._normalize_value(value)
        self._client.set(key, normalized, ex=ttl)

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        normalized = self._normalize_value(value)
        result = self._client.set(key, normalized, nx=True, ex=ttl)
        return bool(result)

    def delete(self, key: str) -> None:
        deleted = self._client.delete(key)
        if deleted == 0:
            raise KVNotFoundError(f"Key not found: {key}")

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        normalized = self._normalize_value(value)
        result = self._client.eval(self._COMPARE_AND_DELETE_SCRIPT, 1, key, normalized)
        return bool(result)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> KVKeyPage:
        """SCAN the whole prefix (Redis has no ordered key index), then page.

        O(keys under the prefix) per call: meant for administration, not hot paths.
        Redis drops expired keys itself, so SCAN never returns them.
        """
        check_page_limit(limit)
        keys = (
            self._normalize_value(raw).decode("utf-8", "surrogateescape")
            for raw in self._client.scan_iter(
                match=f"{glob_escape(prefix)}*", count=1000
            )
        )
        return paginate_keys(keys, prefix, limit, after)

    def get_ttl(self, key: str) -> int | None:
        remaining = cast(int, self._client.ttl(key))
        if remaining == -2:
            raise KVNotFoundError(f"Key not found: {key}")
        if remaining < 0:
            return None
        return remaining
