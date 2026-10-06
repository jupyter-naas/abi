# Engine composition loaders

## Purpose
Load configured domain owners and modules, then inject service dependencies.

## Files
- EngineServiceLoader.py: local service owners and transitive requirements.
- EngineNATSLoader.py: endpoints wrapping owners, never the client view.
  `expose_overflow` starts the process's RPC overflow host (`nats_overflow`,
  `nats.rpc_overflow`) once primaries are exposed; shutdown stops it with them.
- EngineNATSDependencies.py: NATS-backed service facades, ordered cache tiers,
  and owned client cleanup.
- EngineModuleLoader.py: core module dependency resolution and lifecycle.

## Boundary
Without top-level NATS configuration, keep local references and optional imports.
With NATS, owners and modules receive client views. A service retains its own
persistence adapter but never receives another local owner in `self.services`.
The process-local model registry is available to module bootstrapping only; it
is deliberately absent from cross-domain dependencies.
Do not wire client wrappers to event services when their server-side domain
already emits events. Raw-adapter endpoints (cache/vector/event) have explicit
facade wiring. Only the triple-store owner bootstraps schema state.

Facades wait `nats.client_timeout_seconds` (default 10) for a reply; a route
configured to another engine (`adapter: nats_rpc`) keeps its own `timeout_seconds`.
Long dataset operations pass a deadline per call instead.

A secret fanout may mix local and remote adapters (`[dotenv, nats_rpc]`). The
endpoint serves only the local ones, so the global subject never routes into
itself. The facade reads them through one client to this engine's endpoint,
placed where the first local adapter stood, and keeps the remote ones for
upstream reads.

Kernel jobs (`Engine.job_owners`): dataset maintenance gets the engine's own
dataset service, like its endpoints. Jobs that service adapters offer
(`job_owners(services)`, such as the PostgreSQL event archive) work across
domains, so they receive the facades.

## Tests
Run EngineNATSLoader_test.py, EngineNATSDependencies_test.py, and the engine's
optional-NATS/shutdown tests. `make demo-sdk` verifies real broker traffic,
cache hot/cold chains, module lifecycle, and worker dependency isolation.
