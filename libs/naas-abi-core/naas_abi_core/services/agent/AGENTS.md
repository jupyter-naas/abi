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
| `DocumentCheckpointSaver` | `DocumentCheckpointSaver.py` | Engine agent memory in the Document Service (sync + async LangGraph API); `LegacyDocumentCheckpointReader` reads schema 1 |
| `migrate_checkpoints` | `CheckpointMigration.py` | One-shot copy of LangGraph threads into document schema 2 (from PostgresSaver or schema 1) |

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

`memory=None` (every module factory) calls `create_checkpointer()`, which returns,
in order: the engine's agent checkpointer when an engine is loaded, else a shared
`PostgresSaver` when `POSTGRES_URL` is set, else a new `MemorySaver`. An explicit
`memory=` always wins.

- `Engine.load()` binds `DocumentCheckpointSaver.for_engine(services.document)`
  through `engine.context.set_default_agent_checkpointer` before modules load;
  `shutdown()` unbinds it. It uses the engine's own document root, never the NATS
  client view (snapshots must not hit the broker payload limit). No document
  service, or no naas-abi-sdk (core `[nats]`), keeps the fallback above.
- Scope: every engine agent shares namespace `naas_abi_core.services.agent` and
  agent_id `engine.v1`, as they shared one PostgresSaver. A thread is keyed by
  `thread_id` (+ `checkpoint_ns`) whichever agent writes it. Load-bearing: Nexus
  and the OpenAI gateway rebuild agents per request and restore history and the
  active agent (`current_active_agent`) from the thread; sub-agents run in their
  supervisor's graph and checkpointer; a sub-agent invoked directly continues its
  supervisor's thread. Do not split the scope per agent or module without
  replacing that. SDK agents keep their own module namespace.
- Restored routing is checked against the running graph: `current_active_agent`
  and `supervisor_agent` from the thread are adopted only when they name this
  agent or one of its sub-agents, at any depth (a deeper one is reached through
  the direct sub-agent that holds it). A thread another agent left (Nexus keeps
  one thread per conversation when the user switches agents) starts with the
  agent now running. `Agent_routing_test.py` covers these cases.
- Documents are those of `naas_abi_sdk.langgraph.DocumentCheckpointSaver`
  (`naas_abi_sdk.langgraph_documents`, schema 2): change the schema there, for
  both savers; the savers only do I/O. Each step stores what changed (values
  content-addressed in blobs / items / parts), no document holds more than
  256 KiB of a value and reads fetch in batches of at most 2 MiB. Schema 1
  (`*_v1`, full snapshots) is still read; new writes are schema 2.
- A saver remembers what checkpoints it loaded or wrote reference
  (`KnownReferences`), so a put skips it. Keep the write order (parts, items,
  blobs, checkpoint last): a stored checkpoint must always be complete.
- Concurrent turns on one thread fork from the same parent; the newest checkpoint
  becomes the head (as with PostgresSaver). Checkpoint documents are create-only
  and values content-addressed, so nothing is overwritten. There is no run lease.
- Retention: `prune(thread_id, keep_last=N)` (`aprune` async, on both savers;
  rules in `langgraph_documents.kept_checkpoints`) keeps a thread's newest N
  root-namespace checkpoints and the subgraph steps they ran (a child namespace,
  one per sub-agent task, goes with the root checkpoint in its
  `metadata["parents"][""]`, so an interrupted sub-agent still resumes), and
  deletes older checkpoints (schema 2 and 1), their pending writes and every
  value document no kept checkpoint or write references. Values younger than
  `grace` (1 minute) are kept; nothing is deleted before the kept references
  are known, and checkpoints go first. Stop the thread's runs first, as for
  `delete_thread`: each turn re-reads its head (exact references), so a saver's
  remembered references never point at a pruned value. `abi agent
  prune-memory` (dry run; `--apply`; `--keep-last`, default 20; `--thread`;
  `--min-age`; `--namespace`/`--agent-id`) runs it over a scope.
- Secrets are never stored: values are serialized through
  `langgraph_documents.RedactingSerializer`, so a `SecretStr`/`SecretBytes`
  anywhere in state, writes, tool artifacts or metadata is stored (and read
  back) as one holding `REDACTED_SECRET`. Engine and SDK agent state holds no
  secret (messages, system prompt, routing); a graph that needs a credential
  across steps keeps its name and resolves it from the secret service when it
  uses it. Documents written before this keep their values until pruned or
  deleted.
- Migration into schema 2: `abi agent migrate-memory` (dry run; `--apply` to
  write; `--thread` to select; `--from postgres` with `$POSTGRES_URL` or
  `--source-url`, or `--from documents-v1`; `--namespace`/`--agent-id` for
  another scope). Idempotent. Stop the engines first: threads they served on
  documents before the copy are reported as `diverged`.
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
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_routing_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_hooks_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/IntentAgent_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/OpencodeAgent_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/OpencodeSessionService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/AgentMemory_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/test_agent_memory.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/DocumentCheckpointSaver_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/Agent_document_memory_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent/CheckpointMigration_test.py
```

`tests/checkpoint_saver__generic_test.py` is the saver contract, held to LangGraph's
`InMemorySaver`; `DocumentCheckpointSaver_test.py` runs it for the engine saver
(sync and async API) and the SDK saver on one document backend.
`Agent_document_memory_test.py` runs agent scenarios against today's shared saver
and the document saver across restarts; their transcripts must match.
`DocumentCheckpointSaver_test.py` also asserts flat bytes per turn over a 30-turn
chat and a 20 MB value under a capped transport; `tests/legacy_checkpoints.py`
writes schema 1 documents for the fallback and migration tests.

Integration tests (require infra):

- `OpencodeAgent_integration_test.py` — running OpenCode IDE server.
- `test_postgres_integration.py` — running PostgreSQL.

## Adding a new agent type

1. Subclass `Agent` (or `IntentAgent`) and override `build_graph` only if you need a custom topology.
2. Register intents in `intents/default_intents.py` (or a domain-local module) if you want the router to dispatch to it.
3. Emit events via the dataclasses in `ontologies/modules/AgentEventOntology.py` — never invent ad-hoc event types.
4. Mirror the test pattern: `MyAgent_test.py` next to the implementation.


## Remote hosting

RemoteAgentAdapter wraps an existing Agent/IntentAgent as an async SDK host
handler without importing the SDK. It duplicates per invocation with an isolated
thread ID and preserves SSE events. Cancellation must wait for the synchronous
worker to stop before the host releases its conversation claim. Cover both
invocation and cancellation in RemoteAgentAdapter_test.py; the full network
regression is examples/standalone_module/agent_integration_test.py.
