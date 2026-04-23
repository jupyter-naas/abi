# CachePort

## What it is
Interface (port) definitions for a cache layer:
- Typed cache payload model (`CachedData`) and supported data types (`DataType`)
- Adapter interface (`ICacheAdapter`) for storage backends
- Service interface (`ICacheService`) for higher-level cache operations
- Cache-related exceptions (`CacheNotFoundError`, `CacheExpiredError`)

## Public API

### Exceptions
- `CacheNotFoundError`: Error type intended for missing cache entries.
- `CacheExpiredError`: Error type intended for expired cache entries.

### Enums
- `DataType(str, Enum)`
  - Values: `TEXT`, `JSON`, `BINARY`, `PICKLE`
  - Purpose: identifies how cached data should be interpreted/serialized.

### Models
- `CachedData(BaseModel)`
  - Fields:
    - `key: str`
    - `data: Any`
    - `data_type: DataType`
    - `created_at: str` (defaults to current time in ISO format)
  - Purpose: structured cache entry container.

### Interfaces
- `ICacheAdapter`
  - `get(key: str) -> CachedData`: retrieve a cached entry.
  - `set(key: str, value: CachedData) -> None`: store/overwrite a cached entry.
  - `set_if_absent(key: str, value: CachedData) -> bool`: store only if key is not present.
  - `delete(key: str) -> None`: remove an entry.
  - `exists(key: str) -> bool`: check presence.

- `ICacheService`
  - Constructor: `__init__(adapter: ICacheAdapter)`
  - `exists(key: str) -> bool`
  - `delete(key: str) -> None`
  - `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
  - `set_text(key: str, value: str) -> None`
  - `set_json(key: str, value: dict) -> None`
  - `set_binary(key: str, value: bytes) -> None`
  - `set_pickle(key: str, value: Any) -> None`
  - `set_json_if_absent(key: str, value: dict) -> bool`
  - `set_binary_if_absent(key: str, value: bytes) -> bool`
  - Purpose: defines the cache operations expected from a service; methods are not implemented here.

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`
  - Standard library: `datetime`, `enum`, `typing.Any`

No runtime configuration is defined in this file.

## Usage

### Create a `CachedData` instance
```python
from naas_abi_core.services.cache.CachePort import CachedData, DataType

entry = CachedData(key="k1", data={"a": 1}, data_type=DataType.JSON)
print(entry.key, entry.data_type, entry.created_at)
```

### Implement an adapter (example skeleton)
```python
from naas_abi_core.services.cache.CachePort import ICacheAdapter, CachedData

class InMemoryAdapter(ICacheAdapter):
    def __init__(self):
        self._store = {}

    def get(self, key: str) -> CachedData:
        return self._store[key]

    def set(self, key: str, value: CachedData) -> None:
        self._store[key] = value

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        if key in self._store:
            return False
        self._store[key] = value
        return True

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._store
```

## Caveats
- `ICacheAdapter` and `ICacheService` are interfaces with `NotImplementedError` methods; concrete implementations must provide behavior (including how/when to raise `CacheNotFoundError` / `CacheExpiredError`).
- `CachedData.created_at` is stored as a string (ISO format), not a `datetime` object.
