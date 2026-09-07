# TTLCache

## What it is
- A generic in-memory cache with a time-to-live (TTL) per entry.
- Async-safe (`asyncio.Lock`) and designed for `async` fetch functions.
- Supports serving stale data when a refresh fails.

## Public API
- `class TTLCache(Generic[T])`
  - `__init__(ttl_seconds: int, max_size: int = 1000) -> None`
    - Create a cache with TTL (seconds) and a maximum number of stored keys.
  - `async get_or_fetch(key: str, fetch: Callable[[], Awaitable[T]]) -> T`
    - Return a cached value if fresh; otherwise call `fetch()` to refresh.
    - If `fetch()` raises:
      - returns the existing cached (stale) value if present
      - otherwise re-raises the exception
  - `get_stale(key: str) -> T | None`
    - Return the cached value regardless of TTL, or `None` if missing.

## Configuration/Dependencies
- Standard library only:
  - `asyncio` (lock for async safety)
  - `time.monotonic()` (TTL timing)
- Parameters:
  - `ttl_seconds`: entry freshness window.
  - `max_size`: max number of entries; when exceeded, evicts the single oldest entry.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.core.cache import TTLCache

cache: TTLCache[int] = TTLCache(ttl_seconds=30, max_size=100)

async def fetch_value() -> int:
    # Replace with real I/O
    await asyncio.sleep(0.1)
    return 42

async def main():
    v1 = await cache.get_or_fetch("answer", fetch_value)
    v2 = await cache.get_or_fetch("answer", fetch_value)  # likely cached within TTL
    print(v1, v2)

asyncio.run(main())
```

## Caveats
- Freshness is only checked inside `get_or_fetch`; `get_stale` does not enforce TTL.
- `get_or_fetch` releases the lock before running `fetch()`, so concurrent callers may trigger multiple fetches for the same key.
- Eviction policy removes only one oldest entry when `max_size` is exceeded.
