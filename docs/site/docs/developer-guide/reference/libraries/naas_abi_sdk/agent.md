# AgentProxy

## What it is
An async client-side proxy for invoking an agent hosted by a discovered module process. It submits runs over the module’s transport (NATS/RPC), tracks invocation status, streams events, and retrieves final results.

## Public API

### Functions
- `agent_subject(project: str, instance_id: str, name: str, operation: str) -> str`
  - Builds the NATS/RPC subject for an agent operation. Uses `sha256(name)` in the subject.

### Data classes
- `AgentState`
  - Holds per-client state used in submissions.
  - Fields:
    - `thread_id: str` (defaults to a new UUID)
  - Methods:
    - `set_thread_id(thread_id: str) -> None`: validates non-empty `thread_id`.

- `InvocationStatus` (frozen)
  - Immutable status snapshot of an invocation.
  - Fields:
    - `invocation_id`, `thread_id`, `status`, `result`, `error_code`, `error_message`
    - `owner_instance_id`, `owner_available`
    - `events: tuple[dict[str, Any], ...]` (each dict has `sequence`, `event`, `data`)
    - `last_sequence`

### Exceptions
- `SubmissionUncertain(RuntimeError)`
  - Raised when submission outcome is unknown due to transport/timeouts or certain RPC errors.
  - Attribute: `handle: InvocationHandle` (query `handle.status()` before retrying).

### Classes
- `InvocationHandle`
  - Handle to a submitted invocation; can query status, stream events, cancel, and fetch final result.
  - Methods:
    - `status(*, after_sequence: int = 0) -> InvocationStatus`: fetches status (and decodes any multipart outputs).
    - `cancel() -> InvocationStatus`: requests cancellation.
    - `events(*, after_sequence: int = 0, timeout: float | None = None) -> AsyncIterator[dict[str, Any]]`:
      - Yields event dicts (`sequence`, `event`, `data`) until completion.
      - On terminal failure, raises `RPCError(code, message)`.
      - On timeout, raises `RPCError("WAIT_TIMEOUT", ...)`.
    - `result(*, timeout: float | None = None) -> str`: waits for completion via `events()` and returns final `result`.

- `AgentProxy`
  - Main proxy used to submit/invoke the remote agent.
  - Attributes:
    - `name`, `description` (from `descriptor`)
    - `state: AgentState` (holds `thread_id` used in submissions)
  - Methods:
    - `invocation(invocation_id: str) -> InvocationHandle`: creates a handle for an existing invocation id.
    - `submit(prompt: str, *, invocation_id: str | None = None, stream: bool = False, deadline_seconds: int | None = None) -> InvocationHandle`:
      - Submits a run; sets up an updates inbox subscription before submitting.
      - May raise `SubmissionUncertain(handle)` for transport/timeouts or certain RPC failures.
    - `invoke(prompt: str, *, invocation_id: str | None = None, timeout: float | None = None) -> str`:
      - Convenience: `submit(..., deadline_seconds=ceil(timeout) or default)` then returns `handle.result(timeout=timeout)`.
      - Validates `timeout` is `1..3600` seconds if provided.
    - `stream_invoke(prompt: str, *, invocation_id: str | None = None, timeout: float | None = None) -> AsyncIterator[dict[str, str]]`:
      - Convenience: submits in stream mode and yields `{"event": ..., "data": ...}`.
      - Validates `timeout` is `1..3600` seconds if provided.
    - `duplicate(queue=None, agent_shared_state: AgentState | None = None) -> AgentProxy`:
      - Returns a new `AgentProxy` sharing the same module/descriptor.
      - `queue` is not supported (raises `NotImplementedError`); remote streaming must use `stream_invoke`.
    - `as_tools(parent_graph: bool = False) -> list`:
      - Returns LangChain tools via `naas_abi_sdk.agent_tools.agent_tools(self)`.
      - Requires optional dependency `naas-abi-sdk[agents]`.
      - `parent_graph=True` is not supported (raises `NotImplementedError`).
    - `stream(prompt: str)`:
      - Not supported (raises `NotImplementedError`); use `stream_invoke`.

## Configuration/Dependencies
- Transport/RPC:
  - Uses `module.client.transport.call(...)` and `module.client.transport.connect()`; requires a module object providing:
    - `ready_instances()` and `instances()` (for routing)
    - `client.project` and `client.transport`
- Protocol buffers:
  - `naas_abi_proto.agent.v1.agent_pb2` messages (`SubmitRequest`, `StatusRequest`, `CancelRequest`, `EventRequest`, `RunUpdate`, etc.).
- Errors:
  - `naas_abi_sdk.transport.RPCError`
  - `nats.errors.Error` and network/OS errors; protobuf `DecodeError`
- Defaults/constants:
  - Terminal statuses: `SUCCEEDED`, `FAILED`, `CANCELLED`, `TIMED_OUT`
  - Default deadline if no timeout: `DEFAULT_DEADLINE_SECONDS = 300`
  - Update quiet period before status read: `QUIET_SECONDS = 5.0`

## Usage

```python
import asyncio

async def main(agent: "AgentProxy"):
    # Simple request/response
    text = await agent.invoke("Hello!", timeout=30)
    print(text)

    # Streaming events (event name and data)
    async for evt in agent.stream_invoke("Stream this", timeout=30):
        print(evt["event"], evt["data"])

    # Manual submit + handle control
    handle = await agent.submit("Longer task", deadline_seconds=120)
    status = await handle.status()
    print(status.status)

    # Cancel if needed
    # await handle.cancel()

asyncio.run(main(agent_proxy))
```

## Caveats
- `submit()` can raise `SubmissionUncertain(handle)` on transport/timeouts or certain server errors; check `handle.status()` before retrying to avoid duplicate runs.
- `events(timeout=...)` and `result(timeout=...)` enforce a wall-clock timeout and raise `RPCError("WAIT_TIMEOUT", ...)` if exceeded.
- If the owner becomes unavailable (`owner_available == False`), `events()` raises `RPCError("OWNER_UNAVAILABLE", ...)` and execution outcome is considered unknown and not replayed.
- `timeout` validation:
  - `invoke()` / `stream_invoke()`: if provided, must be finite and within `1..3600` seconds.
  - `InvocationHandle.events()`: if provided, must be finite and positive.
- Some features are intentionally unsupported:
  - `AgentProxy.stream()` (raw objects stay in owner process)
  - `duplicate(queue=...)` (process-local queues not supported)
  - `as_tools(parent_graph=True)` (no shared parent graph state)
