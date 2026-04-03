# ADR: Cache Service and Lazy Loading for Services and Modules

- Status: Accepted
- Date: 2025-07-03

## Context

ABI's engine initialized all services and modules eagerly at startup. As the number of modules and integrations grew, startup time became a problem: every module, agent, and service was instantiated regardless of whether it would be used in that session. Additionally, there was no consistent mechanism to cache expensive computations (SPARQL queries, API calls, embedding lookups) across requests.

## Decision

Introduce two complementary mechanisms:

1. **`CacheService`** - a new first-class service port with a filesystem adapter (`CacheFSAdapter`). It provides a get/set/invalidate interface keyed on content-addressable hashes. A `CacheFactory` wires the service from config. The cache is used for LLM responses, intent mapping, and SPARQL query results.

2. **`LazyLoader`** - a wrapper that defers instantiation of services and modules until first access. Services and modules registered with `LazyLoader` are not initialized at startup; initialization occurs on the first call to the wrapped object.

## Consequences

### Positive
- Startup time scales sublinearly with the number of registered modules.
- Repeated expensive operations (embeddings, API calls) benefit from content-addressable caching without per-call cache key management.
- New modules can be added to the registry without impacting startup latency.

### Tradeoffs
- Lazy initialization means the first use of a module incurs its full initialization cost, which can cause unexpected latency spikes at runtime.
- Cache invalidation is file-system based; stale cache entries require manual or TTL-based cleanup.
- Errors in a lazily-loaded module surface later, making them harder to diagnose at startup.
