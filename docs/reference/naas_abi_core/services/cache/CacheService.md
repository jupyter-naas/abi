# CacheService

## What it is
A multi-tier cache service providing:
- **Hot** tier (fast/volatile) and **cold** tier (durable/slower) semantics.
- A **top-level** orchestrator (`CacheService`) that reads **hot → cold** (no promotion) and writes to **cold only** by default.
- **Tier-scoped** operations via `SingleTierCacheService` (exposed as `cache.hot`, `cache.cold`, or `cache.tier(name)`).

## Public API

### `class CacheService(ServiceBase, ICacheService)`
Multi-tier orchestrator over an ordered list of `(tier_name, ICacheAdapter)`.

- `__init__(adapters: list[tuple[str, ICacheAdapter]])`
  - Requires at least one adapter; stores tier registry in read order.

- `adapters -> tuple[tuple[str, ICacheAdapter], ...]` (property)
  - Read-only view of configured adapters.

- Tier access:
  - `hot -> SingleTierCacheService` (property): hot-tier view; raises `ValueError` if not configured.
  - `cold -> SingleTierCacheService` (property): cold-tier view; if no `"cold"` tier is configured, uses the **last adapter** as cold (creates a new `SingleTierCacheService` wrapper).
  - `hot_available() -> bool`: whether a hot tier exists.
  - `tier_names -> tuple[str, ...]` (property): configured tier names in order.
  - `tier(name: str) -> SingleTierCacheService`: view of a configured tier by name.

- Decorator:
  - `__call__(key_builder, cache_type: DataType, ttl: datetime.timedelta | None = None, auto_cache: bool = True)`
    - Returns a decorator that caches function results into the **cold** tier.

- Reads (fall-through; no promotion):
  - `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
    - Tries tiers in order; treats non-cache exceptions as warnings and falls through.
    - Raises `CacheNotFoundError` if missing in all tiers.
  - `get_entry(key: str) -> CacheEntry`
    - Returns the first tier’s raw stored entry (no deserialization, no TTL check).
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`
    - Merges keys across tiers, deduplicated and sorted, limited to `limit`.
  - `exists(key: str) -> bool`
    - Checks tiers in order; warnings on tier errors, treated as misses.

- Writes (cold only at top level):
  - `delete(key: str) -> None`: deletes from **all configured tiers**; ignores errors/missing keys.
  - `set_text(key: str, value: str) -> None`
  - `set_json(key: str, value: Any) -> None`
  - `set_json_if_absent(key: str, value: Any) -> bool`
  - `set_binary(key: str, value: bytes) -> None`
  - `set_binary_if_absent(key: str, value: bytes) -> bool`
  - `set_pickle(key: str, value: Any) -> None`

- Engine wiring:
  - `set_services(services: IEngine.Services) -> None`
    - Calls `adapter.wire_services(services)` when the adapter defines it.
    - Enables event publication if `services.events` is available.

---

### `class SingleTierCacheService`
Tier-scoped wrapper over a single `ICacheAdapter`. Typically obtained from `CacheService.hot`, `CacheService.cold`, or `CacheService.tier(name)`.

- `__call__(key_builder, cache_type: DataType, ttl: datetime.timedelta | None = None, auto_cache: bool = True)`
  - Decorator caching function results into **this tier**.
  - If kwarg `force_cache_refresh` is present, bypasses cached value and recomputes.
  - Cached value is used only if `cached_data.data_type == cache_type`; otherwise treated as a miss.

- Reads:
  - `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
    - Deserializes by stored `DataType` (`TEXT`, `JSON`, `BINARY`, `PICKLE`).
    - If `ttl` provided, uses `CachedData.created_at` (ISO string) to enforce expiration; naive timestamps are treated as UTC.
  - `exists(key: str) -> bool`
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`
  - `get_entry(key: str) -> CacheEntry`
    - Raw stored entry (no deserialization, no TTL check), tagged with tier name.

- Writes:
  - `delete(key: str) -> None`
  - `set_text(key: str, value: str) -> None` (asserts `value` is `str`)
  - `set_json(key: str, value: Any) -> None` (stored as JSON string)
  - `set_json_if_absent(key: str, value: Any) -> bool`
  - `set_binary(key: str, value: bytes) -> None` (asserts `bytes`, stored as base64 string)
  - `set_binary_if_absent(key: str, value: bytes) -> bool`
  - `set_pickle(key: str, value: Any) -> None` (stored as base64(pickle))

## Configuration/Dependencies
- Requires one or more `ICacheAdapter` implementations (from `naas_abi_core.services.cache.CachePort`).
- Uses cache port types/exceptions:
  - `CachedData`, `CacheEntry`, `CacheKeyPage`, `DataType`
  - `CacheNotFoundError`, `CacheExpiredError`
  - `check_page_limit`
- Event ontology (emitted on tier mutations when engine events are available):
  - `CacheSet`, `CacheDeleted`, `CacheError`
- Logging via `naas_abi_core.logger`.

## Usage

### Minimal example (single cold tier + decorator)
```python
import datetime
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.CachePort import DataType

# Provide an adapter implementing ICacheAdapter (not shown here).
cache = CacheService(adapters=[("cold", cold_adapter)])

cache.set_json("k1", {"a": 1})
print(cache.get("k1"))

@cache(lambda x: f"square:{x}", cache_type=DataType.JSON, ttl=datetime.timedelta(minutes=5))
def square(x: int):
    return {"x": x, "x2": x * x}

print(square(3))
```

### Two tiers and explicit tier targeting
```python
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.CachePort import DataType

cache = CacheService(adapters=[("hot", hot_adapter), ("cold", cold_adapter)])

@cache.hot(lambda user_id: f"user:{user_id}", cache_type=DataType.JSON)
def user_meta(user_id: str):
    return {"id": user_id}
```

## Caveats
- **No automatic promotion**: `CacheService.get()` returning from cold does not populate hot.
- Top-level `set_*` writes go to **cold only**; write to hot via `cache.hot.set_*`.
- Tier failures during `get/exists/list_keys/get_entry` are **logged and treated as fall-through/miss**, which can mask transient outages.
- Pickle deserialization (`pickle.loads`) is used for `DataType.PICKLE`; do not use with untrusted data.
