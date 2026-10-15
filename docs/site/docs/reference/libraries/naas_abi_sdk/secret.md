# `SecretClient`

## What it is
An async client wrapper for the `abi.svc.secret.v1` secret service. It delegates RPC calls to a provided `Transport` and uses protobuf request/response messages from `naas_abi_proto.secret.v1.secret_pb2`.

## Public API
- `class SecretClient(transport: Transport)`
  - `async get(request: pb.GetRequest) -> pb.GetResponse`  
    Calls RPC method `"abi.svc.secret.v1.get"`.
  - `async set(request: pb.SetRequest) -> pb.SetResponse`  
    Calls RPC method `"abi.svc.secret.v1.set"`.
  - `async remove(request: pb.RemoveRequest) -> pb.RemoveResponse`  
    Calls RPC method `"abi.svc.secret.v1.remove"`.
  - `async list(request: pb.ListRequest) -> pb.ListResponse`  
    Calls RPC method `"abi.svc.secret.v1.list"`.

## Configuration/Dependencies
- Requires a `Transport` instance from `naas_abi_sdk.transport` that implements:
  - `async call(method: str, request: Any, response_type: Type[Any]) -> Any`
- Uses protobuf message classes from:
  - `naas_abi_proto.secret.v1.secret_pb2` (imported as `pb`)

## Usage
```python
import asyncio
from naas_abi_sdk.secret import SecretClient
from naas_abi_proto.secret.v1 import secret_pb2 as pb

async def main(transport):
    client = SecretClient(transport)

    # Example: list secrets (fields depend on the proto definition)
    resp = await client.list(pb.ListRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a configured Transport instance
```

## Caveats
- All methods are `async` and must be awaited.
- Request/response fields are defined by the protobuf schema; consult `secret_pb2` for exact message structure.
