# `CodingEnvironmentClient`

## What it is
- An async client wrapper around a `Transport` for calling the `abi.svc.coding_environment.v1` service.
- Methods accept protobuf request messages and return protobuf response messages from `naas_abi_proto.coding_environment.v1.coding_environment_pb2`.

## Public API
### Class: `CodingEnvironmentClient`
- `__init__(transport: Transport) -> None`  
  - Stores the provided transport used for all RPC calls.

#### Async methods (RPC wrappers)
- `ensure_user(request: pb.EnsureUserRequest) -> pb.EnsureUserResponse`  
  - Calls: `"abi.svc.coding_environment.v1.ensure_user"`
- `list_templates(request: pb.ListTemplatesRequest) -> pb.ListTemplatesResponse`  
  - Calls: `"abi.svc.coding_environment.v1.list_templates"`
- `provision(request: pb.ProvisionRequest) -> pb.ProvisionResponse`  
  - Calls: `"abi.svc.coding_environment.v1.provision"`
- `start(request: pb.StartRequest) -> pb.StartResponse`  
  - Calls: `"abi.svc.coding_environment.v1.start"`
- `stop(request: pb.StopRequest) -> pb.StopResponse`  
  - Calls: `"abi.svc.coding_environment.v1.stop"`
- `delete(request: pb.DeleteRequest) -> pb.DeleteResponse`  
  - Calls: `"abi.svc.coding_environment.v1.delete"`
- `list_environments(request: pb.ListEnvironmentsRequest) -> pb.ListEnvironmentsResponse`  
  - Calls: `"abi.svc.coding_environment.v1.list_environments"`
- `list_all_environments(request: pb.ListAllEnvironmentsRequest) -> pb.ListAllEnvironmentsResponse`  
  - Calls: `"abi.svc.coding_environment.v1.list_all_environments"`
- `get_status(request: pb.GetStatusRequest) -> pb.GetStatusResponse`  
  - Calls: `"abi.svc.coding_environment.v1.get_status"`
- `get_logs(request: pb.GetLogsRequest) -> pb.GetLogsResponse`  
  - Calls: `"abi.svc.coding_environment.v1.get_logs"`
- `get_access(request: pb.GetAccessRequest) -> pb.GetAccessResponse`  
  - Calls: `"abi.svc.coding_environment.v1.get_access"`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing an async method:
    - `call(method: str, request: Any, response_type: Type) -> Awaitable`
  - Protobuf messages from:
    - `naas_abi_proto.coding_environment.v1.coding_environment_pb2` (imported as `pb`)
- All methods are `async` and must be awaited within an event loop.

## Usage
```python
import asyncio
from naas_abi_sdk.coding_environment import CodingEnvironmentClient
from naas_abi_proto.coding_environment.v1 import coding_environment_pb2 as pb

async def main(transport):
    client = CodingEnvironmentClient(transport)

    # Example: ensure a user exists (fields depend on the proto definition)
    req = pb.EnsureUserRequest()
    resp = await client.ensure_user(req)
    print(resp)

# asyncio.run(main(transport))  # provide a configured Transport instance
```

## Caveats
- Request/response fields are defined by the protobuf schema (`coding_environment_pb2`); this module does not validate or modify messages.
- Requires a correctly configured `Transport`; errors from the underlying call propagate through these methods.
