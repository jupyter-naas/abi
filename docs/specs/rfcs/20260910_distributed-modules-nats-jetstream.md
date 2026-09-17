# RFC: Distributed Modules over NATS/JetStream

- **Date:** 2026-09-10
- **Author:** Maxime Jublou
- **Status:** Draft

## Problem

The ABI `Engine` is one process. `Engine.load()` (`libs/naas-abi-core/naas_abi_core/engine/Engine.py`) reads
`config.yaml`, topologically sorts the declared `modules:` list (`EngineModuleLoader`), `importlib`-imports every
enabled module into the same interpreter, and wires one shared `IEngine.Services` registry (document, triple_store,
object_storage, bus, kv, model_registry, ...) that every module reaches through `EngineProxy`/`ServicesProxy`. That
buys real simplicity today — any module can call another module's code or a shared service as a plain Python call,
in the same stack frame, with no serialization or network cost — but it has hard, now-visible costs:

- **Dagster reloads the whole engine on almost every run.** `apps/dagster/dagster.py` calls `Engine().load()` at
  *module import time*: a full YAML parse + Jinja render, topological module sort, every module's `on_load()`
  (filesystem walks + imports of agents/workflows/pipelines/tools/models), and — unless
  `ABI_SKIP_ONTOLOGY_LOADING` is set — tens of thousands of ontology triples reinserted into the triple store.
  Dagster's default `multiprocess_executor` launches a fresh subprocess per op step, which re-imports that module,
  so this cost repeats per op, per run. Only four orchestrations (the X/Twitter ones) opted into
  `executor_def=dg.in_process_executor` specifically to dodge this, with an explicit comment about why
  (`XSearchRecentTweetsOrchestration.py:169-171`). Everything else pays full boot cost every run.
- **No independent scaling.** Every module shares one process's CPU/memory. If one module is resource-hungry (a
  heavy ingestion pipeline, a scraping workflow), the only lever today is scaling the *whole* engine, not that one
  module.
- **No independent deployability.** Shipping a change to one module means rebuilding/redeploying the whole engine
  process (API, Dagster code-server, Nexus — all one boot).
- **The messaging/coordination stack is already fragmented** into RabbitMQ (bus pub/sub + work queues) and Redis
  (the `KeyValueService`-backed distributed lock protecting Fuseki's MRSW write contention,
  `ApacheJenaTDB2.py:74-106`) — two special-purpose pieces bolted on independently, not one coherent platform
  capability.

We want a credible path to running modules as independent, network-attached processes that discover each other,
expose their domain services over RPC, and can be scaled per-module and deployed independently — without abandoning
hexagonal architecture. The business logic in `<Domain>Service` classes must stay unaware of whether it's being
called in-process or over the network; the network becomes a new **primary adapter** (how a domain is invoked) and,
where needed, a new **secondary adapter** (how a domain reaches another domain), exactly like swapping SQLite for
PostgreSQL is a secondary-adapter concern today.

**This is not theoretical — it's already the cause of real production performance problems.** Current production
instances are experiencing performance issues attributed directly to the in-process architecture: Dagster
struggling under exactly the reload cost described above. That's independent, live confirmation of this
document's original motivation, not a hypothetical future concern.

**A second target this design has to keep in view, not just the current single instance:** the product intends to
offer a hard-multi-tenant SaaS — a genuinely separate, fully isolated instance provisioned per paying customer
(triggered by a payment on a signup page), not a shared multi-tenant deployment. Hard tenancy means there is no
cross-tenant NATS/isolation design needed *within* this RFC — each tenant gets its own complete stack (own NATS,
own Postgres, own everything this document describes), so the isolation boundary is structural, not a
subject-scoping problem this document has to solve. What hard tenancy *does* depend on, directly, is this RFC's
Stage 1: whether one instance of the stack performs acceptably on modest, cheap-to-run hardware is exactly what
determines whether per-tenant unit economics work at all, and that's the same question as "does Stage 1 actually
fix the Dagster reload cost" — the same fix serves both the current production pain and the future SaaS's cost
structure. Provisioning N copies of this stack on demand (the control plane, billing, and orchestration around
*that*) is a distinct, dependent piece of work and is intentionally out of scope here — see the scope note below.

**Scope note.** This RFC is deliberately scoped to *distributing modules within the current Python engine* — it
does not evaluate or propose replacing the engine implementation itself, and no comparison to any other runtime is
in scope here. The reasoning for that ordering: today the contracts between modules and services
(`ModuleDependencies`, `IEngine.Services`, the hexagonal ports) are implicit and Python-specific — enforced by
what happens to be importable in one interpreter, not by anything written down. The moment two pieces talk over
NATS RPC instead of a shared call stack, those contracts have to become explicit, versioned, and
language-agnostic on the wire, because a network boundary won't tolerate "just import the other side's class" the
way one process does. Once most modules speak that way, a much bigger question — whether the engine underneath
those contracts should eventually be replaced — gets *cheaper* to answer later: the answer only requires a new
implementation that speaks the already-sealed contract, not a rewrite of every module's calling convention. That
question is intentionally out of scope for this document; sealing the contracts is the prerequisite, not a
side effect.

Same boundary applies to the hard-tenancy SaaS target above: this document is about what one instance of the stack
looks like and how efficiently it runs, not about the control plane that would provision, bill for, and tear down
N copies of it per paying customer. That's real, dependent work — likely its own RFC once this one's Stage 1 is
proven — but it's a different decision space (orchestration, billing, lifecycle automation) layered on top of this
one, not a change to the module/service architecture itself.

## Proposal

### 1. Where we start from

Three things about the current design are worth keeping in mind because they are either the biggest asset or the
biggest obstacle for this migration, depending on the piece:

- **The bus is already a hexagonal port** (`services/bus/BusPorts.py::IBusAdapter`), with RabbitMQ and an in-process
  SQLite adapter as interchangeable secondary adapters (`EngineConfiguration_BusService.py`, discriminated on
  `adapter: Literal["rabbitmq", "python_queue", "custom"]`). Adding `adapter: "nats_jetstream"` is a same-shaped,
  low-risk change — this is our best low-risk entry point.
- **Every service reaches every other service only through `EngineProxy.services.<x>` or
  `ABIModule.get_instance().engine.services.<x>`** — never a raw import of a concrete adapter class. This
  indirection (`engine/EngineProxy.py`) is exactly the seam where a local `TripleStoreService` object could be
  swapped for a NATS-RPC stub implementing the same port, entirely as a config-time decision
  (`EngineConfiguration_<X>Service.py`'s `adapter: Literal[...]` union already supports a `"custom"` dynamic-import
  branch for this purpose).
- **But module-to-module communication is not similarly mediated.** `ModuleDependencies.services` gates access to
  *services*, but modules also reach other *modules* directly — `BaseModule.get_instance()` (a process-global
  singleton table keyed by class) and direct imports for `isinstance` checks (e.g.
  `PersonnelAgent.py:76-90` importing `TemplatableSparqlQueryABIModule` to assert on the live object). None of that
  survives a process boundary as-is; it has to become an RPC contract.

### 2. Target architecture: NATS + JetStream as the fabric

Replace three separate things — the ad hoc "engine has everything loaded, import whatever you need" model, the
RabbitMQ bus, and (eventually) the Redis distributed lock — with one NATS cluster doing four jobs:

| Today | NATS/JetStream equivalent |
|---|---|
| `Engine.load()` importing modules from local Python paths | Modules run as independent processes/containers; each connects to NATS on boot and **registers itself** (subject + JetStream KV entry) instead of being `importlib`-imported by a coordinator |
| `EngineProxy.services.<x>` (in-process call) | NATS **request-reply** RPC to a subject like `abi.svc.<domain>.<method>`, fronted by a new primary adapter per domain |
| `BaseModule.get_instance()` / direct cross-module import | NATS request-reply to the owning module's registered subject, using a serializable request/response contract instead of a live Python object |
| RabbitMQ (`IBusAdapter` secondary adapter) | A `NATSJetStreamAdapter` implementing the *same* `IBusAdapter` port — JetStream streams for the durable work-queue methods (`enqueue`/`dequeue`), core NATS subjects for the ephemeral pub/sub methods (`publish`/`subscribe`) |
| Redis-backed `KeyValueService.lock()` for Fuseki MRSW | Optional: JetStream KV's atomic `create`/`update`-with-revision gives compare-and-swap semantics that can back the same `KeyValueService` port — not urgent, Redis keeps working, but it means one fewer piece of infrastructure long-term |
| One process's module-dependency topological sort (`EngineModuleLoader.__topological_sort`) | Runtime dependency *discovery*: a module waits on NATS (with timeout/backoff) for the modules/services it depends on to announce themselves, instead of assuming they're already `import`-able |

Why NATS/JetStream specifically, rather than "RabbitMQ + gRPC + etcd/Consul": one system gives us pub/sub, durable
work queues, request-reply RPC, a KV store (for registration/discovery/locks), and an object store (for small-to-
medium binary payloads), all with the same client library and the same operational footprint. That directly
replaces RabbitMQ *and* narrows what Redis is needed for, rather than adding a fourth piece of infrastructure on top
of the two we already run.

### 3. Mapping onto hexagonal architecture

The repo already has a base class every exposable component extends: `Expose`
(`libs/naas-abi-core/naas_abi_core/utils/Expose.py`), with `as_tools()` (LangChain tool, the default primary
adapter) and `as_api()` (REST, mounted by `apps/api/api.py`'s `_load_runtime_routes`). Nexus's own domains go
further and give each domain a `services/<domain>/adapters/primary/<domain>__primary_adapter__FastAPI.py`, and at
least one domain (`chat`) already has *multiple* primary adapters side by side
(`chat__primary_adapter__FastAPI.py`, `chat__primary_adapter__streaming.py`, `chat__primary_adapter__export.py`).
That's the precedent to extend, not replace:

- Add `Expose.as_nats(nc, subject_prefix)` next to `as_api()` — mounts a NATS request-reply subscriber that decodes
  a Protobuf-encoded request, calls the same underlying method `as_api()` would have called via HTTP, and encodes
  a Protobuf response (see "Decisions locked in" below).
- For kernel domains (document, triple_store, object_storage, ...), add
  `services/<domain>/adapters/primary/<domain>__primary_adapter__NATS.py`, mirroring Nexus's naming convention.
  It wraps the *same* `<Domain>Service` object every in-process consumer already uses — it is not a second
  implementation of the domain, just a second way to reach the first one.
- On the secondary-adapter/config side, give `EngineConfiguration_<X>Service.py` a new discriminated-union member —
  e.g. `document_adapter: { adapter: "nats_rpc", config: { subject: "abi.svc.document" } }` — so that, exactly like
  choosing `sqlite` vs `postgresql` today, an environment can decide a given service is *local* (loaded in-process)
  or *remote* (a stub that speaks NATS RPC to wherever the real implementation lives). This means the same
  `config.yaml` mechanism used for storage backend choice becomes the mechanism for topology choice too — no new
  concept for operators to learn.
- Extend the existing **generic adapter test** pattern (`tests/<domain>__secondary_adapter__generic_test.py`, an
  `ABC` with an abstract `adapter` fixture that every secondary-adapter implementation must pass) with an analogous
  **generic primary-adapter test** — a NATS-RPC primary adapter for `document`, say, must satisfy the same
  request/response/error-mapping contract as the FastAPI one, independent of transport.

This keeps the invariant the user asked for explicitly: business logic stays technology-unaware. `DocumentService`
never learns NATS exists; only its new primary adapter does.

### 4. Module registration & discovery protocol (sketch)

A minimal, JetStream-KV-backed discovery mechanism, similar in spirit to Consul/etcd service registration but
riding on infrastructure we're already adopting for RPC:

- On boot, a module process connects to NATS and publishes a **registration record** (a Protobuf message) into a
  JetStream KV bucket (e.g. `abi.modules.<module_name>` → `{instance_id, version, capabilities: [agents/workflows/
  pipelines/tools it exposes], services_required: [...], subject_prefix, started_at}`), with a short TTL, refreshed
  by a heartbeat. It then fetches its own scoped secrets from the engine over an authenticated NATS request-reply
  call before doing anything else (see "Decisions locked in" below).
  KV-with-TTL gives us "deregister on crash" for free — a dead instance's key simply expires — which is exactly the
  failure mode `BaseModule.on_unloaded()` was defined for but never wired up (`module/Module.py:221-222`, dead
  code today).
- A module that depends on another module's service (today expressed as `ModuleDependencies.services`/`.modules`)
  watches the KV bucket for that dependency's key, with a timeout and backoff, instead of assuming
  `importlib.import_module` will just work. This is the runtime analog of `EngineModuleLoader`'s topological sort
  — but resolved live, across processes, rather than once, in one interpreter.
- Scaling a module to N replicas means N processes registering the same `module_name`/`capabilities` under
  **the same NATS queue group**. NATS's queue-group semantics do the load balancing: a request to
  `abi.svc.document.put` is delivered to exactly one member of the group, round-robin, with no code change needed
  in the caller — this is the mechanism that satisfies the user's stated scaling target directly. The module code
  only needs to know it *might* be one of several replicas (e.g. don't assume in-memory local state is authoritative
  — largely already true for the kernel domains, which are designed to be swappable across storage backends and are
  mostly stateless besides the backing store).
- **Build the actual RPC endpoints on NATS's own Services framework** (the "micro" API in `nats.go`, standardized
  across NATS clients), not hand-rolled raw subscriptions. It gives structured endpoint registration, queue-group
  load balancing out of the box, built-in discovery/monitoring (`$SRV.PING`/`$SRV.INFO`/`$SRV.STATS`), and
  structured error headers on replies — all things this RFC would otherwise have to build by hand. The JetStream KV
  registration record above and the Services framework are complementary, not competing: the KV record is the
  durable, richly-queryable directory (capabilities, schema, dependencies — things you want to read without every
  instance having to be alive and answering a PING right now); the Services framework is the live RPC endpoint
  technology those capabilities actually run on.
- **One subtlety worth being precise about**: the Services framework's `version` field is discovery/monitoring
  metadata, not a routing mechanism. Two instances registered under the same *subject* with different `version`
  strings still land in the same queue group and get load-balanced together — a v1-contract caller could be routed
  to a v2 instance with no error, just a broken call. Safety for an actual breaking contract change has to come
  from the subject itself, not the version field — see "Protobuf contract shapes" below for the concrete mechanism
  (versioned subjects, side by side, using the same "Coexistence" pattern already established for extracted
  modules).

### Coexistence: extracted and in-process modules, side by side

Nothing about this migration should be designed as if a flag day were coming. At any point during the rollout,
some modules are still classic in-process members of `config.yaml`'s `modules:` list, imported by
`EngineModuleLoader` exactly as today, while others have been extracted to their own NATS-registered process. Both
have to work, together, in the same running deployment — this is a supported steady state to live in for as long
as needed, not a transient mess to rush through.

The mechanism that makes that possible without touching every call site: `EngineProxy.modules[<name>]` and
`EngineProxy.services.<x>` become the place where "local or remote" is decided, per module or service, from
`config.yaml` — exactly like `EngineConfiguration_<X>Service.py`'s existing `adapter: Literal[...]` choice already
does for storage backends. For a module/service still configured as in-process, the proxy hands back the real
local object, unchanged from today. For one configured as extracted, the proxy hands back a **stub object
implementing the same interface**, generated from the same Protobuf manifest a genuinely external NATS client
would use, that forwards every call over NATS RPC instead. Callers — `PersonnelAgent.get_sparql_tools`,
`AbiAgent`, Nexus resolvers, anything using `BaseModule.get_instance()` or `EngineProxy.services.<x>` — don't
change at all.

This is also what reconciles "cross-module calls always go through NATS, no in-process shortcut" (a decision
below) with "nothing breaks mid-migration": that rule applies once a module has been extracted — an extracted
module is never reachable except over NATS, even from a caller that happens to share its host — but a module that
hasn't been extracted yet keeps using today's direct in-process mechanism with its still-in-process siblings,
because nothing has changed for it yet. The rule isn't violated during the transition; it just doesn't apply to
pairs of modules that are both still on the old side of the line.

It also gives the first real extraction (rollout step 3, §8) a concrete rollback story for free: reverting a
module from "extracted" back to "in-process" is a `config.yaml` change (move it back into the local `modules:`
list, drop its remote config) and a redeploy — not a rewrite. Worth deliberately keeping a freshly-extracted
module's in-process code path intact and tested for at least one stabilization period after the cutover,
specifically so rollback stays cheap while confidence in its NATS path is still being built.

### Agents: the sub-agent composition problem

This deserves its own treatment because it's the one place the "business logic never learns the network exists"
premise (Problem, above) genuinely strains — and it isn't a rare case to design for later. `AbiAgent`
(`libs/naas-abi/naas_abi/agents/AbiAgent.py::get_agents`, lines 169-215) already walks **every loaded module** and
instantiates **every agent class in every module** as its own sub-agents, today, sharing one `AgentSharedState`
and one checkpointer across the whole tree. "An agent with sub-agents from another module" isn't an edge case —
it's the primary mechanism the entire chat experience already runs on.

**What actually happens today, mechanically** (`Agent.build_graph`, `Agent.py:823-848`): a sub-agent isn't called
like a function, or even a tool, by default — its **compiled LangGraph is embedded as a node inside the parent's
own `StateGraph`** (`graph.add_node(agent._name, agent.graph)`), sharing one `AgentSharedState` and one
checkpointer, with handoff routing between agents (`current_active_agent`/`supervisor_agent`) tracked as state that
persists across HTTP turns via that shared checkpointer. `Agent.as_tools()` (lines 820-821) already offers a
looser alternative — `make_handoff_tool(agent=self, ...)`, a LangChain tool the LLM can invoke to hand off — but
`AbiAgent` builds its whole tree via the tighter, graph-embedding path, not the tool-handoff one.

**Why that specific mechanism can't cross a process boundary transparently:** embedding a compiled graph as a node
requires the actual `CompiledGraph` Python object in the caller's process — there is no way to hand a remote
process's in-memory graph object across NATS the way a Protobuf message carries a `DocumentPut` request. Shared,
mutable `AgentSharedState`/checkpointer doesn't survive two processes either. This is a different shape of problem
than `DocumentService.put()`: that's one stateless call; a sub-agent conversation is a long-lived, multi-turn,
LLM-in-the-loop, streaming session.

**Resolution — two tiers, using the "Coexistence" mechanism above rather than replacing it:**

- **Same-process sub-agents** (the common case, unaffected): `build_graph`'s graph-embedding stays exactly as it
  is. Nothing changes for two agents that are both still in-process, same as any other pair of not-yet-extracted
  modules.
- **Cross-network sub-agents**: when `EngineProxy` resolves a sub-agent reference to an *extracted* module, it
  hands back a **remote-handoff proxy** — an object satisfying the same shape `make_handoff_tool` already expects,
  not a full graph-embeddable `Agent`. Invoking it doesn't add a subgraph node; it opens a NATS session against the
  remote module's own graph, keyed by the conversation's existing `thread_id`, the same identifier checkpointing
  already uses today. Streaming (today's SSE `/stream-completion`, `Agent.as_api`) maps onto a NATS subject the
  caller subscribes to for the duration of that turn, mirroring the existing HTTP SSE behavior instead of
  collapsing to one request/response.
- **Checkpointing must not fragment per module — it has to unify over NATS, not just the RPC calls.**
  `create_checkpointer()` (`Agent.py:155-247`) shows today's real invariant precisely: when `POSTGRES_URL` is set,
  every agent in one process already shares a single process-wide `PostgresSaver` connection (a module-level
  singleton, `_shared_checkpointer`) — one unified store for the whole embedded tree, not one store per agent.
  Falling back to "each extracted module opens its own direct connection to that same shared Postgres" would be a
  real regression, not a neutral default: it hands every module process raw database credentials, bypassing the
  NATS/JWT authorization boundary entirely (a leaked module credential could read or rewrite any thread's history,
  not just its own), and it fragments what's currently one consistent, queryable conversation history across N
  independently-connected processes. The fix: promote conversation-state persistence to its own **new centralized
  singleton service reached over NATS**, in the same category as `triple_store`/`document`/`object_storage` (see
  "Decisions locked in"). Its secondary adapter is exactly the Postgres/SQLite logic `create_checkpointer()`
  already has — nothing to reinvent, only relocate behind a NATS primary adapter — called by every agent process
  (in-process or extracted) through a small `NATSCheckpointSaver(BaseCheckpointSaver)` that implements LangGraph's
  own checkpointer interface (`get_tuple`/`put`/`put_writes`/`list`) by forwarding to that service. Because
  `BaseCheckpointSaver` is already a narrow interface LangGraph defines, not something ABI has to design from
  scratch, this is one of the *smaller* new primary adapters in this RFC, not a bigger one. This is what actually
  keeps `thread_id` a reliable continuation key across the whole distributed tree: every agent, local or extracted,
  reads and writes through the same one logical store, exactly matching today's shared-`PostgresSaver` behavior —
  not per-module islands of history.
- **From the composing module's point of view, this is exactly the transparency asked for**: `AbiAgent.get_agents()`
  doesn't need to know or care that a given agent class now lives in another container — it still gets back
  something `Agent`-shaped it can add to its tree. Which of the two tiers that object actually is gets decided
  once, at resolution time, never by the calling code.

**Developer ergonomics — automatic by default, with an escape hatch.** Nothing about any of this should require a
module author to write NATS code. The codebase already draws exactly this line for REST: `Expose.as_api()` has a
sensible generic default, and a subclass *can* override it for custom routing needs, but almost none do. `as_nats()`
follows the identical convention:

- **Default**: the manifest (challenge 1 below) and the wire contract are auto-derived by reflecting on the class —
  the same pydantic configs (`AgentConfiguration`, workflow/pipeline parameter models) already backing `as_api()`
  request bodies today already carry enough type information to generate the Protobuf schema and the NATS
  subscriber without the author writing anything. A module author builds an `Agent`/`Workflow`/`Pipeline`/`Tool`
  subclass exactly as they do today; whether it ends up reachable over NATS, and whether its declared sub-agents
  turn out to be local objects or remote-handoff proxies, is decided entirely by `config.yaml` and the `EngineProxy`
  resolution above — invisible to the class itself.
- **Escape hatch**: a module that genuinely needs control — custom subject partitioning, a hand-written Protobuf
  contract instead of the derived one, custom streaming behavior — overrides `as_nats()` directly, exactly like a
  class can already override `as_api()` today. Not a new concept for this codebase, just the existing one extended
  to a second transport.

### Decisions locked in

The following were open questions in an earlier draft of this RFC; they're now settled, and the rest of this
document assumes them.

- **`CallContext` carries end-user identity (`principal_id`/`workspace_id`/`tenant_id`) starting in Stage 1, even
  though nothing enforces it yet.** Service-to-service auth (the JWT below) and end-user authorization (which
  human may see which data — a pre-existing gap, not one this migration introduces, see challenge 6) are different
  problems; real enforcement of the second one waits for a concrete tenant boundary to enforce against, but the
  wire format is cheap to future-proof now, while the envelope is being designed anyway.

  **Target shape for that later enforcement, decided in direction though not yet built**: ARN-style scopes (a
  structured resource identifier, à la AWS ARNs, giving finest-grained permission matching — e.g. a principal's
  granted scopes checked against the specific resource an operation touches), and — the important part — **checked
  in the domain (`<Domain>Service`), never in a primary adapter**. Doing it in the domain means one correct
  implementation instead of one per adapter (`as_api`, `as_nats`, `as_tools`, and whatever comes later), and it's
  the only way "checked the same way whether you call in-process or over NATS" is actually true rather than
  aspirational. The mechanism that makes that concrete: propagate the ARN/principal via a `contextvars.ContextVar`,
  not an explicit parameter threaded through every port method. Each primary adapter's only auth-related job
  becomes "populate that one context variable from whatever this transport gave me" — deserialize `CallContext`
  for NATS, read the request for REST, already-set-by-the-immediate-caller for a genuine in-process call — and the
  domain's authz check reads the same variable regardless of who populated it. `CallContext`'s
  `principal_id`/`workspace_id`/`tenant_id` above is exactly the wire-level carrier this needs for the NATS case;
  building the actual ARN scope model, the policy-matching logic, and the `contextvars` plumbing is deliberately
  not part of Stage 1 — noted here so the direction is decided, not so it gets built now.
- **Stage 1's JWT is deliberately minimal, not the full Stage 2 design.** Stage 1 has no extracted or untrusted
  module — every NATS client is first-party infrastructure already under your control (the API process, Dagster).
  Ship HS256 JWTs signed with one shared secret (delivered like any other secret today, via `SecretService`/
  `config.yaml` — no new distribution problem, since nothing is a separate process yet), issued once per known
  caller identity (`"api"`, `"dagster"`) with no fine-grained per-module claims, since there's nothing yet to scope
  *between*. Don't build the richer claims-to-`ModuleDependencies` mapping into Stage 1's primary adapters — that's
  genuinely Stage 2 work, once a caller can be something other than trusted first-party infrastructure.
- **Stage 1's Protobuf contracts live inside `naas-abi-core`** (e.g. `naas_abi_core/proto/`), not a standalone
  package — the only consumers are kernel services that already live there. Generate Python stubs with `protoc`
  directly via `grpcio-tools` (`python -m grpc_tools.protoc`), not `buf` — one more tool isn't worth it for a
  small, single-package proto set with no cross-repo compatibility story to enforce yet. Extract to a standalone
  `naas-abi-proto` package (and reconsider `buf`) only once Stage 2 needs marketplace modules to depend on the
  schema independent of `naas-abi-core`'s own release cadence.
- **The migration itself is additive and reversible — never a flag day.** Every phase of the rollout (§8) has to
  leave the system fully working via the existing in-process path; the NATS path is layered on top and cut over
  module by module, never switched globally. See "Coexistence" above for the concrete mechanism (a local-or-remote
  proxy at the `EngineProxy` boundary) that makes this possible without rewriting every call site, and gives each
  individual module cutover a cheap rollback.
- **Sub-agent composition is two-tier, not a single proxy pattern.** Same-process sub-agents keep today's
  graph-embedding mechanism unchanged; a sub-agent in an extracted module becomes a remote-handoff proxy over a
  stateful, streamable NATS session keyed by the conversation's existing `thread_id`. See "Agents: the sub-agent
  composition problem" above — this was the single largest gap between "modules never learn the network exists"
  and what `AbiAgent` actually does today (graph-embed every agent in every module into one shared-state tree).
- **Module authors don't write networking code by default; an escape hatch exists for the cases that need it.**
  `as_nats()` mirrors `as_api()`'s existing default-with-override convention: the manifest and wire contract are
  reflected off the class automatically, and a module is built exactly as it is today regardless of whether it
  ends up local or extracted. Overriding `as_nats()` directly is available, same as overriding `as_api()` is today,
  for the module that genuinely needs custom control.
- **Serialization: Protobuf**, not JSON. RPC request/response payloads, the module-capability manifest (challenge
  1 below), and the JetStream KV registration record (§4) all become `.proto`-defined messages. This needs a schema
  package every module can depend on independent of language — likely a new small package (e.g. `naas-abi-proto`)
  holding the `.proto` sources plus generated Python stubs, versioned separately from `naas-abi-core` so a schema
  change doesn't force a lockstep release of every module. Schema-evolution discipline (additive fields only,
  never renumber or remove) becomes a hard constraint the moment two module versions run against different
  contract versions — worth writing down explicitly once Phase 2 starts. This deliberately borrows gRPC's best
  idea (typed, schema'd, backward-compatible wire messages) without adopting gRPC's transport (HTTP/2, its own
  service-mesh story) — NATS stays the transport, Protobuf is just the payload encoding riding on top of it. See
  "Protobuf contract shapes" below for the concrete message design, including how a module extends its own
  contract without needing the shared schema to change.
- **Auth: a shared JWT, for now.** Simpler than full NATS NKey/decentralized-JWT account scoping, and enough to
  carry Phase 1-3. The JWT should still carry per-module claims mapping to today's `ModuleDependencies` (so a
  module's token only authorizes the subjects/services it actually declared), issued by the engine at module
  registration — this preserves the *intent* of `ServicesProxy.__ensure_access` as a real network boundary instead
  of an in-process check, even though the mechanism is simpler than full NATS-native account isolation. Revisit if
  a module ever needs to run genuinely untrusted (an unreviewed marketplace module, say).
- **Cross-module calls go through NATS too — no in-process shortcut, even for co-located modules.** This settles
  challenge 2 below unambiguously: `BaseModule.get_instance()` and direct imports are fully retired as a calling
  convention, not just deprecated for the modules that happen to be containerized. Why this matters beyond
  tidiness: the whole point of this RFC (per the scope note above) is sealing one explicit, versioned contract that
  a future engine swap could sit behind. A privileged in-process fast path for "modules that happen to be
  co-located" would leave a second, undocumented calling convention alive — exactly the implicit coupling this
  migration exists to remove. The cost is that every module-to-module call pays a network round trip even when it
  didn't strictly have to; that's an accepted trade-off, not an oversight.
- **Secrets are delivered over NATS from the engine, not baked into each container's environment.** The engine
  keeps owning `SecretService` and resolving `{{ secret.X }}` placeholders exactly as it does today — that part
  doesn't move. What changes: instead of every process independently Jinja-rendering the whole `config.yaml`
  (today's model — see challenge 7 below), each module fetches only *its own* resolved config/secrets from the
  engine at boot over an authenticated NATS request-reply call (e.g. `abi.engine.secrets.request`, scoped by the
  module's JWT claims to the `config:` block that module actually declared — the engine already knows this
  mapping today, it's just not currently used to gate anything). A companion pub/sub subject
  (`abi.engine.secrets.rotated.<module_name>`) can notify a running module to re-fetch when a secret rotates,
  which is a real improvement over today, where rotating a secret means restarting whatever process read the YAML.
  One thing this doesn't remove: a module still needs *some* minimal bootstrap credential (at least its own
  JWT/identity) to authenticate to NATS in the first place, and that one has to arrive the conventional way — an
  env var or mounted file at container start — since NATS can't deliver the credential needed to reach NATS.
  Everything downstream of that first credential can flow through NATS.
- **`triple_store`/`document`/`object_storage`, and now also agent conversation-state/checkpointing, stay
  centralized singleton services reached over NATS** — not horizontally scaled or sharded themselves. Checkpointing
  joins this list precisely because it's the same shape of problem: today's `create_checkpointer()` already gives
  every agent in a process one shared Postgres connection, and that unified-store property has to survive the
  migration rather than fragment per module (see "Agents: the sub-agent composition problem" above). This also
  substantially simplifies challenge 4 below (ontology
  bootstrap ownership): since there's exactly one `triple_store` service instance behind its NATS subject (not N
  queue-group replicas racing each other), there's no leader-election problem for *who* loads a given module's
  ontology — it's simply whichever one process is running that service, same as today. What still needs a small
  protocol change: modules push their ontology files to the triple store over a NATS RPC call instead of an
  in-process `insert()`, and something still needs to track "has module X's ontology already been loaded" across
  restarts of the modules that depend on it — worth a JetStream KV entry, just without the multi-instance race that
  made it hard.

### Protobuf contract shapes

There are two different problems here, and treating them the same is what makes challenge 1 below look harder
than it is:

- **Kernel domain services** (`document`, `triple_store`, `object_storage`, `checkpoint`) are a small, stable,
  hand-designed set. Their Python ports already have fixed method signatures — this is normal API design, not
  auto-derivation, and there are only a handful of them.
- **Arbitrary module components** (Agent/Workflow/Pipeline/Tool — 100+ classes, including third-party marketplace
  ones) are where "reflect on an arbitrary Python class and generate a stable message type" genuinely doesn't
  work: Python's typing is looser than Protobuf's, and nobody is hand-annotating 100+ classes.

For the second category, don't generate a distinct Protobuf message type per class. Use one small, generic,
fully-typed envelope whose payload field is `google.protobuf.Struct` — Protobuf's own built-in dynamic/JSON-shaped
value type. The envelope (routing, call id, tracing, streaming, error info) stays typed; only the business payload
is dynamic, validated against a JSON-Schema-shaped description published in the manifest (which is directly useful
for LLM tool-calling schemas too, since those need JSON Schema anyway).

```protobuf
// Registration (hand-designed, stable)
message ModuleRegistration {
  string module_name = 1;
  string instance_id = 2;
  string version = 3;
  string subject_prefix = 4;
  repeated ComponentDescriptor components = 5;
  repeated string services_required = 6;   // -> ModuleDependencies.services
  repeated string modules_required = 7;    // -> ModuleDependencies.modules
}
message ComponentDescriptor {
  enum Kind { AGENT = 0; WORKFLOW = 1; PIPELINE = 2; TOOL = 3; MODEL = 4; }
  Kind kind = 1;
  string name = 2;
  string description = 3;
  bool streaming = 4;
  google.protobuf.Struct input_schema = 5;   // JSON-Schema-shaped
  google.protobuf.Struct output_schema = 6;
}

// Generic call envelope — this is what removes the need for per-class codegen
message ComponentCallRequest {
  string call_id = 1;                // idempotency key
  string component_name = 2;
  google.protobuf.Struct args = 3;   // validated against the published input_schema
  CallContext context = 4;
}
message CallContext {
  string thread_id = 1;              // agent conversation continuation key
  string trace_id = 2;
  int32 timeout_ms = 3;
  string principal_id = 4;           // end-user identity, carried but not yet enforced — see below
  string workspace_id = 5;
  string tenant_id = 6;
}
message ComponentCallResponse {
  string call_id = 1;
  oneof result { google.protobuf.Struct value = 2; CallError error = 3; }
}
message CallError {
  string code = 1;
  string message = 2;
  bool retryable = 3;   // load-bearing answer to challenge 5 — caller doesn't have to guess
}

// Streaming: NATS's request() helper is single-reply, but a responder that
// controls its own reply subject can send multiple frames before a terminal
// one — the standard streaming-over-NATS pattern.
message ComponentStreamFrame {
  string call_id = 1;
  oneof frame {
    google.protobuf.Struct delta = 2;      // partial output
    ComponentCallResponse final = 3;       // closes the stream
    CallError error = 4;
  }
}
```

Kernel services stay fully typed. Document, deliberately still using `Struct` for the document *body* only, since
`DocumentPort` is itself a schemaless JSON store by design — a correct use of dynamic typing there, not a cop-out:

```protobuf
message PutRequest  { string namespace=1; string collection=2; string id=3; google.protobuf.Struct data=4; optional int64 if_version=5; }
message PutResponse { Document document = 1; }
```

Checkpoint's contract is simpler still — LangGraph already serializes its own checkpoint blobs, so most of that
contract is `bytes` pass-through mirroring `BaseCheckpointSaver`'s methods, not something needing its own schema.

**Naming**: `abi.svc.<domain>.<method>` for kernel services (e.g. `abi.svc.document.put`);
`abi.mod.<module_name>.<component>.call` for module components — the latter is what a NATS queue group scales.

**Versioning**: package-namespace per major version (`abi.svc.document.v1`), additive-only fields within a
version, never reuse a field number. The subject itself carries the major version for both kernel services and
module components — `abi.mod.<module_name>.v1.<component>.call`, `abi.mod.<module_name>.v2.<component>.call` — so
two contract-incompatible versions never share a queue group. **This is how a module publishes a breaking change
to its own proto**: register the new subject and NATS Service alongside the still-running old one — the exact same
side-by-side, config-driven pattern "Coexistence" already establishes for extracted modules, just applied to a
contract version instead of a code location. Advertise both in the `ModuleRegistration`/`ComponentDescriptor` (add
a `contract_version` field distinct from the module's own package `version`, since a module can ship a new release
without changing its wire contract, or vice versa) so `EngineProxy`'s stub generation binds each caller to the
version it actually supports, preferring the newest one both sides agree on. Retire the old subject once nothing
depends on it — traffic drains naturally rather than needing a coordinated cutover, again mirroring the rollback
story "Coexistence" already gives module extraction.

**Extensibility, addressing the concern that Protobuf is rigid**: for the common case — a module evolving its own
component's inputs/outputs — there is no recompilation at all, because the payload is `Struct`, not a generated
type; a module author just changes what their own `input_schema` describes. For a module that wants a genuinely
custom, strongly-typed sub-protocol rather than "more JSON fields," Protobuf's `google.protobuf.Any` carries an
arbitrary, independently-versioned message identified by a type URL at runtime — a module can define and evolve
its own `.proto` package on its own schedule, packed into an `Any` inside the generic envelope, without the shared
core schema ever changing. The one honest caveat: whoever needs to *read* that extension meaningfully still needs
the module's generated types available — this isn't "anyone can read anything with zero coordination," it's
"unrelated parties don't need the core schema to change to add their own island of structure" (the same pattern
Kubernetes CRDs and gRPC's own extension mechanisms use). Where recompilation genuinely is required — the envelope
itself, or a kernel service contract — that surface is small, centrally owned, and Protobuf's wire format is
additive-safe, so even that rare case doesn't force a flag day, just a package release.

### 5. Challenges

These are the places where today's in-process assumptions actively fight a distributed design. Roughly ordered by
how much they block the rest:

1. **Cross-module dynamic dispatch is Python-reflection-based, and that stops working across a process boundary.**
   `ModuleComponentLoader.load_subclasses` (`module/ModuleComponentLoader.py:25-73`) discovers agents, workflows,
   pipelines, and tools by walking the filesystem, importing every file, and filtering `inspect.getmembers` for
   live subclasses defined in that exact file. There is no serializable description of "what does this module
   offer" anywhere — the class object *is* the description. A remote module needs to publish a serializable
   manifest at registration time (name, input schema, output schema, streaming or not) so the engine (or Nexus, or
   another module) can build a LangChain tool wrapper that shells out over NATS instead of holding a live Python
   object. This is probably the single largest engineering item in this whole effort — it touches every `Expose`
   subclass, not just the kernel domains. *(The wire format is now decided — Protobuf, see "Decisions locked in"
   above. That settles the format; writing and maintaining a manifest message per `Expose` subclass is still the
   bulk of the work.)*
2. **`BaseModule.get_instance()` and direct cross-module imports assume shared memory.** Real examples:
   `PersonnelAgent.get_sparql_tools` (`.../personnel/agents/PersonnelAgent.py:76-90`) imports another module's class
   directly to `isinstance`-check a live object; `AbiAgent.py`, `NexusPlatformPipeline.py`, and several Nexus API
   resolvers do the equivalent through `ABIModule.get_instance().engine.modules[...]`. Every one of these becomes an
   RPC call with a DTO instead of a live object reference, and every `isinstance` check on another module's class
   becomes meaningless across a process boundary — it has to become a capability check against the registration
   record instead. *(Decided: always over NATS, including for co-located modules — no in-process shortcut. See
   "Decisions locked in" above.)*
3. **No graceful lifecycle exists today.** `on_unloaded()` is defined and never called anywhere in the codebase. A
   distributed deployment needs modules to actually drain in-flight requests and deregister on shutdown (container
   preemption, rolling deploys, autoscale-down), which is new work, not a gap that happens to be latent today.
4. **Ontology bootstrap ownership.** Today, `abi dev` sidesteps the fact that both the API and Dagster processes
   would otherwise double-load the same ~tens-of-thousands-of-triples ontology set into one shared Oxigraph, via a
   blunt `ABI_SKIP_ONTOLOGY_LOADING` env-var hack for the Dagster process specifically
   (`cli/dev.py:385-391`, `EngineConfiguration.py:280-303`). That only works because the two processes and their
   relationship are known in advance. In a world with N module instances that can come and go, "who owns loading
   this module's ontology, and has it already happened" needs a real idempotency/leader-election answer — e.g. a
   JetStream KV compare-and-set ("claim the load for module X" with a TTL) rather than an environment flag.
   *(Substantially simplified by keeping `triple_store` a centralized singleton — see "Decisions locked in" above.
   No multi-instance leader election needed; a JetStream KV "has module X loaded" flag still is.)*
5. **Synchronous, in-memory ports don't map cleanly onto network RPC.** Ports like `IDocumentAdapter`
   (`DocumentPort.py`) are plain synchronous method calls today — a microsecond in-process call. Once a call can go
   over the network, every call site needs to reckon with latency, partial failure, timeouts, and retries that a
   Python function call never had to consider, and (for methods that used to be assumed side-effect-free on retry)
   idempotency, since at-least-once RPC delivery is the safe default. `TripleStoreService.__publish_triples`'s
   already-documented one-message-per-triple bus pattern (`TripleStoreService.py:222-284`) is a preview of this
   class of problem: it already had to be explicitly batched (`publish_many`) to avoid per-message round-trip cost
   dominating engine boot — the same discipline now has to be applied to every domain call that becomes a network
   hop, not just bus publishes.
6. **The `ModuleDependencies.services` access-control model is Python-level, not network-level.**
   `ServicesProxy.__ensure_access` (`engine/EngineProxy.py:75-82`) is an in-process `raise ValueError` — trivially
   bypassable by anything running in the same interpreter, but that was fine because only trusted, reviewed module
   code shared the interpreter. Once modules are separate processes/containers, "module X may only call service Y"
   has to become a real authorization boundary — NATS account/permission scoping (subject-level allow/deny per
   credential) is the natural analog, but it means `ModuleDependencies.services` needs to actually drive NATS
   credential issuance, not just gate a Python property getter. *(Model decided: a shared JWT carrying per-module
   claims, see "Decisions locked in" above. Issuance, lifetime, and rotation/revocation are still open — see Open
   questions.)*

   This is service-to-service identity (which process/module may call which subject) — a genuinely different, and
   older, problem from **end-user authorization** (which human, in which workspace, may see which data), which is
   a pre-existing gap, not something this migration introduces: `PlatformServicesAgent` already gives chat access
   to the triple store/object storage/vector store/cache/kv today with no per-user ACL. NATS exposure doesn't
   create that gap, but it can widen its practical reach — today, reaching `TripleStoreService` requires being
   reviewed Python code in a trusted call graph originating from an authenticated Nexus request; over NATS,
   anything holding the shared service-identity credential can call it directly. Designing real per-user
   enforcement now would be solving for a tenant/workspace boundary that doesn't exist at the kernel-service layer
   yet, and belongs with the future instance-architecture/SaaS RFC once hard-tenancy's actual boundary is concrete
   — but the *wire format* is cheap to future-proof today: `CallContext` (see "Protobuf contract shapes") now
   carries `principal_id`/`workspace_id`/`tenant_id`, unenforced for now, specifically so adding real enforcement
   later is a behavior change in one place, not an envelope change propagated through every existing caller.
7. **Config/secrets distribution.** Today one YAML file is Jinja-rendered once, in one process, with a
   `SecretServiceWrapper` resolving `{{ secret.X }}` placeholders. Each `ModuleConfig.config` dict is already
   scoped per module (a real asset here), but a containerized module needs its *own* slice of config and secrets
   delivered to *its* process, not read out of a shared file on a shared disk — this is a deployment-tooling problem
   (secret injection per container) more than an engine-code problem, but it has to be solved before any module can
   actually run standalone. *(Decided: the engine serves each module its resolved secrets over an authenticated
   NATS request-reply call, see "Decisions locked in" above. Only the module's own bootstrap credential — needed to
   authenticate to NATS in the first place — still needs conventional injection.)*
8. **`model_registry.validate_defaults()` hard-fails engine boot today** (`Engine.py:94-97`) as a single atomic
   gate. In a distributed world "boot" isn't one event — a module can join the network after the engine already
   passed that gate. Validation has to become continuous/eventually-consistent (re-checked as capabilities change)
   rather than a one-shot startup assertion.
9. **Tracing and debugging span processes now.** One stack trace in one process's logs becomes a distributed trace
   across N containers. NATS message headers can carry a `traceparent`, but propagating and correlating it (Dagster
   job → NATS RPC → module logs) is new plumbing, not something that falls out of the migration for free.
10. **Deciding what stays centralized.** Not every domain needs to become a horizontally-scaled remote service on
    day one. `triple_store`/`document`/`object_storage` are today singleton-backed-by-one-database services; making
    the *service* remote-callable (for module isolation) doesn't necessarily mean making the *backing store*
    distributed too. *(Decided: yes, they stay centralized singleton services reached over NATS — see "Decisions
    locked in" above.)*
11. **Agent sub-agent composition doesn't reduce to a simple RPC proxy.** Listed last, but despite that likely the
    single largest remaining design surface in this RFC. `AbiAgent` embeds every agent from every loaded module as
    a node in one shared-state LangGraph today (`AbiAgent.get_agents`, `Agent.build_graph`) — a compiled-graph
    object and shared mutable state, neither of which crosses a process boundary. *(Resolved with a two-tier
    design — same-process stays graph-embedded, cross-module becomes a stateful streaming NATS session keyed by
    `thread_id` — see "Agents: the sub-agent composition problem" and "Decisions locked in" above.)*
12. **Running NATS is a separate problem from talking to NATS, and nothing here addresses it yet.** Every decision
    so far is about the application side — none of it touches clustering/HA, JetStream persistence and backup, and
    keeping `abi dev`, `abi deploy local`, and production configuration in parity the way `config.yaml`'s
    `bus_adapter` choice already does for RabbitMQ today. This is a distinct, currently-unaddressed category, not a
    deployment detail to wave at — a lost JetStream stream is a lost registration/discovery/checkpoint backbone,
    not just a lost queue.
13. **The cost of "always via NATS, no in-process shortcut" (a decision above) hasn't been measured.** That
    decision deliberately trades latency for architectural uniformity — every module-to-module and module-to-service
    call now pays a network round trip, Protobuf encode/decode, and a JWT check, even when caller and callee happen
    to share a host. Nobody has put a number on what that costs yet, and some existing call patterns are already
    known to be latency-sensitive at volume (`TripleStoreService.__publish_triples`'s per-triple bus messages,
    challenge 5 above). Worth measuring during Phase 1-2, with real numbers, before the decision is load-bearing
    everywhere rather than discovering the cost once it's expensive to unwind.

### 6. What this unlocks

- **Kills the Dagster reload problem directly**, which is the concrete pain point that motivated this — and which
  is already degrading production today, not just a theoretical concern. Dagster ops become thin NATS RPC clients
  talking to already-warm, persistently-running module processes, instead of each op subprocess re-running
  `Engine().load()` from scratch. This removes the need for the `in_process_executor` workaround entirely, rather
  than extending that workaround to more orchestrations.
- **Makes hard-tenant SaaS unit economics viable, not just architecturally cleaner.** A single tenant's dedicated
  instance still runs its own Dagster and its own API process; if each one independently pays the full in-process
  reload cost, per-tenant hardware requirements (and therefore cost per customer) stay high regardless of how many
  tenants exist. Stage 1 fixing that cost is what makes "one small, cheap instance per paying customer" a real
  option rather than an aspiration.
- **Per-module horizontal scaling, exactly as targeted**: "this module is consuming a lot of resources, spin up
  more replicas of just that module" becomes N processes in the same NATS queue group — no application code change
  in callers, no change to the module's own business logic, only awareness (already largely true for the kernel
  domains) that it may not be the only instance handling its own subject.
- **Replaces RabbitMQ with close to zero risk**, because the bus is already a hexagonal port — a new
  `NATSJetStreamAdapter implements IBusAdapter` slots in next to `RabbitMQAdapter`/`PythonQueueAdapter` behind the
  existing `bus_adapter: { adapter: "..." }` config switch, and can be validated against the same generic adapter
  contract test pattern used for storage backends today.
- **Consolidates infrastructure.** One NATS cluster can absorb the bus (replacing RabbitMQ), service discovery
  (replacing a bespoke or absent mechanism), RPC transport, and — optionally, later — the KV backing the Fuseki
  distributed lock (replacing Redis for that one purpose, though Redis has other uses via `CacheService` and can
  stay). Fewer moving pieces to operate than RabbitMQ + Redis + a hypothetical separate service-discovery system.
- **Independent deployability and smaller blast radius.** A change to one module ships as one container, without
  rebuilding or redeploying the API/Dagster/Nexus process it used to be bundled into.
- **Rolling upgrades.** A module's container can be replaced without restarting the engine or any other module.
- **Resource isolation and cost control**, since a heavy module gets its own CPU/memory budget instead of
  contending inside one process with everything else.
- **A cleaner relationship with the (draft, not-yet-committed) server-federation idea.** There is an untracked
  `RFC-federated-abi-servers.md` floating in some worktrees proposing HTTP/JWT federation of whole ABI *server*
  processes (coordinator + data planes), which is a different axis from this proposal (that RFC federates whole
  servers; this one distributes modules *within* a server). The two are complementary, not competing: NATS-based
  module distribution could live entirely inside one data-plane server, with that RFC's HTTP/JWT federation staying
  the mechanism for crossing server/tenant boundaries. Worth reconciling explicitly if/when that RFC is picked back
  up (see Open questions).

### 7. The Nexus module-apps problem (flagged explicitly by the user)

Today, Nexus discovers module-provided HTML apps by walking **local disk**: the Nexus API's
`_scan_apps_catalog()`/`_scan_apps_module_apps()`
(`apps/nexus/apps/api/app/services/apps/adapters/primary/apps__primary_adapter__FastAPI.py:201-278`) iterates
`ABIModule.get_instance().engine.modules`, reads each module's `Path(module.module_root_path) / "apps"` for
`manifest.json` files, and a single catch-all route `GET /app-html/{path:path}`
(`apps/nexus/apps/api/app/main.py:370,418`) serves the actual HTML/CSS/JS bytes straight off that same local disk
via `FileResponse`. This assumes the module's files are on the same filesystem as the Nexus API process — true
today because everything is one process/one checkout, false the moment a module moves into its own container.

Two things break simultaneously: **discovery** (Nexus can no longer `Path()` into a module it doesn't share a
filesystem with) and **serving** (Nexus can no longer `FileResponse` bytes it doesn't have local access to).

The good news is the repo already has two working precedents for exactly this shape of problem — auth and
transport for a browser iframe pointed at something *not* co-located with Nexus — and the fix should reuse them
rather than invent a third:

- **The Coder workspace pattern** (`services/coding_environment/adapters/secondary/CoderAdapter.py`): Nexus holds a
  long-lived admin credential for the remote system, JIT-provisions/authenticates the user server-to-server, mints
  a short-lived, scoped redemption token, and hands the iframe a URL to a genuinely separate origin/container
  (`url = f"{base_url}?coder_session_token={token}"`). No bytes are proxied through Nexus; Nexus only brokers the
  handshake.
- **The Pages SSO HMAC pattern** (`apps/nexus/apps/api/app/services/apps/pages_sso.py`), already built for
  externally-hosted catalog apps but not yet consumed by any real app: a short-lived, audience-scoped HMAC token
  asserting "Nexus already authenticated this user" that an allowlisted external origin can verify itself, exposed
  via `POST /api/apps/sso-token`.

Recommended shape, reusing both rather than choosing one:

1. At registration (the same NATS registration record described in §4), a containerized module advertises its
   `apps/` catalog as data — the parsed `manifest.json` entries — plus, for bundled (`html:`) apps, either (a) a
   base URL where its own lightweight sidecar HTTP server serves those static assets directly, or (b) for small
   bundles, the assets themselves pushed into a JetStream Object Store bucket Nexus can read from. (a) is simpler
   operationally and is the recommended default — NATS is well suited to RPC/events/discovery/small KV payloads,
   less naturally suited to being the browser-facing static-asset host for a potentially large SPA bundle; treat
   the Object Store option as a fallback for very small apps only, not the default path.
2. `_scan_apps_catalog()` stops walking local disk for containerized modules and instead reads the NATS-published
   catalog (still process-cached, same as today, just re-sourced).
2. The `/app-html/{path:path}` catch-all, for a containerized module's app, does the Coder-style handshake instead
   of a local `FileResponse`: mint a scoped redemption token, redirect/point the iframe at the module's own sidecar
   URL rather than proxying bytes through Nexus. This mirrors the X Proxy app's existing precedent of intercepting
   `/app-html/...` ahead of the generic catch-all with its own middleware
   (`applications/x/apps/x_proxy/routes.py`), which already proves "a module's app doesn't have to be served from
   local disk" is a pattern the codebase tolerates today, just not yet for a genuinely separate container.
3. For apps whose manifest `url` is already fully external (`https://...`, e.g. `wsr`), nothing changes — that path
   already doesn't assume local disk.

This keeps the manifest.json contract and the Nexus-facing `AppRecord`/catalog shape completely unchanged — only
where the catalog is sourced from, and how the iframe URL is authenticated, needs new plumbing. It's real work, but
it is additive to two mechanisms that already exist and are proven (Coder, and — once a consumer is written — Pages
SSO), not a new invention.

### 8. Phased rollout — two separate programs, not one continuous rollout

This is deliberately split into two stages, not six flat steps: **Stage 1 puts the engine's kernel services on
NATS while every module stays exactly where it is today, fully in-process.** Only once that's stable does **Stage
2** touch modules themselves. This isn't just a safer ordering — it changes what actually has to be solved first.
The two seams were always different things (see "Where we start from" above: `EngineProxy.services.<x>` vs.
`EngineProxy.modules[<name>]`); Stage 1 is "do the service seam as its own complete program," Stage 2 is "do the
module seam as a genuinely separate second program that builds on it."

**Why service-only comes first, concretely**: the dominant cost in the original Dagster-reload problem (Problem,
above) was ontology reinsertion into the triple store — "tens of thousands of triples" — not module class imports.
If `triple_store` (and `document`/`object_storage`) become NATS-reached singleton services while modules stay
in-process everywhere, Dagster's process may stop needing to bootstrap its own local Oxigraph at all, which likely
captures most of the original motivation *before* any of the harder module-level problems are even touched. Stage
1's scope shrinks accordingly: no manifest/auto-derivation problem (challenge 1 — nothing arbitrary is exposed
yet, only a handful of hand-designed kernel contracts), no sub-agent composition problem (challenge 11), no module
lifecycle/drain (challenge 3), no secrets-over-NATS (challenge 7 — modules aren't separate processes yet, they
still read the one `config.yaml` unchanged). What Stage 1 *does* have to solve, and can't defer: the
ontology-bootstrap-ownership idempotency check (challenge 4) — without it, both API and Dagster would each still
push the full ontology to the now-shared triple store once each, saving nothing — and retry/idempotency (challenge
5) for the handful of kernel service calls specifically, not the general case yet.

**Stage 1 — engine and kernel services over NATS, modules untouched:**

1. **Spike**: add NATS+JetStream to `docker-compose.yml` alongside (not replacing) RabbitMQ/Redis. Implement
   `NATSJetStreamAdapter implements IBusAdapter` and validate it against the existing generic bus-adapter contract
   tests. Zero blast radius — it's a new, opt-in `bus_adapter` choice.
2. **Kernel service contracts**: hand-write the Protobuf `.proto` files for `document`, `triple_store`,
   `object_storage` (and `checkpoint`, if convenient to include now — it's the same category and cheap to do while
   everything is still low-risk, even though nothing consumes it remotely until Stage 2's agent work). Add
   `Expose.as_nats()` and one `<domain>__primary_adapter__NATS.py` per service, plus the `adapter: "nats_rpc"`
   branch on each `EngineConfiguration_<X>Service.py`. Everything still runs in one process on the calling side —
   this only proves the request/response contract, serialization, error-mapping, and the generic primary-adapter
   test pattern.
3. **Solve ontology-bootstrap ownership** (challenge 4): the JetStream KV "has this module's ontology already been
   loaded" flag, checked by whichever process (API or Dagster) tries to load a module's ontology against the now
   remote `triple_store`. This is the one piece of new coordination logic Stage 1 actually needs, and it's what
   turns "services are reachable over NATS" into "Dagster's reload is actually cheaper."
4. **Point Dagster at the NATS-reached services**: Dagster's process still imports every module in-process
   (nothing about module loading changes yet), but its `triple_store`/`document`/`object_storage` calls go over
   NATS to the same singleton services the API process uses, instead of each maintaining its own local backend
   connections. Measure the actual reload-cost improvement here (ties to challenge 13) before calling Stage 1 done.
5. **Stabilize**: run Stage 1 in production for a while — this is a legitimate place to pause, not just a
   checkpoint. If it already resolves the original pain well enough, Stage 2 becomes optional rather than assumed.

**Stage 2 — modules over the network** (a separate program, only started once Stage 1 is proven):

6. **Agent/checkpoint RPC prototype**: one small, dedicated prototype — one agent, one remote-handoff-proxy
   sub-agent, real `thread_id`-keyed conversation continuation over the `checkpoint` service from Stage 1. This
   validates the streaming, stateful-session pattern challenge 11 depends on, which nothing in Stage 1 exercises.
7. **Manifest auto-derivation** (challenge 1): the actual reflection-to-Protobuf-envelope work for
   `Agent`/`Workflow`/`Pipeline`/`Tool` classes, using the generic envelope + `Struct` payload approach above. This
   is the largest remaining unknown in the whole RFC and Stage 2's real gate — nothing past this point works
   without it.
8. **First real module extraction**: pick one self-contained, resource-heavy, low-blast-radius module (a scraping
   or ingestion pipeline is a good candidate) and run it as its own container, talking to the Stage 1 services over
   NATS instead of in-process `EngineProxy`. This is where module lifecycle (register/heartbeat/deregister),
   dependency-wait, secrets delivery, and queue-group scaling actually get exercised for the first time.
9. **Dagster orchestrations become NATS clients for extracted modules**: one orchestration at a time, the same way
   today's `in_process_executor` opt-in was adopted by only four orchestrations — not a repository-wide switch.
   Orchestrations touching not-yet-extracted modules keep working exactly as in Stage 1.
10. **Nexus module apps**: the sidecar-HTTP + NATS-catalog-registration path from §7 for the module(s) extracted
    in step 8. Local-disk discovery keeps working for every module that hasn't moved.
11. **Opportunistic expansion**: extract more modules only where real scaling/deployment pain justifies it. Retire
    RabbitMQ and the in-process bus adapter once NATS parity has run in production for a while.

By the end of Stage 2, most modules and kernel services communicate through explicit, versioned NATS contracts
rather than direct Python calls. Only *then* does it make sense to ask whether the engine implementation behind
those contracts should change — at that point the question is scoped to "does a new implementation satisfy the
sealed contract," not "how do we migrate every caller." That follow-on question, and any candidate for it, is out
of scope for this document by design (see the scope note above).

Every step in both stages stays additive: the system keeps working exactly as it does today throughout, via the
"Coexistence" mechanism above, until a given piece is deliberately and individually cut over — and even then,
cheaply reversible for a stabilization period.

## Alternatives considered

- **RabbitMQ (keep) + gRPC (RPC) + etcd/Consul (discovery)**: functionally comparable, but three separate systems
  to operate instead of one, with three client libraries and three failure domains, for no capability NATS/
  JetStream doesn't already cover in this repo's scale range. Worth noting explicitly now that Protobuf is in the
  design (see "Decisions locked in"): this proposal takes gRPC's best idea — typed, schema'd, backward-compatible
  wire messages — without its transport. NATS still does discovery, pub/sub, durable queues, and RPC in one system;
  gRPC alone would still need something else for discovery and pub/sub.
- **Kubernetes-native service mesh (Istio/Linkerd) + plain gRPC, with discovery via k8s Services**: solves transport
  and mTLS well, but doesn't solve the actual hard problem here (in-process module coupling → serializable RPC
  contracts and lifecycle), forces a k8s dependency the project doesn't currently require (docker-compose is the
  primary deployment story today per `abi deploy local`), and is heavier to run locally for `abi dev`-style
  workflows. Not rejected outright — worth revisiting once/if the project standardizes on k8s for production — but
  not the right first step.
- **Big-bang rewrite of every module to be distributed at once**: rejected as far too risky given how deep the
  in-process assumptions run (§5.1-5.2); the phased plan validates the riskiest piece (RPC/discovery) before
  committing any module to containerization.
- **Leave Dagster's reload cost as-is and just tune `executor_def` on more orchestrations**: cheaper in the short
  term and worth doing regardless, but it's a local mitigation, not a fix — it doesn't unlock per-module scaling or
  independent deployability, which were the user's actual stated goals.

## Open questions

What's left, now that serialization, auth model, the cross-module-calling rule, secrets delivery, and backing-store
centralization are decided (see "Decisions locked in" above):

- **JWT mechanics for Stage 2** (per-module claims, rotation/revocation for a long-running extracted module, the
  precise `ModuleDependencies` claim mapping) — genuinely still open, deliberately, since it depends on a caller
  that isn't trusted first-party infrastructure, which doesn't exist until Stage 2 extracts a real module. See
  "Decisions locked in" for Stage 1's minimal, already-settled version.
- **Protobuf schema packaging for Stage 2** (a standalone `naas-abi-proto` package, `buf` adoption) — open for the
  same reason: only needed once marketplace modules must depend on the schema independent of `naas-abi-core`'s own
  release cadence. See "Decisions locked in" for where Stage 1's contracts actually live.
- **Ontology-bootstrap sequencing.** The hard part (leader election across multiple `triple_store` instances) goes
  away now that `triple_store` stays a centralized singleton. What's left is smaller: does a dependent module wait
  on a "this ontology is loaded" JetStream KV flag before it's considered ready, and does the triple-store service
  itself own pushing that flag, or does the loading module set it after a successful push-RPC? Worth a concrete
  design once Phase 3 picks a real module, rather than in the abstract now.
- **How much does this compose with the draft `RFC-federated-abi-servers.md`** (server-level federation via a
  coordinator/IdP)? Recommended framing is "NATS distributes modules within one server; that RFC's HTTP/JWT model
  federates across servers" — but that RFC is itself unmerged/untracked, so this should be reconciled explicitly if
  and when it's picked back up, rather than assumed.
- **Which module is the actual first extraction candidate?** §8 step 3 suggests "a scraping or ingestion pipeline"
  as a placeholder; the real choice should be driven by which module is currently causing the most resource
  contention in production, which this RFC doesn't have visibility into.
