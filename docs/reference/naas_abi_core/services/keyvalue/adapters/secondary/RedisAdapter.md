# RedisAdapter

## What it is
- A Redis-backed implementation of `IKeyValueAdapter` for basic key/value operations.
- Uses `redis.Redis.from_url(...)` and stores values as raw bytes (`decode_responses=False`).

## Public API
### Class: `RedisAdapter(IKeyValueAdapter)`
- `__init__(redis_url: str, socket_timeout: Optional[float] = None)`
  - Creates a Redis client from the provided URL.
  - Validates that `redis_url` is non-empty.
- `get(key: str) -> bytes`
  - Fetches a key; raises `KVNotFoundError` if missing.
- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Sets a key to a value, optionally with TTL (seconds).
- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Sets only if the key does not already exist (`NX`); returns `True` if set.
- `delete(key: str) -> None`
  - Deletes a key; raises `KVNotFoundError` if missing.
- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Atomically deletes the key only if its current value matches; returns `True` if deleted.
- `exists(key: str) -> bool`
  - Returns whether the key exists.

## Configuration/Dependencies
- Requires the `redis` Python package:
  - `pip install redis`
- Inputs:
  - `redis_url` (required): Redis connection URL (e.g., `redis://localhost:6379/0`)
  - `socket_timeout` (optional): passed to the Redis client.

## Usage
```python
from naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter import RedisAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

kv = RedisAdapter(redis_url="redis://localhost:6379/0")

kv.set("k1", b"v1", ttl=60)
assert kv.get("k1") == b"v1"

created = kv.set_if_not_exists("k1", b"v2")
assert created is False

assert kv.exists("k1") is True
deleted = kv.delete_if_value_matches("k1", b"v1")
assert deleted is True

try:
    kv.get("k1")
except KVNotFoundError:
    pass
```

## Caveats
- Missing keys in `get()` and `delete()` raise `KVNotFoundError`.
- Values are normalized to bytes; strings are encoded as UTF-8 before storage/comparison.
- `delete_if_value_matches()` uses a Lua script for atomic compare-and-delete.
