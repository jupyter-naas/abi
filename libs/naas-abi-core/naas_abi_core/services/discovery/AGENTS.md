# Discovery service

## Purpose
Track expiring process registrations and dependency-derived readiness. Membership
leases are not execution locks. Clients remain independent of ABI core.

## Files and port
`discovery_service.py` owns validation and readiness. `discovery_ports.py` defines
an async revisioned snapshot port. Transport DTOs live in the standalone proto
package. The JetStream adapter stores an opaque protobuf snapshot using CAS.

## Adapters and factory
NATS primary authenticates issued service tokens; mutations bind to verified
caller identity plus a lease token. It accepts a registration only when the
token's identity is the descriptor's module id (a module registers as itself,
docs/adr/20261014_module-identities.md); the service's own tests treat the owner
as an opaque lease holder. An authorize call's caller token must be bound to the
instance asking (``aud``); its own calls refuse a token with an audience.
`discovery_factory.py` composes the service. Engine exposure is explicit opt-in;
replicas use a project queue group and share the same JetStream CAS snapshot. No silent in-memory fallback.

## Eviction (platform administration)
`evict` removes a registration whatever its lease. Only `admin_identities`
(default `api` and `engine`, the Nexus System app and the engine) may call it;
any other caller gets PERMISSION_DENIED. Identities are Stage 1 service names,
so this is hygiene between first-party processes, not a security boundary
against holders of the shared secret. A live owner's next renewal fails with
LEASE_EXPIRED and the SDK session registers again under the same instance id
with a fresh lease token, so eviction clears crashed or stuck registrations;
stopping a module means stopping its process. Registering an instance id whose
record expired or was evicted is a new registration (STARTING until its next
initialized renewal).

## Generations
Replicas of one generation (the same rollout id, or none on both) must declare
identical dependencies, agents, jobs, models, apps, workflows and pipelines for a
contract major, or the
registration fails with DESCRIPTOR_CONFLICT. A rollout may change them for the
generation it replaces: it stays STAGED, outside READY lookups and READY-gated
authorizations, until its cohort cuts over.

A module always keeps a serving generation while it has an initialized
instance: its latest complete rollout; else the generation that served at the
last write (stored statuses), even if its rollout became incomplete; else the
oldest. A completing rollout drains older rollouts of its modules, complete or
not. The cycle check reads edges per generation (own cohort, then the serving
or one other live generation for the rest) and refuses only cycles through the
registering module. See the ADR, "Serving generation and dependency cycles".

## Agent authorization
`authorize_agent` with `new_invocation` false (status, event and cancel polls)
is answered from the registry as this replica last read or wrote it, when that
is under `snapshot_seconds` (1 s) old and allows the call. Leases are checked
against the clock at use. A submit, and anything the snapshot would refuse,
reads the registry, so a snapshot never refuses what the registry allows. An
eviction or unregister through another replica can still let polls through for
up to that second. Every read and successful write refreshes the snapshot.

## Workflows and pipelines
A descriptor lists the `processes` a module serves over NATS (`abi.process.v1`): a
`name` (one subject token, up to 64 characters), a `kind` (`workflow` or `pipeline`;
a name is unique per kind), a description of at most 4 KiB, a contract major above
zero; at most 128 per module and 128 KiB of descriptors in all, so they stay a
small part of the 512 KiB snapshot (a refusal names the limit hit; the SDK cuts
descriptions to 512 UTF-8 bytes so its own can never exceed it). The parameter schema is not registered: callers
ask the module (`describe`). `authorize_process` (instance, lease token, kind, name,
caller token) is answered like `authorize_app`, from a recent snapshot when it
already allows the call, else from the registry: the caller's token must be bound to
the instance asking (the NATS adapter verifies `aud` as for the other `authorize_*`
calls), the lease and owner must match, the process must be declared (`PROCESS_NOT_FOUND`)
and the instance READY (`MODULE_UNAVAILABLE`), so a draining or staged instance
authorizes nothing.

## Concurrency
`DiscoveryNATS` answers calls side by side, up to `nats.max_concurrent_requests`
(`naas_abi_sdk.concurrency.ConcurrentCalls`); `stop()` answers the calls received
first. Writes use group commit (`DiscoveryService._mutate`): a replica writes
once at a time, each write taking every mutation waiting, applied in order on
its own copy of the registry, in one compare-and-swap. Run side by side, the
compare-and-swaps on the one registry document would exhaust their five retries
(`REGISTRY_BUSY`). Reads do not wait for writes.

## Tests
Use `uv run pytest .../services/discovery --import-mode=importlib`. Unit tests inject
a clock and a fake port; integration tests use native nats-server. Add port
implementations by implementing both read and compare-and-swap methods.
