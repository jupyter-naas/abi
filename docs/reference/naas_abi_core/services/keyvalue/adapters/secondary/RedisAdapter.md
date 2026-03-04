# RedisAdapter

## What it is
- A Redis-backed implementation of `IKeyValueAdapter` for basic key/value operations.
- Stores and returns raw bytes (`decode_responses=False`) and normalizes returned Redis values into `bytes`.

## Public API
- `class RedisAdapter(IKeyValueAdapter)`
  - `__init__(redis_url: str, socket_timeout: Optional[float] = None)`
    - Creates a Redis client from a URL.
  - `get(key: str) -> bytes`
    - Fetches a value by key.
    - Raises `KVNotFoundError` if the key does not exist.
  - `set(key: str, value: bytes, ttl: int | None = None) -> None`
    - Sets a key to a value with optional TTL (seconds).
  - `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
    - Sets a key only if it does not already exist; returns `True` if set.
  - `delete(key: str) -> None`
    - Deletes a key.
    - Raises `KVNotFoundError` if the key does not exist.
  - `delete_if_value_matches(key: str, value: bytes) -> bool`
    - Atomically deletes a key only if its current value matches; returns `True` if deleted.
  - `exists(key: str) -> bool`
    - Checks if a key exists.

## Configuration/Dependencies
- Requires the `redis` Python package:
  - Install: `pip install redis`
- Constructor parameters:
  - `redis_url`: required; passed to `redis.Redis.from_url(...)`.
  - `socket_timeout`: optional float; forwarded to the Redis client.
- Uses `decode_responses=False` (values handled as bytes-like, then normalized to `bytes`).

## Usage
```python
from naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter import RedisAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

kv = RedisAdapter(redis_url="redis://localhost:6379/0")

kv.set("k1", b"v1", ttl=60)
assert kv.get("k1") == b"v1"

created = kv.set_if_not_exists("k1", b"v2")
assert created is False

deleted = kv.delete_if_value_matches("k1", b"v1")
assert deleted is True
assert kv.exists("k1") is False

try:
    kv.get("k1")
except KVNotFoundError:
    pass
```

## Caveats
- `get()` and `delete()` raise `KVNotFoundError` when the key is missing.
- Values are normalized to `bytes`; passing `str`, `bytearray`, or `memoryview` is accepted internally via normalization.
