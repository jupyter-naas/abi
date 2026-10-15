# DocumentClient

## What it is
An async client wrapper for the `abi.svc.document.v1` document service. It sends protobuf request messages through a provided `Transport`, optionally binding all calls to a fixed module namespace.

## Public API
- **Class `DocumentClient(transport: Transport, namespace: str | None = None)`**
  - Holds a transport and an optional bound namespace used to scope requests.

### Service methods (async)
All methods call `Transport.call(method_name, request, response_type)` and return the corresponding protobuf response type.

- `ensure_collection(request: pb.EnsureCollectionRequest) -> pb.EnsureCollectionResponse`
  - Ensure a collection exists.
- `drop_collection(request: pb.DropCollectionRequest) -> pb.DropCollectionResponse`
  - Drop a collection.
- `collections(request: pb.CollectionsRequest) -> pb.CollectionsResponse`
  - List collections.
- `collection_spec(request: pb.CollectionSpecRequest) -> pb.CollectionSpecResponse`
  - Fetch collection specification.
- `namespaces(request: pb.NamespacesRequest) -> pb.NamespacesResponse`
  - List namespaces (platform-wide request).
- `put(request: pb.PutRequest) -> pb.PutResponse`
  - Insert/update a document.
- `get(request: pb.GetRequest) -> pb.GetResponse`
  - Retrieve a document.
- `delete(request: pb.DeleteRequest) -> pb.DeleteResponse`
  - Delete a document.
- `find(request: pb.FindRequest) -> pb.FindResponse`
  - Query documents.
- `count(request: pb.CountRequest) -> pb.CountResponse`
  - Count documents matching a query.

### Namespace helpers
- `namespace -> str | None` (property)
  - The client’s bound namespace (if any).
- `for_namespace(namespace: str) -> DocumentClient`
  - Returns a namespace-bound client using the same transport.
  - Validates that:
    - a namespace is provided and contains no null bytes (`"\x00"`),
    - a client already bound to a namespace cannot change to a different namespace.

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_sdk.transport.Transport` providing `async def call(name, request, response_type)`.
  - Protobuf messages from `naas_abi_proto.document.v1.document_pb2` imported as `pb`.
- **Namespace scoping behavior**
  - If the client is bound to a namespace, requests that have a `namespace` field are cloned and forced to that namespace.
  - Requests without a `namespace` field are considered platform-wide and are rejected when using a namespace-bound client.

## Usage
```python
import asyncio
from naas_abi_sdk.document import DocumentClient
from naas_abi_proto.document.v1 import document_pb2 as pb

async def main(transport):
    client = DocumentClient(transport).for_namespace("my_module")

    # Example: ensure a collection (fields depend on the .proto definition)
    resp = await client.ensure_collection(pb.EnsureCollectionRequest())
    print(resp)

# asyncio.run(main(transport))
```

## Caveats
- A namespace-bound client **cannot**:
  - make platform-wide requests (i.e., requests whose protobuf type does not have a `namespace` field), raising `PermissionError`;
  - send a request with a different `request.namespace` than the bound namespace, raising `ValueError`;
  - change namespaces via `for_namespace()` once bound to a different namespace, raising `ValueError`.
