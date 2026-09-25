# Standalone protobuf contracts and NATS SDK

Status: Accepted

Date: 2026-09-22

## Context

A module in another process must use engine services without installing ABI core
and its application/framework dependencies. Stage 1 bundled protobuf definitions
and clients inside core. The next step needs a runnable demonstration of the full
existing remote surface.

## Decision

- `naas-abi-proto` owns schemas and generated Python messages/stubs. Its only
  runtime dependency is protobuf. Existing core imports forward to these classes.
  The dependency is part of core's optional NATS extra; legacy configurations do
  not acquire a broker requirement.
- `naas-abi-sdk` depends on proto and nats-py, never core. Explicit async clients
  accept/return protobuf messages; no core entities or domain adapters are copied.
  Core's synchronous adapter layer remains compatible with existing domain ports.
- All clients share one connection per async SDK instance. Defaults remain a
  10-second deadline, at most 8 MiB payload, and no automatic RPC replay. Connection
  options allow deployments to supply broker authentication/TLS. Token callbacks
  supply issued service JWTs, avoiding distribution of the signing secret.
- Native bus helpers preserve Stage 1 subject, stream, and consumer names. Queue
  delivery remains at least once with explicit consumer acknowledgements.
- Cache's existing RPC adapter is wired to the engine's cold tier. No change to
  tiering semantics or exposure of process-local model objects is implied.
- The demo starts a real Engine and real loopback JetStream broker, then launches a
  wheel-installed worker in an isolated environment. It checks every v1 RPC and
  all bus operations (including batch publication), verifies mutations, lists unsupported behavior, and writes
  a report containing process IDs and installed packages.

## Consequences

The worker installs only four packages (proto, SDK, protobuf, nats-py). Schemas and
SDK clients are generated with pinned tooling and checked in. Packages start at
0.1.0; publication must release proto before core/SDK versions requiring it.
Local UV source overrides support development before publication.

This is an independent module process, not a workload scheduler or a module
registration/heartbeat system. It does not implement the workload-service draft.
The demo uses filesystem/SQLite/DuckLake/Oxigraph/local Qdrant backends and in-memory
coding/source-control providers; it verifies NATS/service contracts, not external
forge or workspace-provider integration. Email is written locally, not delivered.

Service JWT authorization is still the Stage 1 shared-trust model: a valid token
can access exposed secrets and administrative endpoints. Broker subject ACLs are
separate. No per-resource authorization or new security guarantees are introduced.
No persistence adapter is added. Existing v1 schemas have no Protovalidate annotations;
validation remains server-side and that gap is explicitly documented.

The demo exposed stale dotenv reads/listing and nonpersistent removals. Updating
the existing adapter's cache and file on mutation is necessary for the verified
secret lifecycle; a regression test covers reads, listing, removal, and reopening.
