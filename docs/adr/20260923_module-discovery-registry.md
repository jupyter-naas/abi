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
