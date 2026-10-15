# `KeyvalueClient`

## What it is
- An async client wrapper for the `abi.svc.keyvalue.v1` key/value service.
- Delegates all operations to a provided `Transport` via `transport.call(...)`.
- Uses protobuf request/response types from `naas_abi_proto.keyvalue.v1.keyvalue_pb2`.

## Public API
### Class: `KeyvalueClient`
- `__init__(transport: Transport) -> None`
  - Stores the transport used to perform RPC calls.

#### Async methods
- `get(request: pb.GetRequest) -> pb.GetResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.get"`.

- `set(request: pb.SetRequest) -> pb.SetResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.set"`.

- `set_if_not_exists(request: pb.SetIfNotExistsRequest) -> pb.SetIfNotExistsResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.set_if_not_exists"`.

- `delete(request: pb.DeleteRequest) -> pb.DeleteResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.delete"`.

- `delete_if_value_matches(request: pb.DeleteIfValueMatchesRequest) -> pb.DeleteIfValueMatchesResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.delete_if_value_matches"`.

- `exists(request: pb.ExistsRequest) -> pb.ExistsResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.exists"`.

- `list_keys(request: pb.ListKeysRequest) -> pb.ListKeysResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.list_keys"`.

- `get_ttl(request: pb.GetTtlRequest) -> pb.GetTtlResponse`
  - Calls RPC method `"abi.svc.keyvalue.v1.get_ttl"`.

## Configuration/Dependencies
- `naas_abi_sdk.transport.Transport`
  - Must provide an async method: `call(method: str, request: Any, response_type: Type) -> Any`.
- Protobuf messages:
  - `naas_abi_proto.keyvalue.v1.keyvalue_pb2` imported as `pb`.
  - Request/response message fields are defined in the proto package (not in this module).

## Usage
```python
import asyncio
from naas_abi_sdk.keyvalue import KeyvalueClient
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2 as pb

async def main(transport):
    client = KeyvalueClient(transport)

    # Set a value
    await client.set(pb.SetRequest())

    # Get a value
    resp = await client.get(pb.GetRequest())
    print(resp)

# asyncio.run(main(transport))  # transport must be provided by your runtime
```

## Caveats
- All methods are `async`; they must be awaited within an event loop.
- This module does not validate request contents; correctness depends on providing valid protobuf request messages.
- Behavior (e.g., key format, TTL semantics, error handling) is determined by the remote service and the `Transport` implementation.
