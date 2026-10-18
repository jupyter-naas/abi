# CacheService

## What it is
- Async client-side wrapper around the Naas ABI cache RPC service.
- Supports multiple cache tiers (“hot”/“cold”) and basic data types: text, JSON, binary.
- Provides tier selection via `.hot` / `.cold` views.

## Public API
- `class CacheService(client, selector: str | None = None)`
  - `hot -> CacheService`: view restricted to the `"hot"` tier.
  - `cold -> CacheService`: view restricted to the `"cold"` tier.
  - `hot_available() -> bool`: returns whether a `"hot"` tier is configured server-side.
  - `get(key: str, ttl: timedelta | None = None) -> Any`
    - Fetches a value across tiers (when unselected) and deserializes based on stored type:
      - text → `str`
      - json → decoded Python object
      - binary → `bytes` (base64 decoded)
    - Optional client-side TTL check using the stored `created_at` timestamp.
  - `exists(key: str) -> bool`: checks existence across tiers (when unselected).
  - `delete(key: str) -> None`: deletes key across tiers; ignores not-found errors.
  - `set_text(key: str, value: str) -> None`: stores a text value.
  - `set_json(key: str, value: Any) -> None`: stores JSON-encoded data.
  - `set_binary(key: str, value: bytes) -> None`: stores binary data (base64 encoded).
  - `set_json_if_absent(key: str, value: Any) -> bool`: sets JSON only if missing; returns success.
  - `set_binary_if_absent(key: str, value: bytes) -> bool`: sets binary only if missing; returns success.
  - `set_pickle(key: str, value: Any) -> None`: **not implemented** (raises `NotImplementedError`).
  - `__call__(*args, **kwargs)`: **not implemented** (decorator support not available; raises `NotImplementedError`).

## Configuration/Dependencies
- Requires an RPC `client` that provides:
  - `describe(...)`, `get(...)`, `exists(...)`, `delete(...)`, `set(...)`, `set_if_absent(...)`
  - `tier(i)` to select a tier-specific client
- Uses protobuf messages from `naas_abi_proto.cache.v1.cache_pb2`.
- Error mapping:
  - RPC failures raise `naas_abi_sdk.transport.RPCError`, converted via `domain_error`.
  - May raise `CacheNotFoundError` / `CacheExpiredError`.

## Usage
```python
import asyncio
from datetime import timedelta

from naas_abi_sdk.services.cache import CacheService

async def main(client):
    cache = CacheService(client)

    await cache.set_json("cfg", {"a": 1})
    print(await cache.get("cfg"))  # -> {'a': 1}

    # Select a specific tier
    if await cache.hot_available():
        await cache.hot.set_text("k", "v")
        print(await cache.hot.get("k"))

    # Client-side TTL check (based on server-stored created_at)
    try:
        await cache.get("cfg", ttl=timedelta(seconds=1))
    except Exception as e:
        print("TTL/lookup error:", e)

asyncio.run(main(client))  # 'client' must be provided by your transport layer
```

## Caveats
- Remote pickle serialization/deserialization is not supported (`set_pickle` and pickle reads raise `NotImplementedError`).
- Decorator-style caching via calling the service is not supported in the async SDK (`__call__` raises `NotImplementedError`).
- If no tiers are configured:
  - `.hot` operations may raise `ValueError("No hot cache tier configured")`.
- `ttl` enforcement is client-side and relies on the cached `created_at` timestamp.
