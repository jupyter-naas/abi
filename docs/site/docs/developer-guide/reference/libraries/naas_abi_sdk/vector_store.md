# VectorStoreClient

## What it is
An async client wrapper around a `Transport` that calls the `abi.svc.vector_store.v1.*` RPC endpoints using protobuf request/response messages from `naas_abi_proto.vector_store.v1.vector_store_pb2`.

## Public API
- `class VectorStoreClient(transport: Transport)`
  - Holds a transport instance and exposes async methods that forward requests to the remote Vector Store service.

### Methods (all `async`)
- `initialize(request: pb.InitializeRequest) -> pb.InitializeResponse`  
  Initialize the vector store service.
- `create_collection(request: pb.CreateCollectionRequest) -> pb.CreateCollectionResponse`  
  Create a vector collection.
- `delete_collection(request: pb.DeleteCollectionRequest) -> pb.DeleteCollectionResponse`  
  Delete a vector collection.
- `list_collections(request: pb.ListCollectionsRequest) -> pb.ListCollectionsResponse`  
  List available collections.
- `store_vectors(request: pb.StoreVectorsRequest) -> pb.StoreVectorsResponse`  
  Store vectors in a collection.
- `search(request: pb.SearchRequest) -> pb.SearchResponse`  
  Search vectors in a collection.
- `get_vector(request: pb.GetVectorRequest) -> pb.GetVectorResponse`  
  Retrieve a single vector.
- `update_vector(request: pb.UpdateVectorRequest) -> pb.UpdateVectorResponse`  
  Update a stored vector.
- `delete_vectors(request: pb.DeleteVectorsRequest) -> pb.DeleteVectorsResponse`  
  Delete vectors from a collection.
- `count_vectors(request: pb.CountVectorsRequest) -> pb.CountVectorsResponse`  
  Count vectors in a collection.
- `list_vectors(request: pb.ListVectorsRequest) -> pb.ListVectorsResponse`  
  List vectors in a collection.
- `get_collection_info(request: pb.GetCollectionInfoRequest) -> pb.GetCollectionInfoResponse`  
  Get metadata/info for a collection.
- `close(request: pb.CloseRequest) -> pb.CloseResponse`  
  Close/shutdown the vector store service connection/session (service-defined).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing `await transport.call(method_name, request, response_type)`
  - Protobuf messages in `naas_abi_proto.vector_store.v1.vector_store_pb2` (imported as `pb`)
- Each method calls a fixed RPC name such as:
  - `"abi.svc.vector_store.v1.search"`, `"abi.svc.vector_store.v1.store_vectors"`, etc.

## Usage
```python
import asyncio
from naas_abi_sdk.vector_store import VectorStoreClient
from naas_abi_proto.vector_store.v1 import vector_store_pb2 as pb

async def main(transport):
    client = VectorStoreClient(transport)

    # Example call (fields depend on your protobuf schema)
    resp = await client.list_collections(pb.ListCollectionsRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a real Transport instance
```

## Caveats
- All operations are asynchronous and require an async runtime (`asyncio`).
- Request message fields are defined by the protobuf schema; this module does not validate or enrich requests.
- Correct behavior depends on the provided `Transport` implementation and the remote service.
