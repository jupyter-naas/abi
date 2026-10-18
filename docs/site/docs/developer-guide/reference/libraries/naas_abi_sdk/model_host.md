# ModelHost

## What it is
Serves a module’s unary chat models over NATS subjects that are addressed by instance ID. Requests carry message history plus optional tool schemas; responses may include tool calls. Inference executes in-process; streaming is not supported.

## Public API

- `model_subject(project: str, instance_id: str, name: str) -> str`
  - Builds the NATS subject for a model’s chat endpoint: `abi.mod.{project}.{instance_id}.model.{name}.chat`.

- `class ModuleModelClient`
  - Unary client bound to a specific model on a specific module instance.
  - `__init__(transport, subject: str, instance_id: str)`
    - Stores transport/subject/instance_id.
  - `async chat(request: pb.ChatRequest) -> pb.ChatResponse`
    - Performs an RPC call to the subject and returns `ChatResponse`.

- `class ModelHost`
  - NATS-side host that subscribes to all configured model subjects and dispatches requests to handlers.
  - `__init__(session, handlers: dict[str, Any], *, max_concurrency: int = DEFAULT_LIMIT)`
    - `handlers` is a mapping of model name → handler (must expose `async invoke(messages, ...)`).
    - Limits total concurrent chat calls across all models via `ConcurrentCalls`.
  - `async start() -> None`
    - Connects to NATS, subscribes to each model subject, and flushes.
  - `async close() -> None`
    - Unsubscribes all subjects and cancels in-flight calls.
  - (internal) `_handle(name, msg)` / `_invoke(name, request)`
    - Validate/authorize, decode inputs, call handler, encode response.

- `_handler_kwargs(handler, tools: list[dict], tool_options: dict) -> dict`
  - Determines whether to pass `tools` / `tool_options` to `handler.invoke(...)` based on its signature.
  - Raises `RPCError("UNIMPLEMENTED", ...)` if tools are provided but the handler does not accept them.

## Configuration/Dependencies

- NATS transport via `session.client.transport.connect()`, using:
  - `nc.subscribe(subject, cb=...)`, `nc.flush()`
- Authorization call performed per request:
  - `session.client._call("authorize_model", AuthorizeModelRequest(...), AuthorizeModelResponse)`
- Uses protobuf types:
  - `naas_abi_proto.model_registry.v1.model_registry_pb2` (`ChatRequest`, `ChatResponse`, `ChatMessage`)
  - `naas_abi_proto.discovery.v1.discovery_pb2` (`AuthorizeModelRequest/Response`)
- Message/tool codec helpers:
  - `decode_message`, `encode_message`, `decode_json`
- Concurrency control:
  - `ConcurrentCalls(max_concurrency)` and `DEFAULT_LIMIT`
- Error type:
  - `naas_abi_sdk.transport.RPCError`
- Expects handlers to return either:
  - `str`, or
  - `langchain_core.messages.AIMessage` (strings are wrapped into `AIMessage(content=...)`)

Constants/limits enforced:
- `MAX_REQUEST_BYTES = 512 * 1024` (rejects oversized payloads or overflow header)
- `MAX_MESSAGES = 1024`
- `MAX_TOOLS = 128`

## Usage

### Host a model handler
```python
from naas_abi_sdk.model_host import ModelHost

class MyHandler:
    async def invoke(self, messages, tools=None, tool_options=None):
        # Return a string or an AIMessage
        return "Hello from model"

# session must provide:
# - session.instance_id, session.lease_token
# - session.client.project
# - session.client.transport.connect()
# - session.client._call(...)
host = ModelHost(session, handlers={"my_model": MyHandler()})

await host.start()
# ... serve requests ...
await host.close()
```

### Compute the subject for a model instance
```python
from naas_abi_sdk.model_host import model_subject

subj = model_subject("my_project", "instance-123", "my_model")
```

## Caveats

- Unary only; streaming responses are not part of this contract.
- Tool support is opt-in by handler signature:
  - If tools are provided and `invoke(...)` does not accept `tools` (or `**kwargs`), the request fails with `UNIMPLEMENTED`.
- Requests are rejected when:
  - payload exceeds 512 KiB (or includes the overflow request header),
  - message count is not in `1..1024`,
  - tool definitions exceed 128,
  - tool options are present without tools,
  - decoded tools/options are not JSON objects (`dict`),
  - handler returns neither `str` nor `AIMessage`.
