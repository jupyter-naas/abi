# ModelRegistryClient

## What it is
An async client wrapper for the `abi.svc.model_registry.v1` service. It sends protobuf request messages over a provided `Transport` and returns protobuf responses.

## Public API
- `class ModelRegistryClient(transport: Transport)`
  - Purpose: Provide typed async methods to call Model Registry service endpoints via `Transport.call`.

Methods (all `async`, return protobuf responses from `naas_abi_proto.model_registry.v1.model_registry_pb2`):
- `list_models(request: pb.ListModelsRequest) -> pb.ListModelsResponse`
  - List available models.
- `resolve(request: pb.ResolveRequest) -> pb.ResolveResponse`
  - Resolve a model reference to a concrete model/config.
- `chat(request: pb.ChatRequest) -> pb.ChatResponse`
  - Execute a chat request.
- `stream_open(request: pb.StreamOpenRequest) -> pb.StreamOpenResponse`
  - Open a streaming session.
- `stream_next(request: pb.StreamNextRequest) -> pb.StreamNextResponse`
  - Fetch next streaming chunk/event for `request.stream_id` (uses a stream-id-derived subject).
- `stream_close(request: pb.StreamCloseRequest) -> pb.StreamCloseResponse`
  - Close a streaming session for `request.stream_id` (uses a stream-id-derived subject).
- `embed(request: pb.EmbedRequest) -> pb.EmbedResponse`
  - Request embeddings.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing `await transport.call(subject, request, response_type)`.
  - Protobuf messages in `naas_abi_proto.model_registry.v1.model_registry_pb2` (imported as `pb`).
  - `naas_abi_sdk.transfer.transfer_subject` for `stream_next` / `stream_close` subject routing based on `stream_id`.
- No internal configuration; caller supplies a `Transport` instance.

## Usage
```python
import asyncio
from naas_abi_sdk.model_registry import ModelRegistryClient
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

async def main(transport):
    client = ModelRegistryClient(transport)

    # Example: list models
    resp = await client.list_models(pb.ListModelsRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a real Transport instance
```

## Caveats
- All methods are asynchronous and require an event loop.
- `stream_next` and `stream_close` require `request.stream_id` to be set; it is used to build the transport subject.
