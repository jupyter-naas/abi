# ADR: BusService and KeyValueService as First-Class Platform Services

- Status: Accepted
- Date: 2026-02-05

## Context

ABI's engine had growing needs for async event passing (pipelines triggering downstream workflows) and lightweight ephemeral state storage (caching, session data, intent mappings). These were being handled ad hoc — direct in-process calls, local file writes, or implicit Dagster job coupling — with no consistent abstraction.

## Decision

Introduce `BusService` and `KeyValueService` as first-class ports in `naas-abi-core`, following the same hexagonal pattern as `TripleStoreService` and `VectorStoreService`.

**BusService** provides a publish/subscribe message bus with two adapter implementations:
- `rabbitmq` — production-grade durable queue (requires Docker container).
- `python_queue` — in-process SQLite-backed queue for local development, no external deps.

**KeyValueService** provides a simple get/set/delete interface with two adapter implementations:
- `redis` — production key-value store (requires Docker container).
- `python` — in-memory dictionary for local development, non-persistent.

Adapter selection is config-driven via `config.yaml`, consistent with the existing service configuration pattern.

## Consequences

### Positive
- Decouples pipeline producers from consumers via the bus.
- Provides a consistent, test-friendly KV abstraction across environments.
- Local development works without Redis or RabbitMQ by switching to in-process adapters.

### Tradeoffs
- In-process adapters are non-persistent and non-distributed; behavior diverges from production in subtle ways.
- Adds two more services to the engine bootstrap sequence, increasing startup complexity.
- RabbitMQ and Redis are now optional but expected in production deployments.
