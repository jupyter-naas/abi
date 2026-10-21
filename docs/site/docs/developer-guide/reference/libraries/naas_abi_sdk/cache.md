# CacheClient

## What it is
- An async client wrapper for the `naas_abi_proto.cache.v1` Cache service.
- Sends protobuf requests via a `Transport` to cache RPC subjects (e.g., `abi.svc.cache.v1.get`).

## Public API
- `class CacheClient(transport: Transport, *, subject_prefix: str = "abi.svc.cache.v1")`
  - Creates a cache service client using the provided transport and subject prefix.

### Methods (async)
- `get(request: pb.GetRequest) -> pb.GetResponse`
  - Fetch a value from the cache.
- `set(request: pb.SetRequest) -> pb.SetResponse`
  - Store a value in the cache.
- `set_if_absent(request: pb.SetIfAbsentRequest) -> pb.SetIfAbsentResponse`
  - Store a value only if the key is not already present.
- `delete(request: pb.DeleteRequest) -> pb.DeleteResponse`
  - Remove a key from the cache.
- `exists(request: pb.ExistsRequest) -> pb.ExistsResponse`
  - Check whether a key exists.
- `describe(request: pb.DescribeRequest) -> pb.DescribeResponse`
  - Retrieve cache description/metadata (as defined by the proto service).
- `list_keys(request: pb.ListKeysRequest) -> pb.ListKeysResponse`
  - List keys (as defined by the proto service).

### Methods (sync)
- `tier(index: int) -> CacheClient`
  - Returns a new `CacheClient` targeting an explicitly configured cache tier.
  - Uses subject prefix: `abi.svc.cache.v1.tier.{index}`.
  - Raises `ValueError` if `index < 0`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` with an async method:
    - `call(subject: str, request: protobuf_message, response_type: Type) -> Awaitable[protobuf_message]`
  - Protobuf messages from:
    - `naas_abi_proto.cache.v1.cache_pb2` (imported as `pb`)
- Default subject prefix: `abi.svc.cache.v1`

## Usage
```python
import asyncio
from naas_abi_sdk.cache import CacheClient
from naas_abi_proto.cache.v1 import cache_pb2 as pb

async def main(transport):
    client = CacheClient(transport)

    # Example calls (fields depend on the proto definitions)
    resp = await client.get(pb.GetRequest())
    await client.set(pb.SetRequest())

    # Target a specific cache tier
    tier0 = client.tier(0)
    await tier0.exists(pb.ExistsRequest())

# asyncio.run(main(transport))  # provide a Transport instance
```

## Caveats
- All RPC methods are async and require an event loop.
- Request/response fields are defined by `cache_pb2`; this module only forwards them.
- `tier(index)` only validates non-negative indices; actual tier availability is determined by the server/configuration.
