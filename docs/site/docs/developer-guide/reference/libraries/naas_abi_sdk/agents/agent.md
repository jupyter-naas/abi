# Agent

## What it is
An async, core-free SDK implementation of the `naas_abi_core`-style Agent behavior built on LangGraph:
- Runs a chat model in a tool-calling loop (model → tools → model).
- Persists conversation state per `thread_id` via a LangGraph checkpointer.
- Exposes async `invoke()` and `stream_invoke()` (SSE-like events) APIs.

## Public API

### Classes

- `AgentSharedState`
  - Holds conversation routing state.
  - Key responsibilities:
    - Tracks `thread_id` (selects the checkpointed thread).
    - Tracks `current_active_agent`, `supervisor_agent`, and a `requesting_help` flag.
    - Remembers active agent per thread and restores it when switching threads.
  - Public members:
    - `thread_id: str`
    - `set_thread_id(thread_id: str) -> None`
    - `current_active_agent: str | None`
    - `set_current_active_agent(agent_name: str | None) -> None`
    - `supervisor_agent: str | None`
    - `set_supervisor_agent(agent_name: str | None) -> None`
    - `requesting_help: bool`
    - `set_requesting_help(requesting_help: bool) -> None`

- `ABIAgentState` (`langgraph.graph.message.MessagesState`)
  - LangGraph state schema extension with:
    - `system_prompt: str`
    - `current_active_agent: str | None`
    - `supervisor_agent: str | None`

- `AgentConfiguration`
  - Callback and prompt configuration for an `Agent`.
  - Fields (all optional):
    - `on_tool_usage(message)`: called when an AI tool-call message is observed.
    - `on_tool_response(message)`: called when a tool response message is observed.
    - `on_ai_message(message, agent_name)`: called when a non-tool-call AI message is observed.
    - `on_agent_calling(agent_name)`: called when the agent is about to call the model.
    - `on_agent_routing(agent_name)`: defined but not actively used by this file’s control flow.
    - `system_prompt: str | Callable[[list[AnyMessage]], str]`
  - Methods:
    - `get_system_prompt(messages: list[AnyMessage]) -> str`

- `Agent` (inherits `ToolCallRepair`)
  - Core class that:
    - Binds a `BaseChatModel` to tools (when supported).
    - Builds and runs a LangGraph tool loop.
    - Provides async execution and an event stream API.
  - Constructor:
    - `Agent(name, description, chat_model, tools=None, agents=None, memory=None, state=None, configuration=None, enable_default_tools=True, markdown_pretty_display=False)`
    - Notes:
      - `agents` is not supported (raises `NotImplementedError` if provided).
      - `chat_model` may be a `BaseChatModel` or an object exposing `.model` as a `BaseChatModel`.
      - If `memory` is not provided, uses `InMemorySaver`.
  - Primary methods:
    - `async stream(prompt: str) -> AsyncIterator[Any]`: yields raw LangGraph stream chunks; also triggers configured callbacks.
    - `async invoke(prompt: str) -> str`: runs one turn; returns final assistant text.
    - `async stream_invoke(prompt: str) -> AsyncIterator[dict[str, str]]`: yields SSE-like events (`tool_usage`, `tool_response`, `ai_message`, `call_model`, `message`, `done`).
    - `reset() -> None`: increments `thread_id` (or sets a UUID if non-numeric).
    - `duplicate(agent_shared_state: AgentSharedState | None = None) -> Agent`: clones the agent with the same configuration/tools/model/checkpointer but a new `AgentSharedState`.
    - `as_handler() -> Any`: returns an `AgentHandler` wrapper (for `BaseModule.expose_agent` integration).
  - Hooks/callback setters:
    - Hook methods intended for subclass override:
      - `onHumanMessage(message) -> None`
      - `onAImessage(message, agent_name) -> None`
    - Callback setters:
      - `on_tool_usage(callback) -> None`
      - `on_tool_response(callback) -> None`
      - `on_ai_message(callback) -> None`
  - Properties:
    - `state: AgentSharedState`
    - `tools: list[BaseTool]` (same as `structured_tools`)
    - `structured_tools: list[BaseTool]`
    - `name: str`
    - `description: str`
    - `chat_model: BaseChatModel`
    - `configuration: AgentConfiguration`
    - `checkpointer: BaseCheckpointSaver` (read-only accessor)

### Functions

- `default_tools(agent: Agent) -> list[BaseTool]`
  - Provides a default `get_time_date(timezone="Europe/Paris")` tool.

- `can_bind_tools(chat_model: BaseChatModel) -> bool`
  - Probes whether the model supports `bind_tools(...)`.

- `Agent.prepare_tools(tools: list[Any]) -> list[BaseTool]` (static)
  - Normalizes tools:
    - Accepts `BaseTool` instances.
    - Also accepts objects with `as_tools()` producing tools.
    - Sanitizes names via `validate_name` and de-duplicates by name.

## Configuration/Dependencies

- Runtime dependencies used directly:
  - `langchain_core` (messages, tools, chat models, runnable config)
  - `langgraph` (StateGraph, checkpointers, message state)
- State persistence:
  - Uses a `BaseCheckpointSaver` (`InMemorySaver` by default).
  - Thread selection is via `RunnableConfig` `{"configurable": {"thread_id": ...}}`.
- Tool binding behavior:
  - If tools exist and `can_bind_tools(model)` is `False`, tools are not available (warning logged).
- Supervisor prompt:
  - If `AgentSharedState.supervisor_agent` is set to a non-empty name different from the agent’s name, the system prompt is wrapped with an additional “SUPERVISOR SYSTEM PROMPT” instruction block.

## Usage

Minimal async example (requires a LangChain `BaseChatModel` implementation, e.g. a provider-specific chat model):

```python
import asyncio
from naas_abi_sdk.agents.agent import Agent, AgentConfiguration, AgentSharedState

async def main(chat_model):
    agent = Agent(
        name="support_agent",
        description="Example agent",
        chat_model=chat_model,
        configuration=AgentConfiguration(),
        enable_default_tools=True,
    )

    text = await agent.invoke("What time is it in Europe/Paris?")
    print(text)

asyncio.run(main(chat_model))
```

Streaming SSE-like events:

```python
import asyncio
from naas_abi_sdk.agents.agent import Agent

async def main(chat_model):
    agent = Agent(name="a", description="d", chat_model=chat_model)
    async for evt in agent.stream_invoke("Tell me the date, then explain it briefly."):
        print(evt["event"], evt["data"])

asyncio.run(main(chat_model))
```

## Caveats

- `Agent.New(...)` is declared but not implemented (raises `NotImplementedError`).
- Passing `agents=` to the constructor is not supported (raises `NotImplementedError`).
- Tools require model support for `bind_tools`; otherwise, tools are silently disabled (with a warning).
- `markdown_pretty_display=True` triggers an additional model call to reformat the final output; failures fall back to the original response.
