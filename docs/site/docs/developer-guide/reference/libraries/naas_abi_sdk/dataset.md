# DatasetClient

## What it is
An async Python client for the `abi.svc.dataset.v1` dataset service. It delegates all operations to a provided `Transport` instance and uses protobuf request/response types from `naas_abi_proto.dataset.v1.dataset_pb2`.

## Public API
- `class DatasetClient(transport: Transport)`
  - `__init__(transport: Transport)`: Store the transport used for RPC calls.
  - `async create(request: pb.CreateRequest) -> pb.CreateResponse`: Create a dataset.
  - `async describe(request: pb.DescribeRequest) -> pb.DescribeResponse`: Get dataset metadata/details.
  - `async list(request: pb.ListRequest) -> pb.ListResponse`: List datasets.
  - `async write(request: pb.WriteRequest) -> pb.WriteResponse`: Write data to a dataset.
  - `async query(request: pb.QueryRequest) -> pb.QueryResponse`: Query data from a dataset.
  - `async flush(request: pb.FlushRequest) -> pb.FlushResponse`: Flush pending writes.
  - `async inlined_row_count(request: pb.InlinedRowCountRequest) -> pb.InlinedRowCountResponse`: Return the inlined row count.
  - `async compact(request: pb.CompactRequest) -> pb.CompactResponse`: Compact dataset storage.
  - `async list_snapshots(request: pb.ListSnapshotsRequest) -> pb.ListSnapshotsResponse`: List dataset snapshots.
  - `async namespace_version(request: pb.NamespaceVersionRequest) -> pb.NamespaceVersionResponse`: The last snapshot that changed a namespace (unset when it never held a dataset).
  - `async drop(request: pb.DropRequest) -> pb.DropResponse`: Drop/delete a dataset.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` with an async method:
    - `call(method: str, request: Any, response_type: Type) -> Awaitable`
  - Protobuf module:
    - `naas_abi_proto.dataset.v1.dataset_pb2` (imported as `pb`)
- Each method maps to a fixed RPC method string (e.g., `"abi.svc.dataset.v1.create"`).

## Usage
```python
import asyncio
from naas_abi_sdk.dataset import DatasetClient
from naas_abi_proto.dataset.v1 import dataset_pb2 as pb

async def main(transport):
    client = DatasetClient(transport)

    # Example: list datasets
    resp = await client.list(pb.ListRequest())
    print(resp)

# asyncio.run(main(transport))  # Provide a concrete Transport instance
```

## Caveats
- All methods are `async`; they must be awaited within an event loop.
- Request/response schemas are defined by the protobuf types in `dataset_pb2`; construct the appropriate `pb.*Request` objects for each call.
