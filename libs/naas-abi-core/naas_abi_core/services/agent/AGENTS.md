# Agent Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/agent/`. Canonical reference for agents working on the agent runtime itself.

## Purpose

Orchestration layer binding a chat model to tools and sub-agents. Handles:

- Intelligent tool selection (LangGraph state graph).
- Conversation memory via pluggable checkpointers (in-memory, SQLite, Postgres).
- Event streaming (SSE) for real-time invocation monitoring.
- Lazy initialization, connection pooling, parallel execution, caching.

## Key Classes

| Class | File | Role |
|---|---|---|
| `Agent` | `Agent.py` | Base orchestrator binding LLM ↔ tools/sub-agents; manages state, memory, graph |
| `CoordinatorAgent` | `CoordinatorAgent.py` | Strict supervisor: refuses direct answers, routes to intent-matched agent; extends `IntentAgent` |
| `IntentAgent` | `IntentAgent.py` | Intent-aware router; multi-stage filtering (intent / entity / relevance) |
| `OpencodeAgent` | `OpencodeAgent.py` | External AI-IDE session orchestrator (subprocess + SSE streaming) |
| `OpencodeSessionService` | `OpencodeSessionService.py` | Session/message/file-event persistence (SQLAlchemy async or in-memory) |
| `SqliteCheckpointSaver` | `SqliteCheckpointSaver.py` | SQLite-backed LangGraph checkpointer (survives restarts) |

## `Agent` Constructor

```python
Agent(
    name: str,
    description: str,
    chat_model: BaseChatModel | ChatModel,
    tools: list[Tool | BaseTool | Agent] = [],
    agents: list[Agent] = [],
    memory: BaseCheckpointSaver | None = None,
    state: AgentSharedState = AgentSharedState(),
    configuration: AgentConfiguration = AgentConfiguration(),
    event_queue: Queue | None = None,
    native_tools: list[dict] = [],
    enable_default_tools: bool = True,
    markdown_pretty_display: bool = False,
)
```

## Public API

```python
invoke(prompt) -> str                           # full sync turn
stream_invoke(prompt) -> Iterator[dict]         # SSE-formatted (event, data) chunks
stream(prompt)                                  # raw LangGraph streaming
duplicate(queue=None, agent_shared_state=None)  # independent copy with same config
as_api(router, route_name, ...)                 # mount invoke + stream on FastAPI router
as_tools(parent_graph=False) -> list[BaseTool]  # expose this agent as a tool for parents
build_graph(patcher=None)                       # construct LangGraph StateGraph
workflow -> StateGraph                          # compiled workflow
```

## Subclass Hooks

Override these on an agent that inherits from `Agent` to observe the
conversation. They are no-ops on the base class:

```python
onHumanMessage(message)              # a new human message entered the conversation
onAImessage(message, agent_name)     # a new AI message was emitted
```

Fire-and-forget by contract: the runtime discards whatever they return and
swallows (logs) any exception they raise, so a hook can never alter or break a
turn. They run inline on the streaming thread — keep them cheap, and hand slow
work off to a queue or thread yourself.

- `onHumanMessage` fires once per turn from `stream()` (and so from `invoke()` /
  `stream_invoke()`), before the message reaches the model.
- `onAImessage` fires for messages from this agent *and* its sub-agents;
  `agent_name` identifies the producer. Assistant messages that only carry tool
  calls do not count — those surface through the `on_tool_usage` callback.

Distinct from the `on_tool_usage` / `on_tool_response` / `on_ai_message`
*callback registration* methods, which take a callable and are set per-instance.

## Subdirectories

| Path | Contents |
|---|---|
| `beta/` | `IntentMapper.py` (embedding-based intent matching), `LocalModel.py`, `VectorStore.py` |
| `intents/` | `default_intents.py` — predefined `Intent` objects (name/desc match, supervisor help, …) |
| `ontologies/` | `modules/AgentEventOntology.py` — event dataclasses (`AgentUserMessageReceived`, `AgentAIMessageEmitted`, `AgentToolCalled`, `AgentToolResponded`, `AgentModelCalled`, `AgentRouted`, `AgentInvocationCompleted`); `classes/` auto-generated from RDF |
| `tools/` | `default_tools.py` (`get_time_date`, `get_current_active_agent`, `get_supervisor_agent`); `utils.py` (`can_bind_tools`) |

## Memory / Checkpointing

- `create_checkpointer()` auto-detects `POSTGRES_URL` → `PostgresSaver`, else `MemorySaver`.
- `SqliteCheckpointSaver` is available for file-backed persistence.
- Conversation state keyed by `thread_id` on `AgentSharedState`.

## Request Context (`context.py`)

Request-scoped `ContextVar`s used to tag emitted events:

```python
agent_user_id: ContextVar[str | None]       # set by auth middleware
agent_chat_id: ContextVar[str | None]       # falls back to AgentSharedState.thread_id
agent_workspace_id: ContextVar[str | None]  # workspace boundary
```

Propagate across async tasks / raw threads with `contextvars.copy_context()`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_hooks_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/IntentAgent_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/OpencodeAgent_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/OpencodeSessionService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/AgentMemory_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/test_agent_memory.py
```

Integration tests (require infra):

- `OpencodeAgent_integration_test.py` — running OpenCode IDE server.
- `test_postgres_integration.py` — running PostgreSQL.

## Adding a new agent type

1. Subclass `Agent` (or `IntentAgent`) and override `build_graph` only if you need a custom topology.
2. Register intents in `intents/default_intents.py` (or a domain-local module) if you want the router to dispatch to it.
3. Emit events via the dataclasses in `ontologies/modules/AgentEventOntology.py` — never invent ad-hoc event types.
4. Mirror the test pattern: `MyAgent_test.py` next to the implementation.
