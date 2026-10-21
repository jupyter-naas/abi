# CachePort

## What it is
Interface (port) definitions and small utilities for a cache layer:
- Typed cache payload model (`CachedData`) and supported data types (`DataType`)
- Paging models for key enumeration (`CacheKeyPage`) and raw entry access (`CacheEntry`)
- Helper functions for key pagination (`paginate_keys`, `check_page_limit`)
- Adapter interface (`ICacheAdapter`) for storage backends
- Service interface (`ICacheService`) for higher-level cache operations
- Cache-related exceptions (`CacheNotFoundError`, `CacheExpiredError`)

## Public API

### Exceptions
- `CacheNotFoundError`: intended for missing cache entries.
- `CacheExpiredError`: intended for expired cache entries.

### Constants
- `MAX_KEYS_PER_PAGE: int = 1000`: upper bound for one `list_keys` page.

### Enums
- `DataType(str, Enum)`
  - Values: `TEXT`, `JSON`, `BINARY`, `PICKLE`
  - Purpose: identifies how cached data is represented/serialized.

### Models / Data containers
- `CachedData(pydantic.BaseModel)`
  - Fields:
    - `key: str`
    - `data: Any`
    - `data_type: DataType`
    - `created_at: str` (default: current UTC time in ISO 8601 format)
  - Purpose: structured cache entry payload.

- `CacheKeyPage(dataclasses.dataclass, frozen=True)`
  - Fields:
    - `keys: tuple[str, ...]` (ascending order)
    - `next_after: str | None` (the last key in this page if more results exist)
  - Purpose: paging structure for key listings.

- `CacheEntry(dataclasses.dataclass, frozen=True)`
  - Fields:
    - `tier: str`
    - `cached: CachedData`
  - Purpose: represents a stored entry “as-is” (never deserialized) plus the tier holding it.

### Functions
- `check_page_limit(limit: int) -> None`
  - Validates `limit` is within `1..MAX_KEYS_PER_PAGE`; raises `ValueError` otherwise.

- `paginate_keys(keys: Iterable[str], prefix: str, limit: int, after: str | None) -> CacheKeyPage`
  - Filters by `prefix`, applies “strictly after” cursor (`after`), deduplicates, sorts ascending, returns one page and `next_after` cursor when more exist.

### Interfaces
- `ICacheAdapter`
  - `get(key: str) -> CachedData`: retrieve a cached entry.
  - `set(key: str, value: CachedData) -> None`: store/overwrite a cached entry.
  - `set_if_absent(key: str, value: CachedData) -> bool`: store only if key is not present.
  - `delete(key: str) -> None`: remove an entry.
  - `exists(key: str) -> bool`: check presence.
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`:
    list logical keys starting with `prefix`, strictly after `after`, ascending, up to `limit`.

- `ICacheService`
  - `__init__(adapter: ICacheAdapter)`: stores `adapter`.
  - `exists(key: str) -> bool`
  - `delete(key: str) -> None`
  - `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
  - `set_text(key: str, value: str) -> None`
  - `set_json(key: str, value: dict) -> None`
  - `set_binary(key: str, value: bytes) -> None`
  - `set_pickle(key: str, value: Any) -> None`
  - `set_json_if_absent(key: str, value: dict) -> bool`
  - `set_binary_if_absent(key: str, value: bytes) -> bool`
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`
  - `get_entry(key: str) -> CacheEntry`
  - Note: all methods raise `NotImplementedError` in this file.

## Configuration/Dependencies
- Dependencies:
  - `pydantic.BaseModel`, `pydantic.Field`
  - Standard library: `datetime`, `dataclasses`, `enum`, `typing.Any`, `collections.abc.Iterable`
- No runtime configuration is defined here.

## Usage

### Create a `CachedData` instance
```python
from naas_abi_core.services.cache.CachePort import CachedData, DataType

entry = CachedData(key="k1", data={"a": 1}, data_type=DataType.JSON)
print(entry.key, entry.data_type, entry.created_at)
```

### Paginate a set of keys
```python
from naas_abi_core.services.cache.CachePort import paginate_keys

keys = ["a/1", "a/2", "b/1", "a/2"]  # duplicates allowed
page1 = paginate_keys(keys, prefix="a/", limit=1, after=None)
page2 = paginate_keys(keys, prefix="a/", limit=1, after=page1.next_after)

print(page1.keys, page1.next_after)
print(page2.keys, page2.next_after)
```

## Caveats
- `ICacheAdapter` and `ICacheService` are interfaces only; concrete implementations must provide behavior (including if/when to raise `CacheNotFoundError` / `CacheExpiredError`).
- `CachedData.created_at` is stored as a string (ISO format), not a `datetime` object.
- `paginate_keys` deduplicates keys (set semantics) and sorts them; returned pages are always ascending.
