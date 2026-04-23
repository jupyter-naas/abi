# Key Value Service

`KeyValueService` exposes simple key-value operations with optional TTL and conditional semantics.

## Core API

- `get(key) -> bytes`
- `set(key, value, ttl=None)`
- `set_if_not_exists(key, value, ttl=None) -> bool`
- `delete(key)`
- `delete_if_value_matches(key, value) -> bool`
- `exists(key) -> bool`

## Adapter options

- `python`: in-memory dict adapter with TTL support.
- `redis`: Redis adapter.
- `custom`: pluggable adapter.

## Config example

```yaml
services:
  kv:
    kv_adapter:
      adapter: "redis"
      config:
        redis_url: "redis://localhost:6379"
```
