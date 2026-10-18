# ActivityLogClient

## What it is
- An async client wrapper for the `abi.svc.activity_log.v1` service.
- Uses a provided `Transport` to make RPC-style calls with protobuf request/response messages.

## Public API
- `class ActivityLogClient(transport: Transport)`
  - `record(request: pb.RecordRequest) -> pb.RecordResponse`
    - Records an activity log entry via `abi.svc.activity_log.v1.record`.
  - `query(request: pb.QueryRequest) -> pb.QueryResponse`
    - Queries activity logs via `abi.svc.activity_log.v1.query`.
  - `list_actors(request: pb.ListActorsRequest) -> pb.ListActorsResponse`
    - Lists actors present in activity logs via `abi.svc.activity_log.v1.list_actors`.
  - `shutdown(request: pb.ShutdownRequest) -> pb.ShutdownResponse`
    - Requests service shutdown via `abi.svc.activity_log.v1.shutdown`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing `async def call(method: str, request, response_type)`.
  - Protobuf messages from `naas_abi_proto.activity_log.v1.activity_log_pb2` imported as `pb`.

## Usage
```python
import asyncio
from naas_abi_sdk.activity_log import ActivityLogClient
from naas_abi_proto.activity_log.v1 import activity_log_pb2 as pb

async def main(transport):
    client = ActivityLogClient(transport)

    # Example: query (fill required fields as defined by your proto)
    req = pb.QueryRequest()
    resp = await client.query(req)
    print(resp)

# asyncio.run(main(transport))  # Provide a Transport instance
```

## Caveats
- All client methods are `async`; they must be awaited within an asyncio event loop.
- Request messages must be valid protobuf types from `activity_log_pb2` (required fields depend on the proto definition).
