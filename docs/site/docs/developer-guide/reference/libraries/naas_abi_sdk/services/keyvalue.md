# KeyValueService

## What it is
- An async service proxy for a remote **key-value** backend.
- Exposes basic CRUD-style operations over a `ServiceProxy` request mechanism.

## Public API
- `class KeyValueService(ServiceProxy)`
  - `domain = "keyvalue"`: Service domain identifier used by the underlying proxy.

### Methods (async)
- `get(key: str) -> bytes`
  - Fetch the raw bytes value for `key`.
- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Store `value` under `key`; optional TTL (units defined by the remote service).
- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Store only if `key` is absent; returns whether the write occurred.
- `delete(key: str) -> None`
  - Delete `key`.
- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Delete only if current value matches `value`; returns whether deletion occurred.
- `exists(key: str) -> bool`
  - Check whether `key` exists.

### Methods (sync)
- `lock(key: str, *, ttl: int = 30, timeout: float = 10.0, retry_delay: float = 0.05)`
  - Always raises `NotImplementedError`.

## Configuration/Dependencies
- Depends on `naas_abi_sdk.services._codec.ServiceProxy`.
- All operations delegate to `self._request(<operation>, ...)`, which must be provided by `ServiceProxy` and properly configured with a transport/client.

## Usage
```python
import asyncio
from naas_abi_sdk.services.keyvalue import KeyValueService

async def main():
    kv = KeyValueService()  # assumes ServiceProxy can be constructed like this

    await kv.set("greeting", b"hello", ttl=60)
    value = await kv.get("greeting")
    print(value)  # b"hello"

    print(await kv.exists("greeting"))  # True
    deleted = await kv.delete_if_value_matches("greeting", b"hello")
    print(deleted)  # True

asyncio.run(main())
```

## Caveats
- `lock(...)` is not implemented and will raise `NotImplementedError`.
- `ttl` semantics (units/behavior) are not defined here; they are determined by the remote key-value service implementation.
