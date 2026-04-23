# Agent

## What it is
A LangGraph/LangChain-based orchestration layer that runs a chat model with tool calling, supports sub-agent handoff via tools, persists conversation state via a checkpointer (in-memory or PostgreSQL), and can stream events (tool usage/response, AI messages) including SSE-friendly output.

## Public API

### Functions
- `create_checkpointer() -> BaseCheckpointSaver`  
  Creates a conversation checkpointer:
  - Uses PostgreSQL-backed checkpointer when `POSTGRES_URL` is set (shared across instances).
  - Falls back to in-memory `MemorySaver` otherwise (or on PostgreSQL init failure).

- `close_shared_checkpointer() -> None`  
  Closes the shared PostgreSQL connection (if used) and resets the shared checkpointer.

- `make_handoff_tool(agent: Agent, parent_graph: bool = False) -> BaseTool`  
  Creates a tool named `transfer_to_<agent_name>` that, when called, returns a `langgraph.types.Command` to route execution to the target agent node and injects a `ToolMessage` indicating handoff.

### Data / Configuration classes
- `class AgentSharedState`  
  Shared mutable routing state:
  - `thread_id: str`
  - `current_active_agent: Optional[str]`
  - `supervisor_agent: Optional[str]`
  - `requesting_help: bool`
  - Setters validate names via `Agent.validate_name`.

- `class AgentConfiguration` (dataclass)  
  Hooks and system prompt configuration:
  - `on_tool_usage(message)`
  - `on_tool_response(message)`
  - `on_ai_message(message, agent_name)`
  - `system_prompt: str | Callable[[list[AnyMessage]], str]`
  - `get_system_prompt(messages)` returns computed prompt.

- `class CompletionQuery(pydantic.BaseModel)`  
  Request model used by the FastAPI endpoints:
  - `prompt: str`
  - `thread_id: str | int`

### Events (dataclasses)
- `Event(payload)`
- `ToolUsageEvent`
- `ToolResponseEvent`
- `AIMessageEvent(payload, agent_name)`
- `FinalStateEvent`

### Main class: `class Agent(Expose)`
Key constructor and methods:

- `Agent.__init__(...)`  
  Creates an agent with:
  - tool binding (if model supports it),
  - optional sub-agents (added as graph nodes and exposed via `transfer_to_*` tools),
  - optional default tools injection (`enable_default_tools=True`),
  - memory via provided `memory` or `create_checkpointer()`,
  - compiled LangGraph `graph` using the checkpointer.

- `Agent.validate_name(name: str) -> str` *(static)*  
  Ensures node/tool-safe names (`^[a-zA-Z0-9_-]+$`), replacing invalid characters with `_`.

- `Agent.prepare_tools(tools, agents) -> (list[Tool|BaseTool], list[Agent])`  
  Normalizes tools and agents:
  - Converts `Agent` instances into handoff tools (via `as_tools()`).
  - Deduplicates by tool/agent name.

- `Agent.as_tools(parent_graph: bool = False) -> list[BaseTool]`  
  Exposes this agent as a single handoff tool: `transfer_to_<agent_name>`.

- `Agent.build_graph(patcher: Optional[Callable] = None) -> None`  
  Builds and compiles the internal LangGraph state machine. If provided, `patcher` can modify the graph before compilation.

- `Agent.stream(prompt: str) -> Generator[tuple|dict|Any, None, None]`  
  Streams LangGraph execution chunks (`graph.stream(..., subgraphs=True)`) and emits internal callbacks/events for:
  - tool usage (AIMessage with tool calls),
  - tool response (ToolMessage),
  - AI messages (from specific nodes).

- `Agent.invoke(prompt: str) -> str`  
  Runs `stream()` to completion and returns the final message content (best-effort extraction from last chunk).

- `Agent.stream_invoke(prompt: str) -> Generator[dict, None, None]`  
  Runs `invoke()` in a background thread and yields SSE-style events:
  - `tool_usage`, `tool_response`, `ai_message`, then line-buffered `message`, and final `done`.

- `Agent.reset() -> None`  
  Starts a new conversation thread by incrementing numeric `thread_id` or generating a new UUID.

- `Agent.duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> Agent`  
  Clones the agent configuration into a new instance with:
  - shared checkpointer,
  - new/shared `AgentSharedState`,
  - shared event queue if provided,
  - recursively duplicated sub-agents.

- `Agent.as_api(router: APIRouter, ...) -> None`  
  Registers FastAPI endpoints:
  - `POST /<route_name>/completion` → returns `invoke(prompt)` for the provided `thread_id`.
  - `POST /<route_name>/stream-completion` → returns `EventSourceResponse` using `stream_invoke(prompt)`.

- Callback registration:
  - `on_tool_usage(callback)`
  - `on_tool_response(callback)`
  - `on_ai_message(callback)` (also propagates to sub-agents)

- Properties:
  - `name: str`, `description: str`
  - `tools: list[Tool|BaseTool]` (structured tools)
  - `structured_tools`
  - `agents: list[Agent]`
  - `state: AgentSharedState`
  - `chat_model: BaseChatModel`
  - `configuration: AgentConfiguration`

- Misc:
  - `hello() -> str` returns `"Hello"`.

## Configuration/Dependencies

### Environment variables
- `POSTGRES_URL`  
  When set, `create_checkpointer()` attempts PostgreSQL-backed persistence via `langgraph.checkpoint.postgres.PostgresSaver` + `psycopg`.
  - Uses a shared global connection/checkpointer per process.
  - Retries connection up to 3 times with 2s delay.

- `ENV=dev`  
  Randomizes `state.thread_id` to a UUID during agent initialization.

### Key runtime dependencies
- LangChain core: `BaseChatModel`, tools (`tool`, `BaseTool`, `StructuredTool`), messages (`HumanMessage`, `AIMessage`, `ToolMessage`, etc.)
- LangGraph: `StateGraph`, `Command`, `MemorySaver` (and optional Postgres saver)
- SSE: `sse_starlette.sse.EventSourceResponse` (for API streaming)
- Internal:
  - `default_tools(self)` (optional injection)
  - `can_bind_tools(model)` (checks tool-binding support)
  - `naas_abi_core.models.Model.ChatModel` (wrapper type supported in constructor)

## Usage

### Minimal invocation
```python
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from naas_abi_core.services.agent.Agent import Agent

# You must provide a concrete BaseChatModel implementation.
model: BaseChatModel = ...  # e.g., a LangChain chat model instance

agent = Agent(
    name="main",
    description="My agent",
    chat_model=model,
)

print(agent.invoke("Hello!"))
```

### Register callbacks (tool usage / responses / AI messages)
```python
from naas_abi_core.services.agent.Agent import Agent
from langchain_core.language_models import BaseChatModel

model: BaseChatModel = ...

agent = Agent(name="main", description="Demo", chat_model=model)

agent.on_tool_usage(lambda msg: print("TOOL USAGE:", msg.tool_calls))
agent.on_tool_response(lambda msg: print("TOOL RESPONSE:", getattr(msg, "content", msg)))
agent.on_ai_message(lambda msg, who: print(f"AI ({who}):", msg.content))

agent.invoke("Do something that calls tools.")
```

### FastAPI endpoints
```python
from fastapi import FastAPI
from naas_abi_core.services.agent.Agent import Agent
from langchain_core.language_models import BaseChatModel

app = FastAPI()
model: BaseChatModel = ...

agent = Agent(name="main", description="API agent", chat_model=model)
agent.as_api(app.router, route_name="agent")

# POST /agent/completion  with JSON: {"prompt": "...", "thread_id": "1"}
# POST /agent/stream-completion with same payload (SSE)
```

## Caveats
- `Agent.New(...)` is declared but **not implemented** (raises `NotImplementedError`).
- Tool calling depends on the chat model supporting `bind_tools()`; when unsupported, tools are not available and a warning is logged.
- Name validation replaces invalid characters (including `:`) with `_`; this affects agent/tool names used as LangGraph node IDs.
- When a sub-agent has a supervisor set, a `request_help` tool is injected and can route control back to the supervisor by setting `current_active_agent` and returning a `Command` to the parent graph.
- `app` property returns `self._app`, but `_app` is not defined in this file (access may fail unless set elsewhere).
