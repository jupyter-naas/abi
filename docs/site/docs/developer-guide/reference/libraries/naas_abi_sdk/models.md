# naas_abi_sdk.models

## What it is
Optional proxy implementations that expose remote ABI-served models as LangChain-compatible objects:
- `ChatModelProxy` implements `langchain_core`’s `BaseChatModel`
- `EmbeddingModelProxy` implements `langchain_core`’s `Embeddings`

The proxies keep provider credentials and execution inside the owning engine, communicating over the SDK transport.

## Public API

### Classes

- `ModelConnection`
  - Purpose: Ensures all NATS/RPC I/O happens on the asyncio event loop that created the connection.
  - Key methods:
    - `sync(coroutine)`: Run an async coroutine on the SDK loop from another thread/loop (raises if called on the SDK loop or if the SDK loop isn’t running).
    - `on_loop(awaitable)`: Await an awaitable on the SDK loop (works both from the SDK loop and from other loops/threads).
    - `frames(operation, request)`: Async generator yielding raw response frames (bytes) for streaming operations.
    - `result(operation, request, response_type)`: Collect exactly one frame and parse it via `response_type.FromString(...)`.

- `UnaryModelConnection(ModelConnection)`
  - Purpose: Connection variant for module-served (unary) models.
  - Differences:
    - `result(...)` calls `client.<operation>(request)` directly on the SDK loop.
    - `frames(...)` always raises `RPCError("UNIMPLEMENTED", ...)` (no streaming).

- `ChatModelProxy(BaseChatModel)`
  - Purpose: LangChain chat model proxy backed by remote ABI RPC calls.
  - Public methods:
    - `bind_tools(tools: Sequence, *, tool_choice=None, **kwargs)`: Binds tools using OpenAI-tool schema conversion (`convert_to_openai_tool`). Also adapts `ls_structured_output_format` if present.
  - Implements LangChain internals used by `.invoke()/.ainvoke()/.stream()/.astream()`:
    - `_generate(...)` (sync) and `_agenerate(...)` (async): perform unary `chat` call.
    - `_stream(...)` (sync) and `_astream(...)` (async): perform streaming `stream` call yielding `ChatGenerationChunk`.

- `EmbeddingModelProxy(Embeddings)`
  - Purpose: LangChain embeddings proxy backed by remote ABI RPC calls.
  - Methods:
    - `aembed_documents(texts: list[str]) -> list[list[float]]`
    - `aembed_query(text: str) -> list[float]`
    - `embed_documents(texts: list[str]) -> list[list[float]]` (sync wrapper)
    - `embed_query(text: str) -> list[float]` (sync wrapper)

- `RemoteModel` (frozen `@dataclass`)
  - Purpose: Container describing a resolved remote model and its instantiated proxy.
  - Fields:
    - `canonical_id`, `model_id`, `provider`, `model`, `model_type`, `name`, `description`, `metadata`

### Functions

- `remote_model(client, descriptor: pb.ModelDescriptor) -> RemoteModel`
  - Purpose: Build a `RemoteModel` and the correct proxy (`ChatModelProxy` if `descriptor.ref.kind == "chat"`, otherwise `EmbeddingModelProxy`) from a protobuf model descriptor.

## Configuration/Dependencies
- Optional extra: `naas-abi-sdk[models]` (as indicated by the module docstring).
- Runtime dependencies used directly in this module:
  - `langchain_core` (chat models, messages, outputs, embeddings, tool conversion)
  - `naas_abi_proto.model_registry.v1.model_registry_pb2` (protobuf request/response types)
  - `pydantic` (`PrivateAttr`)
  - SDK internals: `naas_abi_sdk.model_codec` and `naas_abi_sdk.transfer.model_frames`
- The `client` passed to `ModelConnection` / `remote_model()` must expose RPC methods matching operations used here:
  - Unary: `chat(request)` and `embed(request)`
  - Streaming: `model_frames(client, "stream", request)` must work for chat streaming

## Usage

```python
import asyncio
from naas_abi_sdk.models import remote_model

async def main(client, descriptor):
    rm = remote_model(client, descriptor)

    if rm.model_type == "chat":
        # LangChain-style async invocation
        result = await rm.model.ainvoke("Hello")
        print(result.content)
    else:
        vec = await rm.model.aembed_query("hello")
        print(len(vec))

# asyncio.run(main(client, descriptor))  # client/descriptor provided by your SDK environment
```

## Caveats
- `ModelConnection.sync(...)` cannot be called from the same running loop that created the connection; it is intended for cross-thread / cross-loop bridging. It raises:
  - if called on the SDK loop
  - if the SDK loop is not running
- `UnaryModelConnection` does not support streaming; calling streaming paths raises `RPCError("UNIMPLEMENTED", ...)`.
- `ChatModelProxy` expects the remote `chat` response to decode to an `AIMessage`, and streaming frames to decode to `AIMessageChunk`; otherwise it raises `TypeError`.
