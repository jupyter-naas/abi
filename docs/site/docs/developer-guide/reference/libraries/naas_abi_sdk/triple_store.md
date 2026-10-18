# TripleStoreClient

## What it is
An async Python client wrapper for the `abi.svc.triple_store.v1` service. It forwards typed protobuf requests to a provided `Transport` and returns typed protobuf responses.

## Public API
- `class TripleStoreClient(transport: Transport)`
  - Constructs a client using the given `Transport` implementation.
  - Methods (all `async`, all delegate to `transport.call(...)`):
    - `insert(request: pb.InsertRequest) -> pb.InsertResponse`: Insert data into the triple store.
    - `remove(request: pb.RemoveRequest) -> pb.RemoveResponse`: Remove data from the triple store.
    - `get(request: pb.GetRequest) -> pb.GetResponse`: Retrieve data from the triple store.
    - `handle_view_event(request: pb.HandleViewEventRequest) -> pb.HandleViewEventResponse`: Handle a view-related event.
    - `query(request: pb.QueryRequest) -> pb.QueryResponse`: Run a query.
    - `query_view(request: pb.QueryViewRequest) -> pb.QueryViewResponse`: Run a query against a view.
    - `get_subject_graph(request: pb.GetSubjectGraphRequest) -> pb.GetSubjectGraphResponse`: Fetch a subject graph.
    - `create_graph(request: pb.CreateGraphRequest) -> pb.CreateGraphResponse`: Create a graph.
    - `clear_graph(request: pb.ClearGraphRequest) -> pb.ClearGraphResponse`: Clear a graph’s contents.
    - `drop_graph(request: pb.DropGraphRequest) -> pb.DropGraphResponse`: Drop a graph.
    - `list_graphs(request: pb.ListGraphsRequest) -> pb.ListGraphsResponse`: List available graphs.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport`: must provide an async `call(method: str, request, response_type)` API.
  - Protobuf messages from `naas_abi_proto.triple_store.v1.triple_store_pb2` (imported as `pb`).
- RPC method names used internally:
  - `abi.svc.triple_store.v1.insert`
  - `abi.svc.triple_store.v1.remove`
  - `abi.svc.triple_store.v1.get`
  - `abi.svc.triple_store.v1.handle_view_event`
  - `abi.svc.triple_store.v1.query`
  - `abi.svc.triple_store.v1.query_view`
  - `abi.svc.triple_store.v1.get_subject_graph`
  - `abi.svc.triple_store.v1.create_graph`
  - `abi.svc.triple_store.v1.clear_graph`
  - `abi.svc.triple_store.v1.drop_graph`
  - `abi.svc.triple_store.v1.list_graphs`

## Usage
```python
import asyncio
from naas_abi_sdk.triple_store import TripleStoreClient
from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

async def main(transport):
    client = TripleStoreClient(transport)

    # Example: list graphs (fields depend on the proto definition)
    resp = await client.list_graphs(pb.ListGraphsRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a concrete Transport instance
```

## Caveats
- All methods are async and require an event loop (`await`/`asyncio`).
- Request/response fields are defined by the protobufs; this module does not validate or transform them.
- Behavior (routing, errors, retries, auth) is determined by the injected `Transport` implementation.
