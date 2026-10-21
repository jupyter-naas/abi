# A shared tool registry for composing agents from records and discovering tools at runtime

## Status

Accepted. Covers modules that run in the engine, with NATS off and on (issue
#1245). Other processes read its catalog over NATS
(`docs/adr/20261021_tool-catalog-over-nats.md`), and SDK modules publish tools
that agents find and run over NATS (`docs/adr/20261022_remote-module-tools.md`);
the contract for remote execution of engine tools comes in a later step (see
"Contracts").

## Date

2026-09-23, updated 2026-10-21 for 3.0 (NATS mode, index ownership, Document
Service records, routing, the catalog over NATS).

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
  module's name, before module jobs start and before `Engine.load()` returns. The default publishes
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
  collection).
- **Embedding calls**: the registry resolves the embedding model once per sync
  or search (`IToolEmbedderPort.resolve()`; with a remote model registry each
  lookup is a round trip), and sends documents in batches of at most 1024,
  the most one `embed` call of the engine's model service accepts.
- **Lifecycle**: indexing is lazy (first search or `sync_index()`), so boot
  never depends on an embedding provider. Without one, search fails with
  `ToolSearchUnavailableError`.
- **Ranking**: search over-fetches, drops hits the caller may not discover
  (and hits it does not know: see "Index ownership"), and returns `limit`
  results. There is no default score threshold: against
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

- Record storage sits behind `IAgentSpecRepository`: in-memory, YAML/JSON
  files, and the Document Service (`DocumentAgentSpecRepositoryAdapter`, one
  document per record in the composer's own namespace). The Document Service
  is the shared backend: every engine process reads the same records, and with
  NATS the document facade carries the calls to the serving engine.
  `AgentComposerFactory.Documents(...)` builds a composer on it, and
  `FromEngine` falls back to it when no repository or directory is given. The
  adapter declares its collection on first use, so building a composer never
  reaches the service. The composer never assumes a backend or Nexus.
- Record config values are literals or `{secret: NAME}` references resolved
  through `ISecretResolverPort` (engine `Secret` service). A value for a key a
  tool declares `secret` must be a reference.
- Composition produces the runtime's own objects: a plain `Agent`, with
  sub-agents wired as handoffs sharing one `AgentSharedState` whose
  supervisor is the composed agent, as for Python-defined supervisors.
  Existing instances are duplicated onto that state, never mutated.
- Record trees can nest (`lead -> manager -> worker`). The active agent's name
  is shared by the whole tree while each graph only holds its direct
  children. `main` already routes a follow-up turn through the direct child
  that holds the active agent (`Agent._path_to`, `_in_tree`; this work keeps
  that fix, and adds nothing to it for downward routing). This also covers
  nested Python-defined supervisors.
- **Handoffs upward.** Every node of a tree shares `supervisor_agent`, the top
  agent, so `request_help` from `worker` names `lead`, not `manager`. A graph
  that does not hold the target but knows it holds the requester
  (`Agent._ancestors`, filled in when a parent builds its graph) routes the
  handoff to its parent graph instead of taking the turn. Only a target that
  is nowhere in the tree falls back to the agent that has the turn, which is
  the top agent.
- **Names identify agents.** The active agent, the supervisor, handoff targets
  and `enabled_capabilities` are all keyed by agent name for the whole tree,
  so two agents of one name cannot be told apart once the conversation moves.
  `compose` rejects such a tree (a record reused under two parents, a supplied
  `Agent` instance named like a record) with the paths of every occurrence.
  Python-defined trees keep first-match routing: name your agents apart.
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

### 5. NATS mode: one registry per process

With NATS, kernel services have an owner (the serving engine) and every module
reaches them through NATS facades (`docs/adr/20261015_repository-runs-on-nats.md`).
The tool registry is not one of them: it holds tool *bindings*, which are
Python callables built from the module's own code and cannot cross a process.
So each engine process has a registry of its own, filled by the modules it
loads, in every role:

| Role | Registry | Search backend |
|---|---|---|
| NATS off | the loaded service | embedder and vector store of the engine, shared index |
| serving | the owner's registry, handed to `module_services` like the model registry's owner | embedder and vector store through the NATS facades, shared index (sole writer) |
| standby | same, until it takes over | facades, in-memory index; shared index after the handover |
| client | created by `build_clients`, empty until the modules this engine loads publish | facades, in-memory index |

Publication and `resolve` are always local. The catalog reads (`get_definition`,
`list_definitions`, `availability`, `check_access`, `search_tools`) of a standby
or client engine also cover the serving engine's tools, read over NATS
(`abi.svc.tool_registry.v1`, `docs/adr/20261021_tool-catalog-over-nats.md`); the
serving engine answers them from its own registry.

`EngineProxy.services.tool_registry` and `AgentComposerFactory.FromEngine` work
in all of them; tools are published after `on_initialized` and before module
jobs start. The search backend is wired after `build()`, to the facades and not
to the owners, so the registry reaches the embedding model and the vector store
as any module does (RPC to the serving engine, with the same deadlines). The
registry's catalog is a NATS micro service of the serving engine, read only
(`tool_registry`). A role change at runtime (fenced, restored, handover) re-wires the
index and the catalog.

### 6. Index ownership

The vector-store index is the one part of the registry that can be shared by
processes, so it follows two rules.

- **Who writes.** Only the serving engine, or an engine with NATS off, writes
  the shared index. A standby or client engine uses an in-memory index
  (`ToolIndexRole.LOCAL`), which also keeps it from embedding into a store it
  does not own.
- **No process deletes what another may have written.** `search_tools` skips a
  hit it does not know, instead of deleting it. `prepare()` selects the
  prepared model's collection and drops nothing, so engines on different
  embedding models coexist. A sync removes only ids this registry indexed
  itself. Collections are matched strictly (`<prefix>__<16 hex>__<dim>`), so a
  prefix that extends another is not mistaken for it.
  Cleaning out leftovers (other models' collections, entries of tools no longer
  published) is `IToolIndexPort.collect_garbage`, run once per backend, only by
  a registry configured with `collect_leftovers`: the serving engine (the lease
  makes it the only writer) or a registry whose index is private. An engine
  without NATS never collects, because a one-off process with a narrower module
  set (`abi chat <module>`) may share its store: engines that publish different
  tools to one vector store use different `collection_prefix` values to keep
  their entries apart.

### 7. Contracts

New DTOs are Pydantic models (strict, `extra="forbid"`, frozen) serialisable
to JSON and YAML. The contracts come in steps, on the pattern of the remote
model registry (`docs/adr/20260924_remote-model-registry.md`), and kernel
services validate requests on the server side (there is no Protovalidate):

1. Done: `abi.tool_registry.v1`, the serving engine's catalog (list, get, search)
   for client engines and SDK modules
   (`docs/adr/20261021_tool-catalog-over-nats.md`). Its `ToolDefinition` message
   is the portable form of a definition, for the next two.
2. Done: tools published by remote SDK modules (`abi.tool.v1`, `ModuleDescriptor.tools`;
   `docs/adr/20261022_remote-module-tools.md`). A remote tool's configuration holds no
   secret: the composer rejects a `{secret: NAME}` binding on it.
3. Remote execution of engine tools, where the engine resolves the tool's
   configuration and secrets and enforces access.

The Pydantic models map one to one onto those messages: the record `kind` field and the tool id version
give the compatibility handles, and tool schemas stay JSON Schema inside the
definition's `input_schema`. Credentials never appear in definitions, search
results or records, which carry secret references only.

## Consequences

- Any module's tools are addressable by a stable id and usable by agents that
  never import the module. Existing Python-defined agents, including their
  sub-agent behaviour, are unchanged.
- Records can live anywhere an `IAgentSpecRepository` adapter reaches, the
  Document Service included, which every engine process and (through its
  facade) NATS reaches. Nexus still stores agents as Python class references;
  wiring records into Nexus (list, create, run) is follow-up work.
- A tool a module publishes is composable and runnable only in the process that
  loads the module until remote execution lands. A client engine or an SDK
  module can find the serving engine's tools (search, list, get); the serving
  engine does not see tools published only by a client engine. Records, which
  are shared, may name tools the current process does not have: composing fails
  with `ToolNotFoundError`, or `ToolResolutionError` when only the catalog has
  it.
- Each process embeds its own tool index when it is not the index's writer
  (standby, client): one `embed` call per 1024 tools on first search.
- A tree that reuses one agent name is rejected at composition, which breaks
  record sets that reused a leaf record under two parents. They must give each
  occurrence its own record.
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
