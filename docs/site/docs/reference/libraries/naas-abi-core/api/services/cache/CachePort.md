# CachePort

## What it is
- A small “port” module defining cache domain types and interfaces:
  - Exceptions for cache misses/expiry
  - A `CachedData` Pydantic model describing stored entries
  - Interfaces (`ICacheAdapter`, `ICacheService`) to be implemented by concrete cache adapters/services

## Public API

### Exceptions
- `CacheNotFoundError`
  - Raised by implementations when a key is missing.
- `CacheExpiredError`
  - Raised by implementations when an entry is expired (typically when TTL is enforced).

### Enums
- `DataType (Enum[str])`
  - Supported data type labels for cached values:
    - `TEXT`, `JSON`, `BINARY`, `PICKLE`

### Models
- `CachedData (pydantic.BaseModel)`
  - Represents a cached entry.
  - Fields:
    - `key: str`
    - `data: Any`
    - `data_type: DataType`
    - `created_at: str` (ISO timestamp; defaults to `datetime.datetime.now().isoformat()`)

### Interfaces
- `ICacheAdapter`
  - Low-level storage contract.
  - Methods (all raise `NotImplementedError` here):
    - `get(key: str) -> CachedData`
    - `set(key: str, value: CachedData) -> None`
    - `delete(key: str) -> None`
    - `exists(key: str) -> bool`

- `ICacheService`
  - Higher-level cache service contract built on an adapter.
  - Attributes:
    - `adapter: ICacheAdapter`
  - Constructor:
    - `__init__(adapter: ICacheAdapter)` stores the adapter.
  - Methods (all raise `NotImplementedError` here):
    - `exists(key: str) -> bool`
    - `get(key: str, ttl: datetime.timedelta | None = None) -> Any`
    - `set_text(key: str, value: str) -> None`
    - `set_json(key: str, value: dict) -> None`
    - `set_binary(key: str, value: bytes) -> None`
    - `set_pickle(key: str, value: Any) -> None`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (`BaseModel`, `Field`)
  - Standard library: `datetime`, `enum`, `typing.Any`
- No runtime configuration is defined in this module.

## Usage

This file defines interfaces; you must implement them to use caching.

```python
import datetime
from naas_abi_core.services.cache.CachePort import (
    ICacheAdapter, ICacheService, CachedData, DataType, CacheNotFoundError
)

class InMemoryAdapter(ICacheAdapter):
    def __init__(self):
        self._store = {}

    def get(self, key: str) -> CachedData:
        if key not in self._store:
            raise CacheNotFoundError(key)
        return self._store[key]

    def set(self, key: str, value: CachedData) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._store

class SimpleCacheService(ICacheService):
    def exists(self, key: str) -> bool:
        return self.adapter.exists(key)

    def get(self, key: str, ttl: datetime.timedelta | None = None):
        return self.adapter.get(key).data

    def set_text(self, key: str, value: str) -> None:
        self.adapter.set(key, CachedData(key=key, data=value, data_type=DataType.TEXT))

adapter = InMemoryAdapter()
cache = SimpleCacheService(adapter)

cache.set_text("greeting", "hello")
print(cache.get("greeting"))
```

## Caveats
- `ICacheAdapter` and `ICacheService` are not `abc.ABC`; they only raise `NotImplementedError`. Implementations must provide behavior.
- TTL/expiry semantics are not implemented here; `ttl` is only part of the `ICacheService.get` interface.
- `CachedData.created_at` is stored as a string timestamp (ISO format), not a `datetime` object.
