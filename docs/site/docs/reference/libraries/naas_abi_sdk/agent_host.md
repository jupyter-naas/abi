# AgentHost

## What it is
Provider-side agent hosting for ABI agents where **only data crosses the network boundary**. It:
- Subscribes to per-agent NATS subjects (`submit`, `status`, `cancel`, `event`).
- Persists invocation state and output fragments in a document store.
- Enforces single active execution per `(caller, agent, thread_id)` via a durable “conversation claim”.
- Supports streaming and non-streaming agent handlers.

## Public API

### Classes

- `InvocationContext`
  - Fields:
    - `invocation_id: str`
    - `thread_id: str` (derived stable hash for the conversation)
    - `caller_identity: str`
    - `cancelled: asyncio.Event` (set when cancellation requested)

- `AgentHandler` (Protocol)
  - `async invoke(prompt: str, context: InvocationContext) -> str`
  - Optional: `async stream_invoke(prompt: str, context: InvocationContext)` yielding dict events (see Caveats).

- `AgentHost`
  - `__init__(session, documents, handlers: dict[str, AgentHandler], *, idle_timeout_seconds: float = 300.0, max_concurrency: int = DEFAULT_LIMIT)`
    - `session`: ABI provider session (used for discovery authorization, module membership, NATS connection, instance id, lease token).
    - `documents`: document service implementing collection CRUD used by the SDK.
    - `handlers`: mapping of agent name → handler object.
    - `idle_timeout_seconds`: cancels runs that do not make progress within this time (used mainly for streaming or runs without a deadline).
    - `max_concurrency`: max in-flight RPC handlers (submit/status/cancel/event) processed concurrently.
  - `async start() -> None`
    - Ensures needed collections exist and binds NATS subscriptions for all handlers/operations.
  - `async drain(timeout: float) -> None`
    - Stops accepting new submits; lets accepted runs finish up to `timeout` seconds. Does **not** cancel runs.
  - `async close() -> None`
    - Drains subscriptions, waits for in-flight calls to finish, then cancels all still-running invocations and waits for tasks.

### Functions

- `agent_runs_collection(project: str) -> str`
  - Returns deterministic collection name for run records for the given project.

- `agent_events_collection(project: str) -> str`
  - Returns deterministic collection name for event/output fragments for the given project.

## Configuration/Dependencies

- Requires `naas_abi_proto` protobufs:
  - `naas_abi_proto.agent.v1.agent_pb2` (requests/responses, Invocation, AgentEvent, RunUpdate)
  - `naas_abi_proto.discovery.v1.discovery_pb2` (AuthorizeAgent)
- Requires SDK services:
  - Document store with `ensure_collection`, `get`, `put`, `delete` and exceptions `DocumentNotFound`, `VersionConflict`.
  - Provider `session` with:
    - `instance_id`, `lease_token`, `descriptor.module_id`, `descriptor.contract_major`
    - `client.project`, `client.transport.connect()`, `client._call(...)`, `client.get_module(...)`
- Uses NATS for messaging (via the session’s transport connection).
- Concurrency control via `ConcurrentCalls(max_concurrency)`.

## Usage

Minimal example showing how to construct and start an `AgentHost` (requires real `session` and `documents` from the SDK runtime):

```python
import asyncio
from naas_abi_sdk.agent_host import AgentHost, InvocationContext

class EchoAgent:
    async def invoke(self, prompt: str, context: InvocationContext) -> str:
        return f"echo: {prompt}"

async def main(session, documents):
    host = AgentHost(
        session=session,
        documents=documents,
        handlers={"echo": EchoAgent()},
        idle_timeout_seconds=300.0,
    )
    await host.start()

    # Run until externally stopped; on shutdown:
    # await host.drain(timeout=10)
    # await host.close()

# asyncio.run(main(session, documents))
```

## Caveats

- **Invocation IDs** must match regex `[A-Za-z0-9_.:-]{1,128}`; invalid IDs are rejected.
- **Submit constraints**:
  - `thread_id` required and `<= 256` chars.
  - `prompt` size `<= 64 KiB` (UTF-8 bytes).
  - `mode` must be `"invoke"` or `"stream"`.
  - `deadline_seconds` must be `0..3600`.
  - `updates_inbox` (if provided) must match `(_INBOX|_INBOX_MODULES)\.[A-Za-z0-9_.-]{1,240}`.
- **Ownership/claims**:
  - Only one active execution per `(caller, agent, thread_id)` via a durable claim document.
  - If a claim owner disappears from discovery, the invocation is marked `FAILED` with `OWNER_GONE` and is **not replayed**.
  - Cancellation is only allowed when this process still owns the live run; lease expiry does **not** imply cancel.
- **Streaming handler contract** (`stream_invoke` if present and `mode="stream"`):
  - Must yield dicts exactly shaped like `{"event": str, "data": str}`.
  - `event` length must be `<= 64`.
  - Must not yield events after a `"done"` event; host will error with `INVALID_STREAM`.
  - Host will append a final `{"event": "done", "data": "[DONE]"}` if missing.
- **Output storage model**:
  - Events and result are stored as fragments in the events collection; inline updates to watchers may omit large payloads (watchers must fall back to `status`/`event` RPCs).
  - Invocation record size is capped (~384 KiB JSON); exceeding this fails with `OUTPUT_LIMIT`.
- **Event retrieval**:
  - `event` RPC serves stored fragments; it rejects requests for uncommitted output (`NOT_FOUND`).
- **Capacity limits**:
  - Maximum active runs in-process: `MAX_ACTIVE_RUNS = 200`.
  - Request payload cap: `128 KiB` (also rejects overflow uploads via header).
  - Status returns at most 64 events per call (paged via `after_sequence`).
