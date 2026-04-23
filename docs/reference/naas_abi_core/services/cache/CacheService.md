# CacheService

## What it is
A **multi-tier cache service** with explicit **hot** (fast/volatile) and **cold** (durable/slower) tiers, plus a single-tier view for tier-scoped operations. Reads can fall through tiers; writes on the top-level service target **cold only** by default.

Key semantics:
- `CacheService.get(key)`: hot → cold, **no automatic promotion**
- `CacheService.exists(key)`: checks any tier, hot first
- `CacheService.set_*`: **cold only**
- `CacheService.delete(key)`: deletes from **all configured tiers**
- Decorator (`__call__`): caches in **cold** by default; use `cache.hot(...)` / `cache.cold(...)` for explicit tier

---

## Public API

### `class CacheService(ServiceBase, ICacheService)`
Multi-tier orchestrator over an ordered list of `(tier_name, adapter)`.

- `__init__(adapters: list[tuple[str, ICacheAdapter]])`
  - Requires at least one adapter.
- `hot -> SingleTierCacheService` (property)
  - Access hot tier; raises `ValueError` if not configured.
- `cold -> SingleTierCacheService` (property)
  - Access cold tier; if no `"cold"` tier is explicitly configured, uses the **last adapter** as cold (backward compatible).
- `hot_available() -> bool`
  - Whether a hot tier is configured.
- `__call__(key_builder, cache_type, ttl=None, auto_cache=True)`
  - Decorator that caches results into the **cold** tier.
- `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
  - Read-through across tiers (hot first). Logs warnings and falls through on tier failures.
  - Raises `CacheNotFoundError` if missing in all tiers.
- `exists(key: str) -> bool`
  - True if present in any tier; tier failures are logged and treated as misses.
- `delete(key: str) -> None`
  - Deletes from all configured tiers; ignores errors.
- Cold-tier writes (top-level convenience methods):
  - `set_text(key: str, value: str) -> None`
  - `set_json(key: str, value: Any) -> None`
  - `set_json_if_absent(key: str, value: Any) -> bool`
  - `set_binary(key: str, value: bytes) -> None`
  - `set_binary_if_absent(key: str, value: bytes) -> bool`
  - `set_pickle(key: str, value: Any) -> None`
- `set_services(services: IEngine.Services) -> None`
  - Calls `wire_services(services)` on adapters that implement it.

### `class SingleTierCacheService`
A tier-scoped API wrapping a single `ICacheAdapter`. Exposed via `CacheService.hot` and `CacheService.cold`.

- `__call__(key_builder, cache_type, ttl=None, auto_cache=True)`
  - Decorator caching function results **in this tier**.
  - Special kwarg: if `force_cache_refresh` is present, cached value is bypassed.
- `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
  - Reads and deserializes based on stored `DataType`; TTL is enforced using `created_at`.
- `exists(key: str) -> bool`
- `delete(key: str) -> None`
- Writers:
  - `set_text(key: str, value: str) -> None`
  - `set_json(key: str, value: Any) -> None`
  - `set_json_if_absent(key: str, value: Any) -> bool` (falls back if adapter lacks `set_if_absent`)
  - `set_binary(key: str, value: bytes) -> None` (base64-encoded)
  - `set_binary_if_absent(key: str, value: bytes) -> bool` (falls back if adapter lacks `set_if_absent`)
  - `set_pickle(key: str, value: Any) -> None` (pickle + base64)

---

## Configuration/Dependencies
- Requires one or more `ICacheAdapter` implementations.
- Uses types/exceptions from `naas_abi_core.services.cache.CachePort`:
  - `CachedData`, `DataType`, `CacheNotFoundError`, `CacheExpiredError`
- TTL behavior depends on `CachedData.created_at` being an ISO-format datetime string (`datetime.fromisoformat` is used).
- Logging via `naas_abi_core.logger`.
- Optional adapter hook: `adapter.wire_services(services)` is called if present.

---

## Usage

### Basic (single cold tier)
```python
import datetime
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.CachePort import DataType

# fs_adapter must implement ICacheAdapter
cache = CacheService(adapters=[("cold", fs_adapter)])

cache.set_json("k1", {"a": 1})
print(cache.get("k1"))

@cache(lambda x: f"square:{x}", cache_type=DataType.JSON, ttl=datetime.timedelta(minutes=5))
def compute(x):
    return {"x": x, "x2": x * x}

print(compute(3))
```

### Two tiers (hot + cold) and explicit tier targeting
```python
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.CachePort import DataType

cache = CacheService(adapters=[("hot", redis_adapter), ("cold", fs_adapter)])

@cache.hot(lambda user_id: f"user-meta:{user_id}", cache_type=DataType.JSON)
def user_meta(user_id):
    return {"id": user_id}

@cache.cold(lambda doc_id: f"doc:{doc_id}", cache_type=DataType.TEXT)
def load_doc(doc_id):
    return "content"
```

---

## Caveats
- **No automatic promotion**: a `CacheService.get()` hit in cold does not populate hot.
- Top-level `set_*` methods write to **cold only**; write to hot explicitly via `cache.hot.set_*`.
- Tier failures during `get()` / `exists()` are **logged and treated as misses**, potentially masking transient adapter errors.
- `set_pickle()` uses `pickle.loads(...)` on read in the decorator path; only use with trusted data sources.
