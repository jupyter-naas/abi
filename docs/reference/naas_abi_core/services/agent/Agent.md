# Agent

## What it is
A LangGraph/LangChain-based orchestration layer that:
- Wraps a `BaseChatModel` (or `ChatModel`) and binds tools (including sub-agents exposed as “handoff” tools).
- Maintains conversation state via a checkpointer (in-memory by default, PostgreSQL if configured).
- Exposes synchronous (`invoke`) and streaming (`stream`, `stream_invoke`) execution, plus optional FastAPI endpoints (`as_api`).

## Public API

### Module-level functions
- `create_checkpointer() -> BaseCheckpointSaver`
  - Creates a checkpointer:
    - PostgreSQL-backed when `POSTGRES_URL` is set (shared connection, initialized once).
    - Otherwise `MemorySaver` (in-memory).
- `close_shared_checkpointer() -> None`
  - Closes and clears the shared PostgreSQL connection/checkpointer (if used).

### State / configuration models
- `class AgentSharedState`
  - Shared cross-agent state:
    - `thread_id: str`
    - `current_active_agent: Optional[str]`
    - `supervisor_agent: Optional[str]`
    - `requesting_help: bool`
  - Methods: getters/setters for all fields.
- `class ABIAgentState(MessagesState)`
  - LangGraph state: `messages` plus `system_prompt: str`.
- `class AgentConfiguration`
  - Callbacks and system prompt configuration:
    - `on_tool_usage(message)`
    - `on_tool_response(message)`
    - `on_ai_message(message, agent_name)`
    - `system_prompt: str | Callable[[list[AnyMessage]], str]`
  - `get_system_prompt(messages) -> str`
- `class CompletionQuery(BaseModel)`
  - FastAPI request schema:
    - `prompt: str`
    - `thread_id: str | int`

### Events (used for SSE streaming)
- `Event(payload)`
- `ToolUsageEvent(payload)`
- `ToolResponseEvent(payload)`
- `AIMessageEvent(payload, agent_name)`
- `FinalStateEvent(payload)`

### Main class: `Agent`
Constructor:
- `Agent(...)`
  - Key parameters:
    - `name: str`, `description: str`
    - `chat_model: BaseChatModel | ChatModel`
    - `tools: list[Tool | BaseTool | Agent]` (default tools are injected automatically)
    - `agents: list[Agent]` (sub-agents; also exposed as handoff tools)
    - `memory: BaseCheckpointSaver | None` (defaults to `create_checkpointer()`)
    - `state: AgentSharedState`
    - `configuration: AgentConfiguration`
    - `event_queue: Queue | None` (used by `stream_invoke`)
    - `native_tools: list[dict]` (passed through to model tool binding)

Core methods/properties:
- `invoke(prompt: str) -> str`
  - Runs a prompt through the compiled graph and returns the final message content (if any).
- `stream(prompt: str) -> Generator[dict[str, Any] | Any, None, None]`
  - Streams LangGraph execution chunks; also triggers callbacks/events for tool usage/response and AI messages.
- `stream_invoke(prompt: str) -> Generator[dict, None, None]`
  - Server-Sent-Events (SSE) style generator using the internal event queue:
    - emits `tool_usage`, `tool_response`, `ai_message`, `message`, `done`.
- `reset() -> None`
  - Advances `thread_id` (numeric increment if possible, else new UUID).
- `duplicate(queue: Queue | None = None, agent_shared_state: AgentSharedState | None = None) -> Agent`
  - Creates a new agent instance with duplicated sub-agents and shared memory backend; uses provided/shared state and event queue.
- `as_api(router: APIRouter, ...) -> None`
  - Registers FastAPI endpoints:
    - `POST /{route}/completion`
    - `POST /{route}/stream-completion` (SSE)
- Callback registration:
  - `on_tool_usage(callback)`
  - `on_tool_response(callback)`
  - `on_ai_message(callback)` (propagates to sub-agents)
- Tool/sub-agent exposure:
  - `as_tools(parent_graph: bool = False) -> list[BaseTool]` (handoff tool(s))
  - `tools` (property): structured tools available to the agent
  - `agents` (property): configured sub-agents
- Introspection/config:
  - `name`, `description`, `state`, `chat_model`, `configuration`, `structured_tools`
- `hello() -> str`
  - Returns `"Hello"`.

Default injected tools (via `default_tools()`):
- `get_time_date(timezone="Europe/Paris")` (return_direct=False)
- `list_tools_available()` (return_direct=True)
- `list_subagents_available()` (return_direct=True)
- `list_intents_available()` (return_direct=True; depends on `_intents` being present elsewhere)
- Conditionally:
  - `request_help(reason)` if `state.supervisor_agent` exists and differs from `self.name`
  - `get_current_active_agent()`, `get_supervisor_agent()` if a supervisor exists or there are sub-agents
  - `read_makefile()` only when `state.supervisor_agent == self.name` and `ENV=dev`

### Handoff tool factory
- `make_handoff_tool(agent: Agent, parent_graph: bool = False) -> BaseTool`
  - Creates `transfer_to_{agent.name}` tool that returns a `Command` routing execution to the target agent node, appending a `ToolMessage` to the message history.

## Configuration/Dependencies

### Environment variables
- `POSTGRES_URL`
  - If set, `create_checkpointer()` attempts to use PostgreSQL-backed persistence via `langgraph.checkpoint.postgres.PostgresSaver` and `psycopg`.
  - Uses a shared connection/checkpointer across instances; closed at process exit (and via `close_shared_checkpointer()`).
- `ENV`
  - If `ENV == "dev"`:
    - Agent constructor randomizes `thread_id` with a UUID.
    - Adds `read_makefile` tool when the agent is its own supervisor (`state.supervisor_agent == self.name`).

### Runtime dependencies (non-exhaustive)
- LangChain core (`langchain_core.*`) for models/messages/tools.
- LangGraph (`langgraph.*`) for `StateGraph`, `Command`, checkpointers.
- `sse_starlette` for SSE streaming response (`EventSourceResponse`).
- Optional for PostgreSQL memory: `psycopg`, `langgraph.checkpoint.postgres`.

## Usage

### Minimal invocation (requires a LangChain `BaseChatModel` implementation)
```python
from langchain_core.language_models import BaseChatModel
from naas_abi_core.services.agent.Agent import Agent

# Provide a concrete BaseChatModel instance from your LangChain provider
chat_model: BaseChatModel = ...

agent = Agent(
    name="assistant",
    description="General assistant",
    chat_model=chat_model,
)

print(agent.invoke("What time is it in Europe/Paris?"))
```

### With a sub-agent (handoff tool is auto-created)
```python
from naas_abi_core.services.agent.Agent import Agent, AgentSharedState

chat_model = ...  # BaseChatModel

shared_state = AgentSharedState(supervisor_agent="supervisor")

math_agent = Agent(
    name="math",
    description="Handles math questions",
    chat_model=chat_model,
    state=AgentSharedState(supervisor_agent="supervisor"),
)

supervisor = Agent(
    name="supervisor",
    description="Routes to specialists",
    chat_model=chat_model,
    agents=[math_agent],
    state=shared_state,
)

print(supervisor.invoke("@math What is 2+2?"))
```

## Caveats
- Tool binding is attempted only if the model supports `.bind_tools(...)`; otherwise tools are not available (a warning is logged).
- `call_tools()` assumes tool names exist in `_tools_by_name`; missing tool names will raise a `KeyError`.
- `invoke()` extracts the final response by inspecting the last streamed chunk; if no messages are present it returns `""`.
- `stream_invoke()` uses a shared `Queue`; if reused across concurrent requests without isolating queues, events may interleave.
