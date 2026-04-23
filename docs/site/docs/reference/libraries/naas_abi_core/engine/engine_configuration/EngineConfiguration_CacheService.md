# CacheServiceConfiguration

## What it is
Engine configuration models and loader for the Cache service. It supports a *stack* of cache adapters split into tiers (e.g., `hot`, `cold`) and produces a `CacheService` instance wired with the requested adapters.

Supported adapter types:
- `fs` (filesystem)
- `redis` (Redis)
- `object_storage` (uses engine `ObjectStorageService`, wired during engine startup)
- `custom` (loaded via `GenericLoader`)

## Public API

### Constants
- `TIER_HOT = "hot"`
- `TIER_COLD = "cold"`

### Configuration models
- `CacheAdapterFSConfiguration`
  - Fields: `base_path: str = "storage/cache"`
  - Extra keys forbidden.

- `CacheAdapterRedisConfiguration`
  - Fields: `redis_url: str`, `prefix: str`, `socket_timeout: float | None`
  - Defaults: `redis://localhost:6379/0`, `naas:cache`, `None`
  - Extra keys forbidden.

- `CacheAdapterObjectStorageConfiguration`
  - Fields: `cache_prefix: str = "cache"`
  - Extra keys forbidden.

### Loader / entry types
- `CacheAdapterEntry(GenericLoader)`
  - Represents one adapter definition in the cache stack.
  - Fields:
    - `adapter: Literal["fs", "redis", "object_storage", "custom"]`
    - `tier: str = "cold"`
    - `config: dict | None = None`
  - Methods:
    - `load_adapter() -> ICacheAdapter`
      - Instantiates the concrete adapter (or delegates to `GenericLoader.load()` for `custom`).
  - Validation:
    - For non-`custom`, `config` is required and validated against the corresponding pydantic config model.

### Service configuration
- `CacheServiceConfiguration(BaseModel)`
  - Fields:
    - `adapters: list[CacheAdapterEntry]`
      - Default: a single `fs` adapter in `cold` tier with `base_path="storage/cache"`.
  - Methods:
    - `load() -> CacheService`
      - Builds `CacheService(adapters=[(tier, adapter_instance), ...])`.

## Configuration/Dependencies
- `fs` adapter:
  - Uses `naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter`.
- `redis` adapter:
  - Uses `naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter`.
  - Requires the `redis` Python package (as indicated by module docstring).
- `object_storage` adapter:
  - Returns an `ObjectStorageBackedAdapter` placeholder that must be wired later via `wire_services(services)`, which injects `services.object_storage` and creates a `CacheObjectStorageAdapter`.

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

## Caveats
- `object_storage` adapter is *not usable before engine wiring*:
  - Until `wire_services()` is called (by `CacheService.set_services()` during engine startup), calls will raise `RuntimeError` via an internal no-op adapter.
- For `fs`, `redis`, and `object_storage`, `config` must be provided and must match the respective configuration schema (extra keys are rejected).
