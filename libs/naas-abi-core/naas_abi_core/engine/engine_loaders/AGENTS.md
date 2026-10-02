# Engine composition loaders

## Purpose
Load configured domain owners and modules, then inject service dependencies.

## Files
- EngineServiceLoader.py: local service owners and transitive requirements.
- EngineNATSLoader.py: endpoints wrapping owners, never the client view.
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

## Tests
Run EngineNATSLoader_test.py, EngineNATSDependencies_test.py, and the engine's
optional-NATS/shutdown tests. `make demo-sdk` verifies real broker traffic,
cache hot/cold chains, module lifecycle, and worker dependency isolation.
