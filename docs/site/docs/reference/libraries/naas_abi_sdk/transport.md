# Transport

## What it is
- An async, one-attempt protobuf RPC transport over NATS.
- Adds service-token authentication via NATS headers.
- Supports request/reply payload overflow using `naas_abi_sdk.overflow` when messages exceed broker limits.
- Designed to be owned by a single client/event loop.

## Public API

### Constants
- `MODULE_USER = "module"`: NATS username used by broker user SDK modules.
- `MODULE_INBOX_PREFIX = "_INBOX_MODULES"`: Inbox prefix used for module connections.
- `INBOX_PREFIXES = ("_INBOX.", "_INBOX_MODULES.")`: Recognized reply inbox prefixes.

### Functions
- `is_inbox(subject: str) -> bool`
  - Returns whether a subject starts with a recognized inbox prefix.

- `is_module_subject(subject: str) -> bool`
  - Returns whether `subject` targets a module instance (expects `abi.agent.<project>...` or `abi.mod.<project>...` in a 3-token prefix check).

- `module_audience(subject: str, instance_id: str) -> str`
  - Validates `instance_id` (must match `[A-Za-z0-9_-]{1,128}`) and ensures `subject` addresses that instance (expects token 4 to equal `instance_id`).
  - Returns the validated `instance_id`.
  - Raises `ValueError` on invalid `instance_id` or mismatched subject.

### Exceptions
- `class RPCError(RuntimeError)`
  - Raised for transport-level and remote-reported errors.
  - Attributes:
    - `code: str`
    - `response: google.protobuf.message.Message | None` (present when error came from a protobuf response containing an `error` field)

### Class: `Transport`
Async transport wrapper around a NATS client.

#### `__init__(url: str, token: str | Callable[[], str], timeout: float = 10.0, **connection_options)`
- `timeout` must be finite and positive, otherwise raises `ValueError`.
- If `url` has username `module`, sets `inbox_prefix` to `_INBOX_MODULES` unless provided.

#### `async connect() -> nats.aio.client.Client`
- Establishes a connection if not already connected.
- Uses an internal lock to serialize connect/close operations.
- Raises `RuntimeError` if the transport is closed.

#### `async close() -> None`
- Marks the transport closed and closes the underlying NATS connection.

#### `async call(subject: str, request: Message, response_type: type[Response], *, transfer: TransferTrace | None = None, instance_id: str | None = None) -> Response`
- Performs a single request/reply exchange.
- Copies `request` before mutation.
- Ensures `request.context.trace_id` is set (UUID if empty) and sets `request.context.timeout_ms`.
- Adds header `Nats-Auth-Token` from the configured token source.
  - If calling a module subject, `instance_id` is required and token source must provide `for_audience(audience)`; otherwise raises `ValueError`.
- Handles overflow:
  - If no `transfer` is provided, may upload oversized request and/or download parked replies via `naas_abi_sdk.overflow`.
  - If `transfer` is provided, performs a direct exchange (intended for overflow chunk transfers).
- Raises `RPCError` for:
  - Payload too large for broker limit.
  - Remote NATS service error headers.
  - Protobuf response containing an `error` field (including nested `error.error...` chains).

## Configuration/Dependencies
- Requires:
  - `nats-py` (`nats.aio.client.Client`)
  - `google.protobuf`
  - `naas_abi_sdk` modules: `overflow`, `no_responders`, `lifeline`, `messages.message_size`, `telemetry`
- Authentication:
  - Adds `Nats-Auth-Token` header to each request.
  - For module subjects, token provider must implement `for_audience(instance_id)` (e.g., `naas_abi_sdk.service_token.ModuleToken` as referenced in error text).
- Connection options:
  - Passed through as `**connection_options` to `Client.connect(...)` (with `pending_size=0` and a managed `closed_cb`).

## Usage

```python
import asyncio
from google.protobuf.message import Message

from naas_abi_sdk.transport import Transport

# Replace these with your generated protobuf classes.
from my_pb2 import MyRequest, MyResponse  # noqa: F401


async def main():
    t = Transport(
        url="nats://localhost:4222",
        token="your-service-token",
        timeout=10.0,
        name="my-client",
    )

    req = MyRequest()
    # req.context is expected by the transport (trace_id/timeout_ms are set).
    resp = await t.call("abi.svc.myservice.v1.Method", req, MyResponse)

    await t.close()
    print(resp)


asyncio.run(main())
```

### Calling a module subject (requires `instance_id` and a token source with `for_audience`)
```python
# token_source must provide: token_source.for_audience(instance_id) -> str
t = Transport(url="nats://localhost:4222", token=token_source)

resp = await t.call(
    "abi.mod.myproject.myinstance.v1.Method",
    req,
    MyResponse,
    instance_id="myinstance",
)
```

## Caveats
- The transport mutates `request.context` fields; it copies the request first to avoid altering caller-owned instances.
- Module-subject calls require:
  - A valid `instance_id` (regex `[A-Za-z0-9_-]{1,128}`)
  - A subject whose 4th token matches `instance_id`
  - A token provider supporting `for_audience`; a plain string token is insufficient.
- Service token must be non-empty and must not contain `\r` or `\n`; otherwise `ValueError` is raised.
- Timeouts:
  - The call uses `asyncio.wait_for(..., timeout=self.timeout)` around the NATS request, and also sets `context.timeout_ms` in the protobuf request.
- If the NATS client gives up reconnecting, the transport resets its internal client and will reconnect on the next `connect()/call()`.
