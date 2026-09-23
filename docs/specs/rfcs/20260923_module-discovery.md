# Remote module discovery

Status: Backend approved; first discovery implementation delivered.
Agent invocation remains outside this slice. See implementation notes below.

## Existing behavior

The core EngineModuleLoader resolves Python module dependencies and sorts them
before loading. The standalone SDK currently rejects ModuleDependencies.modules.
Its runner already owns connection lifetime and task-scoped current_module().
Discovery should extend that runner, without importing core into the SDK.

## Alternatives

| Approach | Benefit | Cost |
| --- | --- | --- |
| Static module/subject configuration | Smallest implementation; deterministic deployment | No runtime membership, readiness or crash detection |
| NATS Services discovery / broadcast requests | Existing endpoint discovery and monitoring | ABI still needs readiness, dependency/version rules and expiring membership; a timeout cannot prove a complete inventory |
| Modules write directly to JetStream KV | TTL, watches and revision checks using existing infrastructure | Every module participates in registry policy and requires registry access; broker ACLs alone do not validate ABI descriptors |
| Discovery service backed by JetStream KV | Central contract and policy; lightweight clients; registry can run separately | Additional service owner and explicit availability/recovery requirements |
| Discovery service backed by DocumentService | Reuses existing persistence and CAS | Requires lease expiry/query/change-notification design; couples bootstrap availability to the document service |
| External registry such as etcd/Consul | Appropriate when already part of deployment infrastructure | Adds another operated dependency to the current NATS deployment |

## Recommendation

A small DiscoveryService with protobuf RPCs over NATS and a registry port, with
JetStream KV as the proposed production adapter. Start hosted by the engine;
keep its bootstrap independent so it can later run as its own process. The
project's explicit NATS direction supersedes generic gRPC/DDS guidance here.
No module imports its implementation. No new database is required.

The owner approved JetStream KV as the backend. Use an in-memory adapter for
deterministic contract tests only. Do not silently substitute it in production.

Only the service writes registry records. Clients receive typed descriptors via
RPC and use bounded refresh initially. A later watch contract needs revisions,
snapshot completion and resynchronization; plain pub/sub is not a reliable
registry history. The backend can use KV watches internally.

## Identity and contracts

- project scope: deployment-configured subject prefix and registry namespace;
  a caller-provided project string alone is not isolation.
- module_id: stable logical identity, defaulting to the import path, explicitly
  overridable for scripts that would otherwise all identify as __main__.
- instance_id: random ID for each process start; replicas never overwrite one
  module-wide record. Lease identity is separate from the stable module name.
- package_version and contract_version: distinct fields; initial compatibility
  uses exact supported contract major versions, not arbitrary semver expressions.
- agent descriptors: stable name, description, supported contract majors and
  capabilities. Advertise callable subjects only after a handler exists.
- lease: opaque registration token, revision and server-derived expiry. Renew
  and unregister must match this process's registration. Old requests cannot
  overwrite a newer incarnation or resurrect an expired lease.

Proposed RPCs: RegisterInstance, RenewLease, UnregisterInstance, GetModule,
ListModules. Registration carries declared required module dependencies and
capability descriptors. GetModule returns compatible live instances and readiness;
ListModules is bounded/paginated. Unregister is idempotent for the same lease.
Register uses a client-generated registration ID so an ambiguous reply can be
reconciled. Renew uses revision checks; retry policy is specific to these control
operations, not automatic replay of arbitrary agent calls.

Protobuf owns transport shapes. The SDK exposes Python values and ModuleProxy
objects. SDK dependency declarations restrict API access; service/broker identity
must enforce actual permissions separately.

## Lifecycle and readiness

1. Connect, construct the module, and run on_load for local declarations.
2. Register STARTING and begin lease renewal. Being registered is not readiness.
3. Resolve required modules to compatible READY instances within a startup bound.
4. Run on_initialized with dependency proxies available, install any handlers,
   and advertise local initialization complete.
5. Publish READY only when initialization and required dependencies are healthy;
   run the module's main operation.
6. On dependency loss, report DEGRADED and fail new calls to unavailable targets
   explicitly. Keep independent work running; do not kill the module by default.
7. On shutdown, mark DRAINING, stop accepting new work, unload, unregister and
   close the connection. A crash is handled by lease expiry.

The registry must keep local initialization separate from effective readiness.
For an acyclic required-dependency graph it computes readiness transitively; this
avoids recovery deadlocks where every degraded module waits for another to become
ready. Reject known required cycles, including ones completed by later registration.
Unknown dependencies stay unresolved until the startup deadline. Optional
relationships need a separate future declaration and must not block readiness.

Initial proposed defaults: heartbeat every 5 seconds with jitter, lease 20 seconds,
startup wait 60 seconds, dependency refresh every 2 seconds. All configurable;
these are design defaults, not shipped behavior. Account for RPC deadlines within
the lease budget. Readiness cached by clients has a bounded age, never an indefinite
last-known-good fallback. A successful lookup cannot guarantee the next call.

On broker/registry outage, stop claiming readiness once the last confirmed lease
expires. Reconnect requires revalidation or fresh registration. Expiry is evaluated
on lookup even if backend deletion notifications lag. Do not rely on KV deletion
notifications alone, or treat potentially stale direct reads as a lock authority.

Start with a single registry service owner. Multi-owner operation requires shared
lease/CAS semantics, consistent graph decisions and tested restart recovery;
putting several memory registries in a queue group is not an HA implementation.

## Module-facing API

```python
class ABIModule(BaseModule):
    dependencies = ModuleDependencies(modules=("acme.research",))

    async def on_initialized(self):
        research = self.engine.modules["acme.research"]
        agents = await research.list_agents()
```

The runner resolves required dependencies before on_initialized. The indexed
object is a logical ModuleProxy, not a remote Python object or a permanently
selected process. list_agents returns portable descriptors initially. Later,
get_agent(name) constructs AgentProxy against the compatible invocation contract.
Agent invocation, streaming and execution ownership are a separate implementation.

Undeclared access raises immediately. Missing, incompatible and unavailable
modules are distinct failures. Enumeration of unrelated modules is an explicit
administrative discovery API, not a way to bypass dependency declarations.

Register engine-hosted modules through the same discovery contract when enabled;
do not make legacy modules available remotely merely by listing their Python agent
classes. An installed remote handler is required before advertising invocability.
Existing projects without discovery retain current startup behavior. Remote module
dependencies require discovery configured; an absent registry fails explicitly.

## Security and execution boundary

Current Stage 1 tokens provide shared trust, not module-specific ownership.
Untrusted module registration requires verified module/project claims and subject
permissions; registration tokens alone do not establish an authenticated identity.
Do not allow descriptors to redirect callers to arbitrary unauthorized subjects.
No credentials, Python objects or pickles belong in descriptors.

Discovery leases express membership only. They neither lock a conversation nor
fence an old worker's side effects. Invocation IDs, durable status, checkpoint
ownership, cancellation and execution fencing remain in the AgentProxy follow-up.

## Implementation slices and acceptance tests

1. Versioned protobuf contract, registry port and deterministic application tests:
   registration, replicas, revisions, expiry, cycles, compatibility and pagination.
2. Backend adapter after the storage decision, authenticated NATS primary and SDK
   client/facade. Test unauthorized mutations and actual broker restart/reconnect.
3. Runner registration/renewal/cleanup, ModuleProxy and dependency gating. Cover
   cancellation, missing registry, partial initialization and bounded startup.
4. Disposable demo: provider and consumer in separate SDK-only processes. Consumer
   waits for provider readiness; enumerate agent descriptors; kill provider and
   observe unavailability; restart and recover with a new instance ID. Include
   duplicate registrations, lost renewal replies and dependency-chain recovery.
5. Engine-hosted module registration and remote invocation in subsequent slices;
   do not claim discovery by itself proves cross-process agent execution.

## Sources

- Existing design: 20260910_distributed-modules-nats-jetstream.md, section 4.
- https://docs.nats.io/learn/key-value/ (TTL, revisions and watches)
- https://github.com/nats-io/nats.docs/blob/master/nats-concepts/jetstream/key-value-store/README.md
  (documented direct-read consistency caveat)
- https://github.com/nats-io/nats.docs/blob/master/using-nats/developing-with-nats/sending/request_reply.md
  (ordinary request API accepts one response; inventory needs explicit collection)

## First implementation and deliberate bounds

- Engine opt-in: `nats.discovery: {project: default, lease_seconds: 20}`. One
  configured registry owner per project. SDK runner opt-in: DiscoveryConfiguration.
- Five authenticated RPCs: register, renew, unregister, get_module, list_modules.
  Mutations verify the JWT caller and lease-token hash. SDK modules advertise a
  stable module_id, package version, contract major, dependencies and agent metadata.
- Atomic graph decisions use one JetStream snapshot with revision CAS and leader
  reads, capped at 256 live instances and 512 KiB. Logical expiry is checked on
  every read; writes prune expired records. This is not a per-instance KV TTL
  implementation and does not scale arbitrarily with heartbeat throughput.
- No public watch stream yet. Proxies query fresh state on access; runner heartbeat
  maintains its own registration and last-confirmed status. Pagination is a live
  keyset view, not a frozen inventory snapshot.
- A lost lease causes fresh registration with a new incarnation. Initialization
  remains local state; the registry recomputes transitive readiness. An unavailable
  registry never triggers a local lookup fallback. Incompatible dependencies keep
  startup waiting until its bound, allowing a compatible replica to arrive.
- Agent descriptors do not imply installed invocation handlers. No callable subject
  is exposed in this version. Engine-hosted module registration is still future work.
- Validation currently executes in the application service; Protovalidate support
  remains absent from the existing proto tooling and is not claimed by these tests.
