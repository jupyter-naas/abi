# RedisAdapter

## What it is
- A Redis-backed implementation of `IKeyValueAdapter` for basic key/value operations plus key listing and TTL inspection.
- Uses `redis.Redis.from_url(...)` with `decode_responses=False` (stores/returns raw bytes).

## Public API

### Function: `glob_escape(text: str) -> str`
- Escapes Redis glob metacharacters (`\ * ? [ ]`) so a prefix can be used literally in `SCAN MATCH`.

### Class: `RedisAdapter(IKeyValueAdapter)`
- `__init__(redis_url: str, socket_timeout: float | None = None)`
  - Creates a Redis client from a URL.
  - Validates `redis_url` is non-empty.
  - Raises `ModuleNotFoundError` if `redis` package is unavailable.
- `get(key: str) -> bytes`
  - Gets a key’s value.
  - Raises `KVNotFoundError` if missing.
- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Sets a key to a value.
  - Optional `ttl` in seconds (passed as `ex`).
- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Sets only if the key does not exist (`nx=True`).
  - Returns `True` if the key was set.
- `delete(key: str) -> None`
  - Deletes a key.
  - Raises `KVNotFoundError` if missing.
- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Atomically deletes only if the current value equals the provided value (Lua script).
  - Returns `True` if deleted.
- `exists(key: str) -> bool`
  - Returns whether the key exists.
- `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> KVKeyPage`
  - Iterates keys under `prefix` using Redis `SCAN` and returns a paginated `KVKeyPage`.
  - Uses `check_page_limit(limit)` and `paginate_keys(...)`.
- `get_ttl(key: str) -> int | None`
  - Returns remaining TTL in seconds.
  - Returns `None` if key exists but has no TTL (or TTL is otherwise negative except `-2`).
  - Raises `KVNotFoundError` if Redis reports missing key (`ttl == -2`).

## Configuration/Dependencies
- Requires the `redis` Python package:
  - `pip install redis`
- Inputs:
  - `redis_url` (required): e.g. `redis://localhost:6379/0`
  - `socket_timeout` (optional): passed to `redis.Redis.from_url(...)`

## Usage
```python
from naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter import RedisAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

kv = RedisAdapter(redis_url="redis://localhost:6379/0")

kv.set("k1", b"v1", ttl=60)
assert kv.get("k1") == b"v1"

assert kv.set_if_not_exists("k1", b"v2") is False
assert kv.exists("k1") is True

assert kv.get_ttl("k1") is not None

page = kv.list_keys(prefix="k", limit=10)
print(page)

assert kv.delete_if_value_matches("k1", b"v1") is True
try:
    kv.get("k1")
except KVNotFoundError:
    pass
```

## Caveats
- `get()` and `delete()` raise `KVNotFoundError` for missing keys.
- Values may be returned by Redis as `bytes`, `str`, `bytearray`, or `memoryview`; the adapter normalizes to `bytes` (UTF-8 encoding for `str`).
- `list_keys()` performs a `SCAN` across all keys matching the prefix and then paginates in Python; it is **O(number of keys under prefix) per call** and intended for administration, not hot paths.
