# OpencodeAgent

## What it is
- A lightweight wrapper around the `opencode` CLI server that:
  - starts/stops the server process,
  - sends prompts via HTTP,
  - optionally streams server events (SSE),
  - exposes the agent as LangChain tools and FastAPI routes,
  - optionally persists session/messages via `OpencodeSessionService`.

## Public API

### Exceptions
- `OpencodeError`: Base exception.
- `OpencodeUnavailableError`: Opencode server not reachable (e.g., connection refused).
- `OpencodeRequestError(status_code: int, body: str)`: Non-2xx HTTP responses.
- `OpencodeStartupError`: Server failed to become ready / port not initialized / port conflict.
- `OpencodeTimeoutError`: HTTP request timed out.

### Data / Schemas
- `OpencodeAgentConfiguration` (dataclass)
  - `workdir: str`: Working directory for the server process.
  - `port: int | None`: Port to bind; if `None`, dynamically assigned.
  - `name: str`: Agent/tool name.
  - `description: str`: Agent/tool description.
  - `model: str | None`: Optional `"provider/model"` identifier, sent as `{providerID, modelID}`.
  - `system_prompt: str`: Optional system prompt primed once per session.
  - `opencode_bin: str`: Binary name/path (default `"opencode"`).
  - `startup_timeout: int`: Seconds to wait for health (default `15`).
  - `request_timeout: float | None`: If set, used as `httpx.Timeout(value)`; else connect/write/pool bounded and `read=None`.

- `OpencodeCompletionQuery` (Pydantic)
  - `prompt: str`
  - `thread_id: str = ""`

- `OpencodeToolInput` (Pydantic)
  - `message: str`
  - `thread_id: str = ""`

### Class: `OpencodeAgent`
Core methods/operators:
- `start() -> None`
  - Ensures auth bootstrap file (best-effort), selects/validates port, starts `opencode serve`, waits for `/global/health`.
- `stop() -> None`
  - Terminates/kill the spawned server process (if started by this instance).
- `duplicate(queue=None, agent_shared_state=None)`
  - Returns a new instance sharing configuration and (by default) shared state.
- `reset() -> None`
  - Attempts to increment `state.thread_id` if supported; otherwise clears internal thread→session mapping.
- `invoke(prompt: str, thread_id: Optional[str]=None) -> str`
  - Synchronous wrapper over `ainvoke(...)`.
- `ainvoke(message: str, thread_id: Optional[str]=None) -> str`
  - Sends a message to an opencode session and returns extracted text from returned parts.
  - Watches `/event` in the background to emit tool usage/response callbacks and auto-approve permissions.
- `astream(message: str, thread_id: Optional[str]=None) -> AsyncIterator[str]`
  - Streams raw SSE `data:` JSON lines (as strings) while prompt runs; auto-approves permissions and emits callbacks.
- `stream(message: str, thread_id: Optional[str]=None) -> AsyncIterator[str]`
  - Alias of `astream`.
- `as_tools() -> list[BaseTool]`
  - Exposes a single LangChain `StructuredTool` using `OpencodeToolInput` schema.
- `as_api(router: APIRouter, route_name="", name="", description="", description_stream="", tags=None) -> None`
  - Registers two FastAPI endpoints:
    - `POST /{route_name}/completion` → `{"completion": "..."}`
    - `POST /{route_name}/stream-completion` → SSE stream (`EventSourceResponse`) yielding `{"data": chunk}` and a final `type=end` message.

Callbacks:
- `on_tool_usage(callback)`
- `on_tool_response(callback)`
- `on_ai_message(callback)`
  - Callbacks receive `langchain_core.messages.AIMessage` (and for `on_ai_message`, also `agent_name`).

## Configuration/Dependencies
Runtime dependencies used in this module:
- External process: `opencode` CLI (`opencode serve --port ...`)
- HTTP client: `httpx` (sync/async)
- API framework: `fastapi`, `sse_starlette` (only for `as_api`)
- LangChain: `langchain_core` (only for callbacks/tools)
- Optional persistence: `OpencodeSessionService` (if provided)

Auth bootstrap (best-effort, only if missing):
- Loads `EngineConfiguration` and, if `configuration.opencode.providers` is present, writes auth JSON to:
  - `opencode.auth_file_path` or default `~/.local/share/opencode/auth.json`
- File is created only if it does not exist; mode set to `0600`.

Network endpoints expected from opencode server:
- `GET /global/health` returning JSON like `{"healthy": true}`
- `GET /event` SSE stream with `data: <json>`
- `POST /session` to create a session
- `GET /session/{id}` to check existing session
- `POST /session/{id}/message` to send message parts
- `POST /session/{id}/permissions/{permission_id}` to approve permissions

## Usage

### Minimal invocation
```python
from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
)

conf = OpencodeAgentConfiguration(
    workdir="/tmp/opencode-work",
    port=None,  # auto-pick a free port
    name="opencode_agent",
    description="Opencode-backed dev agent",
)

agent = OpencodeAgent(conf)
print(agent.invoke("Say hello in one sentence."))
agent.stop()
```

### Async streaming (raw SSE `data:` payloads)
```python
import asyncio
from naas_abi_core.services.agent.OpencodeAgent import OpencodeAgent, OpencodeAgentConfiguration

async def main():
    agent = OpencodeAgent(OpencodeAgentConfiguration(
        workdir="/tmp/opencode-work",
        port=None,
        name="opencode_agent",
        description="Opencode-backed dev agent",
    ))
    async for data in agent.astream("List three bullet points."):
        print(data)

asyncio.run(main())
```

### FastAPI routes
```python
from fastapi import FastAPI, APIRouter
from naas_abi_core.services.agent.OpencodeAgent import OpencodeAgent, OpencodeAgentConfiguration

app = FastAPI()
router = APIRouter()

agent = OpencodeAgent(OpencodeAgentConfiguration(
    workdir="/tmp/opencode-work",
    port=None,
    name="opencode_agent",
    description="Opencode-backed dev agent",
))
agent.as_api(router, route_name="opencode")
app.include_router(router)
```

## Caveats
- `start()` will raise `OpencodeStartupError` if:
  - `port` cannot be initialized,
  - the port is in use and the process on it is not healthy,
  - the spawned server does not become healthy within `startup_timeout`,
  - the spawned server exits during startup.
- Default async HTTP timeout has `read=None` (no read timeout). If you set `request_timeout`, it becomes a single `httpx.Timeout(value)` applied to all phases.
- Streaming yields raw JSON strings from SSE `data:` lines; consumers must parse and interpret them.
- Permission auto-approval is attempted when event payloads contain strings starting with `per_` (walks the entire event object).
