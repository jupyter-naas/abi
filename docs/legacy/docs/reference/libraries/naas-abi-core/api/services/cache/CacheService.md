# CacheService

## What it is
- A cache service that:
  - Reads/writes cached values via an injected `ICacheAdapter`.
  - Serializes values as **TEXT**, **JSON**, **BINARY**, or **PICKLE**.
  - Provides a decorator (`__call__`) to cache function results with optional TTL and optional forced refresh.

## Public API

### Classes
- `CacheService(adapter: ICacheAdapter)`
  - Main service. Requires an `ICacheAdapter` implementation.

### Methods
- `__call__(key_builder: Callable, cache_type: DataType, ttl: datetime.timedelta | None = None, auto_cache: bool = True)`
  - Returns a decorator that caches the decorated function’s result.
  - Cache key is computed by `key_builder(**filtered_args)` where `filtered_args` is a subset of the decorated function’s arguments matching `key_builder`’s parameters.
  - Cache refresh:
    - If the decorated function is called with `force_cache_refresh=<anything>`, cache lookup is bypassed and the function is executed; the result is re-cached if `auto_cache=True`.
  - TTL enforcement:
    - If `ttl` is provided and cache entry is older than `created_at + ttl`, `CacheExpiredError` is treated as a miss (function executed).

- `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
  - Fetches and deserializes a cached value by key.
  - Applies TTL check if provided.

- `set_text(key: str, value: str) -> None`
  - Stores a string value as `DataType.TEXT`. Asserts `value` is `str`.

- `set_json(key: str, value: Any) -> None`
  - Stores JSON-serialized value as `DataType.JSON` (uses `json.dumps`).

- `set_binary(key: str, value: bytes) -> None`
  - Stores base64-encoded bytes as `DataType.BINARY`. Asserts `value` is `bytes`.

- `set_pickle(key: str, value: Any) -> None`
  - Stores pickled+base64-encoded value as `DataType.PICKLE`.

- `exists(key: str) -> bool`
  - Returns whether the key exists in the adapter.

## Configuration/Dependencies
- Depends on:
  - `ICacheAdapter` for persistence (`get`, `set`, `exists`).
  - `CachedData` model returned by adapter `get`, expected to include:
    - `data` (serialized string)
    - `data_type` (`DataType`)
    - `created_at` (ISO format string used by `datetime.fromisoformat`)
- Uses exceptions from `naas_abi_core.services.cache.CachePort`:
  - `CacheNotFoundError`, `CacheExpiredError`

## Usage

```python
import datetime
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.CachePort import DataType, ICacheAdapter

# You must provide an ICacheAdapter implementation.
adapter: ICacheAdapter = ...

cache = CacheService(adapter)

@cache(lambda user_id: f"user:{user_id}", cache_type=DataType.JSON, ttl=datetime.timedelta(minutes=10))
def load_user(user_id: int):
    return {"id": user_id}

# First call computes and caches
u1 = load_user(123)

# Second call returns cached value (if not expired)
u2 = load_user(123)

# Force refresh (bypasses cache lookup)
u3 = load_user(123, force_cache_refresh=True)
```

## Caveats
- `cache_type` must match the stored entry’s `data_type`; if it differs, it is treated as a cache miss and the function is executed (and may be re-cached).
- TTL is enforced using `cached_data.created_at` parsed via `datetime.fromisoformat(...)`; adapter must provide an ISO-formatted timestamp string.
- `set_text` and `set_binary` use `assert` type checks (can be disabled with Python optimization flags).
