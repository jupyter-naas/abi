# Cache Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/cache/`. This file is the canonical reference for agents working on the cache. Prefer it over external docs.

## Purpose

Multi-tier cache with explicit **hot** (fast, possibly volatile — Redis, in-memory) and **cold** (durable, slower — object storage, filesystem) tiers.

- **Read**: `cache.get(key)` → hot, then cold. **No automatic promotion** between tiers.
- **Write**: `cache.set_*(key, value)` → **cold only**. Explicit is explicit.
- **Delete**: `cache.delete(key)` → all tiers.

For explicit tier access, use `cache.hot.<method>` or `cache.cold.<method>`.

## Files

| File | Role |
|---|---|
| `CachePort.py` | Port interfaces (`ICacheAdapter`, `ICacheService`) + DTOs + exceptions |
| `CacheService.py` | Top-level service, decorator API, tier orchestration |
| `CacheFactory.py` | Pre-wired service builders |
| `adapters/secondary/` | Concrete adapters |
| `ontologies/` | RDF event classes |

## Port (`CachePort.py`)

```python
class ICacheAdapter:
    def get(key: str) -> CachedData              # raises CacheNotFoundError
    def set(key: str, value: CachedData) -> None
    def set_if_absent(key: str, value: CachedData) -> bool
    def delete(key: str) -> None                 # raises CacheNotFoundError
    def exists(key: str) -> bool
```

DTO: `CachedData(key, data, data_type: DataType, created_at)`. `DataType` ∈ `TEXT | JSON | BINARY | PICKLE`.

Exceptions: `CacheNotFoundError`, `CacheExpiredError`.

## Service API (`CacheService.py`)

```python
get(key, ttl=None)              → Any            # hot → cold; logs tier failures as warnings
exists(key)                     → bool           # hot first
delete(key)                     → None           # all tiers
set_text(key, value)            → None           # cold
set_json(key, value)            → None           # cold
set_binary(key, value)          → None           # cold
set_pickle(key, value)          → None           # cold
set_json_if_absent(key, value)  → bool           # cold
set_binary_if_absent(key, value)→ bool           # cold

# tier views
cache.hot                       → CacheService   # raises if no hot tier
cache.cold                      → CacheService   # falls back to last adapter
cache.hot_available()           → bool

# decorator (defaults to cold tier)
@cache(key_builder, cache_type=DataType.JSON, ttl=None, auto_cache=True)
@cache.hot(key_builder, cache_type=DataType.JSON)
```

## Available Adapters (`adapters/secondary/`)

| Adapter | Backend |
|---|---|
| `CacheFSAdapter` | Filesystem (JSON files, SHA256 key hashing) |
| `CacheRedisAdapter` | Redis (`{prefix}:{sha256_key}`, JSON) |
| `CacheObjectStorageAdapter` | S3-compatible (`{prefix}/entries/{sha256_key}.json`) |

## Factory (`CacheFactory.py`)

```python
CacheFactory.CacheFS_find_storage(subpath="cache", needle="storage") -> CacheService
CacheFactory.CacheObjectStorage(object_storage, cache_prefix="cache") -> CacheService
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/cache/
uv run pytest libs/naas-abi-core/naas_abi_core/services/cache/CacheService_test.py
```

## Adding a new adapter

1. Implement `ICacheAdapter` in `adapters/secondary/<Name>Adapter.py`. All five methods. `set_if_absent` may raise `NotImplementedError` (service falls back to check-then-act).
2. Add a `<Name>Adapter_test.py` next to it.
3. If the adapter has a stable, off-the-shelf setup, add a `CacheFactory.<Name>(...)` helper.
4. Verify against the generic contract by writing tests that exercise the public `ICacheAdapter` surface — same shape as the existing `_test.py` siblings.

## NATS RPC adapters

`adapters/primary/cache__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/CacheSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/cache/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
