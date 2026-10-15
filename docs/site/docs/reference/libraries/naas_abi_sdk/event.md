# EventClient

## What it is
- An async client wrapper for the `abi.svc.event.v1` Event service.
- Delegates all RPC calls to a provided `naas_abi_sdk.transport.Transport` instance.
- Uses protobuf request/response types from `naas_abi_proto.event.v1.event_pb2`.

## Public API
### Class: `EventClient`
- `EventClient(transport: Transport)`
  - Stores the transport used to perform RPC calls.

#### Methods (all `async`)
- `append(request: pb.AppendRequest) -> pb.AppendResponse`
  - Calls RPC method `"abi.svc.event.v1.append"`.
- `query(request: pb.QueryRequest) -> pb.QueryResponse`
  - Calls RPC method `"abi.svc.event.v1.query"`.
- `max_seq(request: pb.MaxSeqRequest) -> pb.MaxSeqResponse`
  - Calls RPC method `"abi.svc.event.v1.max_seq"`.
- `get_cursor(request: pb.GetCursorRequest) -> pb.GetCursorResponse`
  - Calls RPC method `"abi.svc.event.v1.get_cursor"`.
- `set_cursor(request: pb.SetCursorRequest) -> pb.SetCursorResponse`
  - Calls RPC method `"abi.svc.event.v1.set_cursor"`.
- `query_for_consumer(request: pb.QueryForConsumerRequest) -> pb.QueryForConsumerResponse`
  - Calls RPC method `"abi.svc.event.v1.query_for_consumer"`.
- `list_event_types(request: pb.ListEventTypesRequest) -> pb.ListEventTypesResponse`
  - Calls RPC method `"abi.svc.event.v1.list_event_types"`.

## Configuration/Dependencies
- Requires a `Transport` implementation providing:
  - `async def call(self, method: str, request: Any, response_type: Type) -> Any`
- Protobuf module:
  - `naas_abi_proto.event.v1.event_pb2` (imported as `pb`), which defines all request/response message classes used above.

## Usage
```python
import asyncio
from naas_abi_sdk.event import EventClient
from naas_abi_proto.event.v1 import event_pb2 as pb

async def main(transport):
    client = EventClient(transport)

    # Example: list event types
    resp = await client.list_event_types(pb.ListEventTypesRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a naas_abi_sdk.transport.Transport instance
```

## Caveats
- All methods are asynchronous; you must call them from an async context.
- This module is generated (“do not edit”); local changes may be overwritten.
