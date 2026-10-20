# CacheServiceConfiguration

## What it is
Engine configuration models and loader for the Cache service. It supports a *stack* of cache adapters split into tiers (e.g., `hot`, `cold`) and produces a `CacheService` instance wired with the requested adapters.

Supported adapter types:
- `fs` (filesystem)
- `redis` (Redis)
- `object_storage` (lazy adapter wired with engine `ObjectStorageService` during startup)
- `keyvalue` (lazy adapter wired with engine KV service during startup)
- `nats_rpc` (NATS request/reply cache secondary client)
- `custom` (loaded via `GenericLoader`)

## Public API

### Constants
- `TIER_HOT = "hot"`
- `TIER_COLD = "cold"`

### Configuration models (Pydantic)
- `CacheAdapterFSConfiguration`
  - Fields:
    - `base_path: str = "storage/cache"`
  - `extra="forbid"`

- `CacheAdapterRedisConfiguration`
  - Fields:
    - `redis_url: str = "redis://localhost:6379/0"`
    - `prefix: str = "naas:cache"`
    - `socket_timeout: float | None = None`
  - `extra="forbid"`

- `CacheAdapterObjectStorageConfiguration`
  - Fields:
    - `cache_prefix: str = "cache"`
  - `extra="forbid"`

- `CacheAdapterNATSConfiguration`
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str` (required)
    - `service_identity: str = "api"`
  - `extra="forbid"`

### Adapter entry / loader
- `CacheAdapterEntry(GenericLoader)`
  - Purpose: represents one adapter definition in the cache stack.
  - Fields:
    - `adapter: Literal["fs","redis","object_storage","keyvalue","nats_rpc","custom"]`
    - `tier: str = "cold"`
    - `config: dict | None = None`
  - Methods:
    - `load_adapter() -> ICacheAdapter`
      - Instantiates the concrete adapter for `fs`, `redis`, `object_storage`, `keyvalue`, `nats_rpc`, or delegates to `GenericLoader.load()` for `custom`.
    - `local_storage(object_storage: str | None = None, keyvalue: str | None = None) -> str | None`
      - Returns a human-readable description of where data is stored for this entry (when known).
  - Validation:
    - For non-`custom`, `config` is required.
    - For known adapter types, `config` is validated against the corresponding Pydantic model (extra keys forbidden).

### Lazy / wiring-time adapters
- `ObjectStorageBackedAdapter(ICacheAdapter)`
  - Purpose: placeholder adapter that becomes a real `CacheObjectStorageAdapter` after `wire_services(services)` is called.
- `KeyValueBackedAdapter(ObjectStorageBackedAdapter)`
  - Purpose: same lazy-wiring behavior, becomes a `CacheKeyValueAdapter` after `wire_services(services)`.

### Service configuration
- `CacheServiceConfiguration(BaseModel)`
  - Fields:
    - `adapters: list[CacheAdapterEntry]`
      - Default: single `fs` adapter in `cold` tier with `base_path="storage/cache"`.
  - Methods:
    - `load() -> CacheService`
      - Builds `CacheService(adapters=[(tier, adapter_instance), ...])`.

## Configuration/Dependencies
- `fs` adapter:
  - Uses `naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter`.
- `redis` adapter:
  - Uses `naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter`.
  - Requires the `redis` Python package (per module docstring).
- `object_storage` adapter:
  - Uses `CacheObjectStorageAdapter`, but only after `ObjectStorageBackedAdapter.wire_services()` injects `services.object_storage`.
- `keyvalue` adapter:
  - Uses `CacheKeyValueAdapter`, but only after `KeyValueBackedAdapter.wire_services()` injects `services.kv`.
- `nats_rpc` adapter:
  - Uses `CacheSecondaryAdapterNATSClient` with `nats_url`, `jwt_secret`, and `service_identity`.
- `custom` adapter:
  - Loaded via `GenericLoader` (external configuration determines what class to load).

## Usage

### Create a default cache service (filesystem, cold tier)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CacheService import (
    CacheServiceConfiguration,
)

cfg = CacheServiceConfiguration()
cache_service = cfg.load()
```

### Configure Redis (hot) + filesystem (cold)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CacheService import (
    CacheServiceConfiguration,
    CacheAdapterEntry,
    TIER_HOT,
    TIER_COLD,
)

cfg = CacheServiceConfiguration(
    adapters=[
        CacheAdapterEntry(
            adapter="redis",
            tier=TIER_HOT,
            config={"redis_url": "redis://localhost:6379/0", "prefix": "naas:cache"},
        ),
        CacheAdapterEntry(
            adapter="fs",
            tier=TIER_COLD,
            config={"base_path": "storage/cache"},
        ),
    ]
)

cache_service = cfg.load()
```

### Configure NATS RPC adapter (single tier)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CacheService import (
    CacheServiceConfiguration,
    CacheAdapterEntry,
)

cfg = CacheServiceConfiguration(
    adapters=[
        CacheAdapterEntry(
            adapter="nats_rpc",
            tier="cold",
            config={
                "nats_url": "nats://127.0.0.1:4222",
                "jwt_secret": "YOUR_JWT_SECRET",
                "service_identity": "api",
            },
        )
    ]
)
cache_service = cfg.load()
```

## Caveats
- `object_storage` and `keyvalue` adapters are not usable until wired:
  - They start as a placeholder that raises `RuntimeError` if called before `wire_services()` is executed (performed during engine startup via `CacheService.set_services()`).
- For all non-`custom` adapters, `config` is required and extra keys are rejected by the corresponding Pydantic model.
