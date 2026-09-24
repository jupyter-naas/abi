# A shared tool registry for composing agents from records and discovering tools at runtime

## Status

Proposed (implemented on `feat/1245-tool-registry`, issue #1245)

## Date

2026-09-23

## Context

Modules expose capabilities as tool classes (`tools/`, discovered by
`ModuleToolLoader` into `module.tools`) and as integration
`as_tools(configuration)` functions. Only agent factories consume them: to use
the GitHub tools, `GitHubAgent.New()` builds the integration configuration and
calls `as_tools` itself. That leaves three gaps.

1. An agent cannot exist without a Python file that assembles it.
2. Nothing can find a capability by what it does. An agent's tool set is fixed
   when it is built.
3. Programmatic creation has no single entry point that also reuses existing
   agents as sub-agents.

Constraints from the codebase: `ModelRegistryService` already provides
canonical model lookup and module registration; `VectorStoreService` provides
vector search; the base `Agent` accepts a model, prompt, tools and sub-agents,
and each HTTP request rebuilds the agent tree (`duplicate`) and restores
conversation state from the LangGraph checkpointer.

## Decision

### 1. `tool_registry` core service

A new hexagonal service (`services/tool_registry/`), always loaded like the
model registry and exempt from `ModuleDependencies`.

- **Ids** are `<namespace>/<name>@<version>`. The namespace is the publishing
  module's configured name, the name is the model-facing tool name, the
  version is `MAJOR[.MINOR[.PATCH]]` (bump the major version on an
  incompatible input change). References may omit the version to mean the
  highest published one.
- A tool is a **definition** (serialisable: description, input schema from
  the tool's `tool_call_schema`, output schema, owning module, tags, config
  requirements, required scopes) plus a **binding** (runtime factory,
  `create(context, config)`). Records, search results and anything crossing a
  process boundary only ever see definitions.
- **Publication**: after every module's `on_initialized`, the engine calls
  `module.publish_tools(publisher)` and publishes the result under the
  module's name, before `Engine.load()` returns. The default publishes
  `module.tools`; modules override it to publish integration factories
  (`publisher.add_factory(as_tools_fn, default_config=..., requirements=...)`).
  The GitHub module does this for its REST and GraphQL integrations, so its
  30 tools are usable without `GitHubAgent`. The registry is in memory and
  rebuilt at each boot; a module's publication replaces its previous set.
- **Resolution** merges the binding's module defaults with the caller's
  configuration, enforces the access policy and required configuration, then
  builds the tool. Credentials enter only as resolved values at this point;
  definitions never hold them.
- **Access** goes through an `IToolAccessPolicy` port. The default grants a
  tool when the caller's `ToolContext.scopes` cover the tool's
  `required_scopes`, for each of discover, enable and execute.

### 2. Semantic discovery

`search_tools(query, context, limit, min_score)` embeds the query and ranks
definitions by cosine similarity.

- **Embedding** comes from the model registry (the configured default
  embedding model, or `services.tool_registry.embedding_model`), through the
  `IToolEmbedderPort`. **Index** is an `IToolIndexPort`: in process memory by
  default, or the engine's `VectorStoreService` when one is loaded
  (`index: auto | memory | vector_store`). The registry owns the index.
  Tool ids are not valid point ids on every backend (a Qdrant server accepts
  only UUIDs and integers), so the vector-store index stores each entry under
  a UUID derived from the tool id and keeps the id in the entry's metadata.
  Scores are cosine similarities on every backend; `SqliteVecAdapter` now
  converts sqlite-vec's cosine distance so `min_score` means the same thing
  on SQLite and Qdrant.
- **Embedded text** is the name split into words, the description, the
  parameter names and descriptions, the tags and the last segment of the
  module path (`github`, not the `naas_abi_marketplace.applications.` prefix
  every marketplace tool shares).
- **Invalidation** is by fingerprint: `sha256(model_key + embedded text)`.
  New and changed definitions are embedded, unchanged ones skipped (also
  across restarts with a vector-store index), removed ones deleted, and a
  change of embedding model re-embeds everything (each model gets its own
  collection; the previous one is dropped).
- **Lifecycle**: indexing is lazy (first search or `sync_index()`), so boot
  never depends on an embedding provider. Without one, search fails with
  `ToolSearchUnavailableError`.
- **Ranking**: search over-fetches, drops hits the caller may not discover,
  and returns `limit` results. There is no default score threshold: against
  `nomic-embed-text`, correct top hits scored 0.43 to 0.67 and the runner-up
  was sometimes within 0.01, so a fixed cut-off would drop right answers.
- An optional `where` filter (an agent's allow-list, for instance) is applied
  inside that widening loop, so filtered-out hits never starve the limit.
- Discovery is separate from activation: search never builds, runs or grants
  a tool.

### 3. Composition (`agent_composer` service)

`AgentComposerService` builds agents from an `AgentSpec` record
(`kind: abi.agent/v1`: name, description, prompt, model reference, tool
bindings with config, sub-agent references, capabilities) or from Python
values (`create`, which accepts `BaseTool` instances and existing `Agent`
instances too). Both paths share one implementation.

- Record storage sits behind `IAgentSpecRepository` (in-memory and
  YAML/JSON file adapters). The composer never assumes a backend or Nexus.
- Record config values are literals or `{secret: NAME}` references resolved
  through `ISecretResolverPort` (engine `Secret` service). A value for a key a
  tool declares `secret` must be a reference.
- Composition produces the runtime's own objects: a plain `Agent`, with
  sub-agents wired as handoffs sharing one `AgentSharedState` whose
  supervisor is the composed agent, as for Python-defined supervisors.
  Existing instances are duplicated onto that state, never mutated.
- Record trees can nest (`lead -> manager -> worker`). The active agent's name
  is shared by the whole tree while each graph only holds its direct
  children, so `Agent.current_active_agent` now enters the child whose
  subtree holds the active agent, and an active agent outside the tree hands
  the turn back instead of targeting a missing node. This also covers nested
  Python-defined supervisors.
- Validation reports every problem found in one `AgentCompositionError`
  (unknown or denied tools, missing configuration or secrets, inline
  credentials, unknown models and records). Cycles raise
  `SubAgentCycleError`. A model-facing name claimed twice (by tools, default
  tools, handoffs or capability tools) raises `ToolNameCollisionError`; the
  runtime would otherwise keep one and silently drop the other.

### 4. Runtime capabilities (`CapabilityAgent`)

A record with `capabilities.enabled` composes a `CapabilityAgent`: an `Agent`
with `search_capabilities`, `enable_capability`, `disable_capability` and
`list_enabled_capabilities` tools.

- `Agent` gains three overridable hooks (`_chat_model_for_turn`,
  `_tool_for_call`, `_tool_names_for_turn`) that `call_model` and
  `call_tools` go through. The base behaviour is unchanged.
- **Scope and persistence**: the enabled set is the checkpointed state key
  `ABIAgentState.enabled_capabilities`, per agent name, with an
  operation-merging reducer. It is scoped to one conversation (thread),
  survives per-request agent reconstruction and restarts with a durable
  checkpointer, and never touches the shared registry.
- **Default state**: nothing is enabled. Static tools are always on and
  cannot be disabled. An allow-list (fnmatch over tool ids) and
  `max_enabled` bound what can be enabled.
- **Timing and in-flight calls**: a change applies from the next graph step.
  Calls the model already issued in the current step are dispatched against
  the tool set the step started with, so a call issued alongside its own
  `disable_capability` completes. The next model call no longer sees the
  tool, and a later call to it gets an explicit "not available" message.
- **Batches**: the calls of one step all receive the state the step started
  with, so each enable or disable is validated against that state plus the
  changes issued before it in the same step. Simultaneous enables cannot
  exceed `max_enabled` or claim one model-facing name.
- **Authorization**: checked on enable (`ENABLE`) and again whenever the tool
  is bound or dispatched (`EXECUTE`), for the caller of the current request.
  The agent's current allow-list is applied at the same points, so narrowing
  it revokes selections persisted in existing conversations. A restored
  selection whose name a static tool now owns is not bound (dispatch prefers
  the static tool), and dynamic tools are bound under their normalised name.
- **Binding cache**: bound models are cached by what the model is shown (name,
  description, argument schema), so switching versions or republishing a tool
  with a new schema rebinds it.

### 5. Contracts

New DTOs are Pydantic models (strict, `extra="forbid"`, frozen) serialisable
to JSON and YAML. Protobuf/Protovalidate contracts are being defined outside
this repository. When they land, these models map one to one onto messages:
the record `kind` field and the tool id version give the compatibility
handles, and existing tool schemas stay JSON Schema inside the definition's
`input_schema`. Everything runs in process for now, so no gRPC/DDS transport
is introduced; the NATS RPC work (`docs/specs/rfcs/20260910_…`) is the path
when registry calls cross processes.

## Consequences

- Any module's tools are addressable by a stable id and usable by agents that
  never import the module. Existing Python-defined agents, including their
  sub-agent behaviour, are unchanged.
- Records can live anywhere an `IAgentSpecRepository` adapter reaches. Nexus
  still stores agents as Python class references; wiring records into Nexus
  (list, create, run) is follow-up work.
- Boot does one extra pass (publication), with no network I/O: integration
  factories must build tools without calling their service. Embedding cost
  moves to the first search.
- Search quality depends on the embedding model and on tool descriptions.
  Vague descriptions now cost discoverability, which gives a reason to fix
  them.
- Fixed a latent bug on the way: `call_tools` injected the graph `state` next
  to the tool call instead of into its arguments, so every tool declaring
  `InjectedState` failed validation. Injection now applies only when `state`
  is hidden from the model; an ordinary `state` argument (such as
  `github_list_issues`'s issue filter) keeps the model's value.
- Out of scope: a visual agent builder, uploaded executable code, remote tool
  marketplaces, migrating existing agents.
