# CacheRedisAdapter

## What it is
- A Redis-backed implementation of `ICacheAdapter`.
- Stores cache entries as JSON-serialized `CachedData` values in Redis.
- Uses namespaced, hashed Redis keys: `{prefix}:{sha256(logical_key)}`.

## Public API
- `class CacheRedisAdapter(ICacheAdapter)`
  - `__init__(redis_url: str, prefix: str = "naas:cache", socket_timeout: float | None = None) -> None`
    - Creates a Redis client via `redis.Redis.from_url(...)`.
    - Normalizes `prefix` by stripping trailing `:`.
  - `get(key: str) -> CachedData`
    - Loads and deserializes a cached entry.
    - Raises `CacheNotFoundError` if missing.
  - `set(key: str, value: CachedData) -> None`
    - Writes a cached entry (JSON from `value.model_dump()`).
  - `set_if_absent(key: str, value: CachedData) -> bool`
    - Atomic “set only if not exists” using Redis `SET ... NX`.
    - Returns `True` if written, `False` if it already existed.
  - `delete(key: str) -> None`
    - Deletes an entry.
    - Raises `CacheNotFoundError` if missing.
  - `exists(key: str) -> bool`
    - Returns whether an entry exists.
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`
    - SCANs the adapter’s namespace and returns logical keys from stored values.
    - Paginates results via `paginate_keys(...)` and validates `limit` via `check_page_limit(...)`.

## Configuration/Dependencies
- Python package dependency: `redis` (imported as `redis as redis_lib`).
- Redis client configuration:
  - `redis_url`: e.g. `redis://localhost:6379/0`
  - `socket_timeout`: forwarded to the Redis client
  - Uses `decode_responses=True` (Redis values returned as `str`)
- Relies on project types/utilities from `naas_abi_core.services.cache.CachePort`:
  - `CachedData`, `CacheKeyPage`, `CacheNotFoundError`, `ICacheAdapter`
  - `check_page_limit`, `paginate_keys`

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter import CacheRedisAdapter
from naas_abi_core.services.cache.CachePort import CachedData

cache = CacheRedisAdapter(redis_url="redis://localhost:6379/0", prefix="naas:cache")

key = "user:123"
value = CachedData(key=key, value={"name": "Ada"})  # fields depend on CachedData definition

cache.set(key, value)

loaded = cache.get(key)
print(loaded)

print(cache.exists(key))  # True

print(cache.set_if_absent(key, value))  # False if already present

page = cache.list_keys(prefix="user:", limit=50)
print(page)

cache.delete(key)
```

## Caveats
- Redis keys are **hashed** (SHA-256) and prefixed; you cannot directly find entries in Redis by the logical key without hashing.
- `get()` and `delete()` raise `CacheNotFoundError` when the logical key is not present.
- `list_keys()` is effectively **O(number of entries)** in the namespace: it SCANs stored keys, then `MGET`s values in batches and extracts the logical `"key"` field from each JSON value.
