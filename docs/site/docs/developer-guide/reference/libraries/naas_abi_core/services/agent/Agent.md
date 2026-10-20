# Agent

## What it is

A LangGraph/LangChain orchestration wrapper around a `BaseChatModel` that:

- Runs a chat model with optional tool calling (LangChain tools + “native” tool schemas).
- Supports sub-agents via `transfer_to_<agent>` handoff tools (LangGraph `Command` routing).
- Persists conversation state via a LangGraph checkpointer (engine-provided, PostgreSQL, or in-memory).
- Streams execution events (tool usage/response, AI messages, routing/model-call) and can expose SSE endpoints.

---

## Public API

### Module-level functions

- `create_checkpointer() -> BaseCheckpointSaver`  
  Creates a checkpointer:
  - If running inside an engine: uses `get_default_agent_checkpointer()`.
  - Else, uses PostgreSQL when `POSTGRES_URL` is set (shared singleton per process).
  - Else falls back to in-memory `MemorySaver`.

- `close_shared_checkpointer() -> None`  
  Closes/reset the shared PostgreSQL connection/checkpointer (if in use).

- `compact_old_tool_messages(messages: list[AnyMessage]) -> list[AnyMessage]`  
  Returns a copy of `messages` where older `ToolMessage` contents are stubbed/truncated to reduce context size (does not mutate checkpointed state).

- `make_handoff_tool(agent: Agent, parent_graph: bool = False) -> BaseTool`  
  Builds a tool named `transfer_to_<agent_name>` that:
  - Appends an internal `ToolMessage` (`__handoff__:<agent>`) to the state’s messages.
  - Updates `current_active_agent`.
  - Returns a `langgraph.types.Command` that routes to the target agent node (optionally in `Command.PARENT` graph).

### Data / configuration classes

- `class AgentSharedState`  
  Shared, mutable routing/thread state:
  - `thread_id: str`
  - `current_active_agent: str | None` (sticky routing target)
  - `supervisor_agent: str | None` (used by sub-agents + `request_help`)
  - `requesting_help: bool`
  - Methods: `set_thread_id`, `set_current_active_agent`, `set_supervisor_agent`, `set_requesting_help`

- `class AgentConfiguration` *(dataclass)*  
  Hooks + system prompt:
  - `on_tool_usage(message)`
  - `on_tool_response(message)`
  - `on_ai_message(message, agent_name)`
  - `on_agent_calling(agent_name)`
  - `on_agent_routing(agent_name)`
  - `system_prompt: str | Callable[[list[AnyMessage]], str]`
  - `get_system_prompt(messages) -> str`

- `class CompletionQuery(BaseModel)`  
  Request body used by FastAPI endpoints:
  - `prompt: str`
  - `thread_id: str | int`

### Events (dataclasses)

Used internally for `stream_invoke` and the shared event queue:

- `Event(payload)`
- `ToolUsageEvent`
- `ToolResponseEvent`
- `AIMessageEvent(payload, agent_name)`
- `CallModelEvent(payload, agent_name)`
- `AgentRoutingEvent(payload, agent_name)`
- `FinalStateEvent`

### Main class: `class Agent(Expose)`

#### Constructor

- `Agent.__init__(..., chat_model, tools=None, agents=None, memory=None, state=AgentSharedState(), configuration=AgentConfiguration(), event_queue=None, native_tools=None, enable_default_tools=True, markdown_pretty_display=False)`

Key behaviors from initialization:

- Validates/sanitizes `name` via `validate_name`.
- Optionally injects:
  - `request_help` tool when `state.supervisor_agent` is set (and differs from this agent).
  - default tools via `default_tools(self)` when `enable_default_tools=True`.
- Normalizes tools and sub-agents via `prepare_tools(...)`.
- Binds tools to the chat model when supported (`can_bind_tools(model)`), including a variant that excludes “workspace-gated” tools unless a workspace context is present.
- Selects checkpointer from `memory` or `create_checkpointer()`.
- In `ENV=dev`, randomizes `thread_id` to a UUID.
- Builds/compiles the internal LangGraph (`build_graph()`).

#### Primary methods

- `validate_name(name: str) -> str` *(static)*  
  Replaces invalid graph/tool name characters with `_` (pattern `^[a-zA-Z0-9_-]+$`). Cached.

- `prepare_tools(tools, agents) -> (list[Tool|BaseTool], list[Agent])`  
  - Converts `Agent` instances into `transfer_to_*` tools (`as_tools()`).
  - Deduplicates by tool/agent name.

- `as_tools(parent_graph: bool = False) -> list[BaseTool]`  
  Exposes this agent as a single handoff tool via `make_handoff_tool`.

- `build_graph(patcher: Callable | None = None) -> None`  
  Builds/compiles a `StateGraph(ABIAgentState)` with nodes:
  - `render_system_prompt` → `current_active_agent` → `continue_conversation` → `call_model` → `call_tools` (as needed)
  - Each sub-agent is added as a node with `agent.graph`.

- `stream(prompt: str) -> Generator[dict|Any, None, None]`  
  Runs `graph.stream(..., subgraphs=True)` for a `HumanMessage(prompt)` and yields raw LangGraph stream chunks. Also emits internal events/callbacks for:
  - tool usage (AI messages containing tool calls),
  - tool responses (ToolMessage; excluding handoff tool messages),
  - AI messages (from `call_model` / `call_tools`).

- `invoke(prompt: str) -> str`  
  Consumes `stream()` to completion and returns final message content (best-effort extraction). Publishes an “invocation completed” event.

- `stream_invoke(prompt: str) -> Generator[dict, None, None]`  
  Runs `invoke()` in a background thread and yields SSE-style events:
  - `tool_usage`, `tool_response` (truncated), `ai_message`, `call_model`, `agent_routing`
  - `message` (line-buffered final response)
  - `done`

- `reset() -> None`  
  Starts a new conversation thread:
  - increments numeric `thread_id`, else sets a new UUID.

- `duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> Agent`  
  Creates a new instance that shares:
  - the same checkpointer,
  - the provided/shared `AgentSharedState`,
  - the provided/shared event queue,
  and recursively duplicates sub-agents. Rebuilds graphs; may carry `recursion_limit`.

- `as_api(router: APIRouter, route_name="", name="", description="", description_stream="", tags=None) -> None`  
  Registers FastAPI endpoints:
  - `POST /<route_name>/completion` → duplicates the agent with `thread_id` and returns `invoke(prompt)`.
  - `POST /<route_name>/stream-completion` → SSE via `EventSourceResponse(stream_invoke(prompt))`.

#### Callback registration (configuration overrides)

- `on_tool_usage(callback)`
- `on_tool_response(callback)`
- `on_ai_message(callback)` (also applied to sub-agents)

#### Properties

- `name: str`
- `description: str`
- `tools: list[Tool|BaseTool]` (structured tools)
- `structured_tools: list[Tool|BaseTool]`
- `agents: list[Agent]`
- `state: AgentSharedState`
- `chat_model: BaseChatModel`
- `configuration: AgentConfiguration`
- `app` (returns `self._app`; `_app` is not defined in this file)

#### Misc

- `hello() -> str` → `"Hello"`
- `Agent.New(...)` → raises `NotImplementedError`

---

## Configuration/Dependencies

### Environment variables

- `POSTGRES_URL`  
  Enables a shared, process-wide PostgreSQL checkpointer (`langgraph.checkpoint.postgres.PostgresSaver` via `psycopg`). Retries connection up to 3 times.

- `ENV=dev`  
  On init, randomizes `state.thread_id` to a UUID.

### Runtime dependencies (non-exhaustive)

- LangChain Core: `BaseChatModel`, messages (`HumanMessage`, `AIMessage`, `ToolMessage`, …), tools (`tool`, `StructuredTool`, `BaseTool`).
- LangGraph: `StateGraph`, `Command`, checkpointers (`MemorySaver`, optional `PostgresSaver`).
- SSE: `sse_starlette.sse.EventSourceResponse`
- Internal modules: `default_tools`, `can_bind_tools`, engine context (`get_default_agent_checkpointer`, `get_default_event_service`), agent context vars (workspace/user/chat ids).

---

## Usage

### Minimal invocation

```python
from naas_abi_core.services.agent.Agent import Agent
from langchain_core.language_models import BaseChatModel

model: BaseChatModel = ...  # provide a concrete LangChain chat model
agent = Agent(name="main", description="Demo agent", chat_model=model)

print(agent.invoke("Hello"))
```

### With sub-agent handoff

```python
from naas_abi_core.services.agent.Agent import Agent
from langchain_core.language_models import BaseChatModel

model: BaseChatModel = ...

math_agent = Agent(name="math", description="Math helper", chat_model=model)
main = Agent(name="main", description="Supervisor", chat_model=model, agents=[math_agent])

# The supervisor will have a tool named transfer_to_math
print(main.invoke("Please ask @math to compute 2+2."))
```

### FastAPI endpoints

```python
from fastapi import FastAPI
from naas_abi_core.services.agent.Agent import Agent
from langchain_core.language_models import BaseChatModel

app = FastAPI()
model: BaseChatModel = ...

agent = Agent(name="agent", description="API agent", chat_model=model)
agent.as_api(app.router, route_name="agent")
```

---

## Caveats

- `Agent.New(...)` is declared but not implemented.
- Tool calling is only enabled when the model supports binding tools (`can_bind_tools`); otherwise tools are not available to the model.
- `Agent.app` returns `self._app`, but `_app` is not defined in this module (property access may fail unless set elsewhere).
- Sub-agent routing is persisted in the checkpointer (`current_active_agent` / `supervisor_agent`) and restored per-thread on subsequent turns; names not in the agent’s graph are ignored.
- `stream_invoke` uses a shared queue; if the worker thread dies before posting a final event, it raises `RuntimeError`.
