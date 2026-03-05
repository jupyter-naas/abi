# Cache Service

`CacheService` provides typed cache storage plus a decorator for function-level caching.

Related pages: [[services/Key-Value-Service]], [[Architecture]].

## Storage types

- `TEXT`
- `JSON`
- `BINARY`
- `PICKLE`

## Core methods

- `get(key, ttl=None)`
- `set_text`, `set_json`, `set_binary`, `set_pickle`
- `exists(key)`

## Decorator usage

```python
import datetime
from naas_abi_core.services.cache.CachePort import DataType

@cache_service(
    key_builder=lambda user_id: f"user:{user_id}",
    cache_type=DataType.JSON,
    ttl=datetime.timedelta(hours=1),
)
def load_user(user_id: str):
    return {"id": user_id}
```

To force bypass:

```python
load_user("123", force_cache_refresh=True)
```

## Adapter

Current built-in adapter: filesystem (`CacheFSAdapter`) via `CacheFactory.CacheFS_find_storage(...)`.
