# CacheRedisAdapter

## What it is
- A Redis-backed implementation of `ICacheAdapter`.
- Stores cache entries as JSON-serialized `CachedData` in Redis.
- Uses namespaced, hashed Redis keys: `{prefix}:{sha256(logical_key)}`.

## Public API
- `class CacheRedisAdapter(ICacheAdapter)`
  - `__init__(redis_url: str, prefix: str = "naas:cache", socket_timeout: float | None = None)`
    - Connects to Redis using `redis.Redis.from_url(...)`.
    - Normalizes `prefix` by stripping trailing `:`.
  - `get(key: str) -> CachedData`
    - Fetches and deserializes a `CachedData` entry.
    - Raises `CacheNotFoundError` if missing.
  - `set(key: str, value: CachedData) -> None`
    - Stores a `CachedData` entry (JSON).
  - `set_if_absent(key: str, value: CachedData) -> bool`
    - Atomically sets only if key does not exist (Redis `NX`).
    - Returns `True` if set, `False` otherwise.
  - `delete(key: str) -> None`
    - Deletes an entry.
    - Raises `CacheNotFoundError` if missing.
  - `exists(key: str) -> bool`
    - Checks existence of an entry.

## Configuration/Dependencies
- Requires the `redis` Python package (`import redis as redis_lib`).
- Redis connection:
  - `redis_url`: e.g. `redis://localhost:6379/0`
  - `socket_timeout`: forwarded to the Redis client
- Uses `decode_responses=True` (Redis values are returned as `str`).

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter import CacheRedisAdapter
from naas_abi_core.services.cache.CachePort import CachedData

cache = CacheRedisAdapter(redis_url="redis://localhost:6379/0", prefix="naas:cache")

key = "user:123"

value = CachedData(...)  # construct per your project's CachedData schema
cache.set(key, value)

if cache.exists(key):
    loaded = cache.get(key)
    print(loaded)

was_set = cache.set_if_absent(key, value)
print("set_if_absent:", was_set)

cache.delete(key)
```

## Caveats
- Redis keys are not the raw logical keys; they are SHA-256 hashes with a prefix. You cannot easily inspect Redis to find entries by logical key without hashing.
- `get()` and `delete()` raise `CacheNotFoundError` when the entry does not exist.
