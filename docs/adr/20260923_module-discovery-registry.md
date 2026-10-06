# Module discovery registry

## Status
Accepted. Backend approved by the owner; first implementation adds opt-in discovery.

## Date
2026-09-23

## Context
Remote module dependencies are currently rejected. The SDK needs stable module
identities, live instance descriptors and readiness before AgentProxy can resolve
an agent. The existing distributed-module RFC proposes NATS and JetStream KV.

## Decision
Use a DiscoveryService exposed by protobuf RPC over the project's chosen NATS
transport, with a registry port and a JetStream KV adapter behind that boundary.
Modules register and resolve through SDK facades. Start with one registry owner;
make standalone hosting possible without importing core into client packages.
The initial JetStream adapter stores a single CAS-protected protobuf snapshot.
It reads through the stream leader and filters expired instances on every lookup.
Agent authorization polls are the exception: see "Authorization without a
registry read per poll" in the remote agent ADR.
Physical TTL deletion is not required for correctness. Writes prune expired
records. Bound the registry to 256 live instances and 512 KiB; this deliberately
trades throughput/scale for atomic graph validation and straightforward recovery.

Separate stable module identity from per-process registrations, local initialization
from dependency-derived readiness, and discovery leases from execution fencing.
The runner resolves explicit module dependencies before on_initialized. Preserve
existing loading behavior when discovery is not enabled.

## Consequences
A small service centralizes validation, lease policy and discovery. It introduces
an availability dependency with explicit expiry and reconnect behavior. Direct
module writes to shared KV and a document-backed registry were considered.
No additional database is proposed. Stage 1 trust remains insufficient for
untrusted registrations. Agent invocation is a separate contract and delivery slice.

See ../specs/rfcs/20260923_module-discovery.md for alternatives, proposed SDK API,
defaults, failure handling and acceptance tests.

The SDK runner registers STARTING, gates initialization on dependencies, renews
membership and unregisters on unload. Failed lease renewal reports unavailable;
expired leases get a fresh instance identity on recovery. Agent descriptors are
metadata only. Engine-hosted legacy module publication and AgentProxy invocation
remain separate slices. Logging uses existing core logging and SDK standard
logging; no new metrics/tracing stack is introduced.

The existing proto package does not yet include Protovalidate annotations/runtime.
This contract currently validates at the discovery application boundary with
behavior tests; schema-embedded validation remains an explicit repository gap.

## Rollouts and draining (2026-10-05)

A process joins a rollout by registering a rollout id. Processes that must cut
over together send the same id and the same list of module ids. An empty list
means that module alone. `ABI_ROLLOUT_ID` and `ABI_ROLLOUT_MODULES` set those
values when the discovery configuration leaves them empty.

Discovery keeps the current generation serving until every module id in the new
rollout has an initialized instance, and until each of that rollout's
dependencies is either inside the rollout or already initialized outside it.
Until then the new instances are `STAGED` while a previous generation of that
module id is still up, and lookups that want a ready module skip them. When the
rollout is complete, it becomes the serving generation for those module ids.
Older complete generations, and instances with no rollout id, are marked
draining. A later complete rollout replaces an earlier one. An incomplete
rollout is left in place, so a deploy that never finishes does not take traffic
away from the current one. Same-rollout replicas stay up together. The module
id is the identity being replaced. The contract major stays the caller's pin.
`package_version` is not an order.

`SIGTERM` and `SIGINT` ask the process to drain as well. Draining renews with
`draining` set, stops new agent submits, job fetches and model chats, and waits
for runs and jobs that already started. A finished agent run releases its
conversation claim. The process then unregisters. A draining instance stays in
discovery until it exits, so a claim held by a live run is not treated as
abandoned. A hard kill still falls through to lease expiry.

## Descriptors across generations (2026-10-06)

Replicas of one generation must declare the same dependencies, agents, jobs and
models for a contract major: the same rollout id, or no rollout id on both. A
new rollout may change them without a contract bump, for example to add a job.
Before, any live replica of the contract had to match, so a v2 that added a job
got `DESCRIPTOR_CONFLICT` while v1 was up and a `maxUnavailable=0` deploy
stalled.

During the overlap the new generation is `STAGED`. Agent, model and job lookups
take `READY` instances, and submits and model chats require `READY`, so callers
keep using the current generation's agents and models. Jobs need more: a job's
schedule and durable consumer belong to the module, not to an instance, so a
staged process starting its job host would republish schedules, change
consumer limits and run its jobs before its cohort is up. The SDK runner of a
process with a rollout id therefore starts its job host only once discovery
reports it `READY` or `DEGRADED`, and never if it is asked to drain first. The
System app's job list skips staged instances and prefers the serving
generation's definition over a draining one's. A trigger for a brand-new job
sent between the cutover and the new host's start (at most one heartbeat) has
no consumer yet and is not delivered.

## Lease loss keeps the instance id (2026-10-06)

This supersedes "expired leases get a fresh instance identity on recovery"
above. When a renewal fails with `LEASE_EXPIRED` (the lease ran out, or an
admin evicted the registration), the SDK session registers again under the
same instance id with a new lease token. Discovery treats it as a new
registration: `STARTING` until the next renewal reports it initialized.

The instance id is the address of everything the process serves: agent and
model subjects, the `owner` of its agent runs and conversation claims, and the
`instance` on its job runs. A fresh id left those pointing at an id no lookup
listed, so cancel and status of in-flight runs failed with `OWNER_UNAVAILABLE`,
`events()` raised, a model host stayed subscribed to the old subjects, and the
process could release its own live claims as abandoned and mark their runs
`OWNER_GONE`. Keeping the id keeps all of them valid without rewriting records.

Rewriting `owner` on each in-flight run and claim (a CAS per record) and keeping
the old subjects subscribed until those runs end was the alternative. It needs
the same treatment in every host, races each run's own writes, and still
leaves callers holding the old id. While the registration is absent, other
replicas see the owner as gone, as before: a submit to one of its conversations
in that window can release the claim and fail the run as `OWNER_GONE`.
