from typing import Optional, cast

import redis
from naas_abi_core.services.KeyValue.KVPorts import IKVAdapter, KVNotFoundError


class RedisAdapter(IKVAdapter):
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
        socket_timeout: Optional[float] = None,
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
        value = cast(
            bytes | str | bytearray | memoryview | None, self._client.get(key)
        )
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
