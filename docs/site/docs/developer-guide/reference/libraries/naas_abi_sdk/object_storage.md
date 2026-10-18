# ObjectStorageClient

## What it is
An asynchronous client wrapper for the `abi.svc.object_storage.v1` object storage service. It forwards typed protobuf requests to a provided `Transport` and returns typed protobuf responses.

## Public API
- `class ObjectStorageClient(transport: Transport)`
  - `async get_object(request: pb.GetObjectRequest) -> pb.GetObjectResponse`  
    Calls RPC `abi.svc.object_storage.v1.get_object`.
  - `async put_object(request: pb.PutObjectRequest) -> pb.PutObjectResponse`  
    Calls RPC `abi.svc.object_storage.v1.put_object`.
  - `async delete_object(request: pb.DeleteObjectRequest) -> pb.DeleteObjectResponse`  
    Calls RPC `abi.svc.object_storage.v1.delete_object`.
  - `async list_objects(request: pb.ListObjectsRequest) -> pb.ListObjectsResponse`  
    Calls RPC `abi.svc.object_storage.v1.list_objects`.
  - `async list_objects_recursive(request: pb.ListObjectsRecursiveRequest) -> pb.ListObjectsRecursiveResponse`  
    Calls RPC `abi.svc.object_storage.v1.list_objects_recursive`.
  - `async get_object_metadata(request: pb.GetObjectMetadataRequest) -> pb.GetObjectMetadataResponse`  
    Calls RPC `abi.svc.object_storage.v1.get_object_metadata`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing `await transport.call(method: str, request: Any, response_type: Type)`.
  - Protobuf messages from `naas_abi_proto.object_storage.v1.object_storage_pb2` (imported as `pb`).

## Usage
```python
import asyncio
from naas_abi_sdk.object_storage import ObjectStorageClient
from naas_abi_proto.object_storage.v1 import object_storage_pb2 as pb

# transport must be an instance of naas_abi_sdk.transport.Transport
transport = ...  # provide your Transport implementation
client = ObjectStorageClient(transport)

async def main():
    req = pb.ListObjectsRequest()  # populate fields as required by your proto
    resp = await client.list_objects(req)
    print(resp)

asyncio.run(main())
```

## Caveats
- All methods are `async` and must be awaited.
- Request/response shapes are defined by the protobuf module (`pb`); this client does not validate or transform fields beyond forwarding them to `Transport.call`.
