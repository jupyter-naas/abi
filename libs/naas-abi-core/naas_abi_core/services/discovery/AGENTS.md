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
caller identity plus a lease token. Stage 1 does not authorize logical module IDs.
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
identical dependencies, agents, jobs and models for a contract major, or the
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

## Tests
Use `uv run pytest .../services/discovery --import-mode=importlib`. Unit tests inject
a clock and a fake port; integration tests use native nats-server. Add port
implementations by implementing both read and compare-and-swap methods.
