# EngineServiceLoader

## What it is
- Loads and instantiates engine services based on module-declared dependencies.
- Adds implicit/transitive service dependencies (e.g., requesting object storage pulls events and bus).
- Supports a NATS mode where the engine loads a broader set of services to satisfy runtime-declared dependencies.

## Public API
- `class EngineServiceLoader`
  - `__init__(configuration: EngineConfiguration)`
    - Stores the `EngineConfiguration` used to instantiate services.
  - `load_services(module_dependencies: dict[str, ModuleDependencies]) -> IEngine.Services`
    - Determines which services to load from module dependencies and configuration.
    - Instantiates an `IEngine.Services` container with requested services (others set to `None`), plus always-loaded services.
    - If **not** in NATS mode, calls `services.wire_services()` before returning.
  - `local_backends(module_dependencies: dict[str, ModuleDependencies]) -> dict[str, str]`
    - Returns “local backend” locations for the services this engine will load, using `configuration.services.local_backends(...)`.

## Configuration/Dependencies
- Requires an `EngineConfiguration` that provides factories under `configuration.services.<name>.load()` for:
  - `activity_log`, `bus`, `cache`, `coding_environment`, `dataset`, `document`, `email`, `event`, `kv`, `model_registry`, `object_storage`, `secret`, `source_control`, `triple_store`, `vector_store`
- Implicit/transitive service dependencies (`SERVICES_DEPENDENCIES`):
  - `TripleStoreService -> BusService`
  - `EventService -> BusService`
  - `ObjectStorageService -> EventService` (transitively loads `BusService`)
- NATS mode behavior:
  - If `configuration.nats is not None`, the loader adds **all** `ON_DEMAND_SERVICES` to the load list (to support runtime dependency declarations).
  - Bus loading differs:
    - Without NATS: `configuration.services.bus.load()`
    - With NATS: constructs `BusService(NATSJetStreamAdapter(nats_url), emit_message_events=...)`
- Additional configuration-driven dependencies:
  - If `CacheService` requested, cache adapter entries may add:
    - `"object_storage"` -> loads `ObjectStorageService`
    - `"keyvalue"` -> loads `KeyValueService`
  - If `ActivityLogService` requested and `activity_log_adapter.adapter == "document"`:
    - loads `DocumentService`
- Always loaded (regardless of module dependencies):
  - `model_registry`, `coding_environment`, `source_control`
  - For `local_backends(...)`, also includes names: `coding_environment`, `source_control`

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

config = EngineConfiguration(...)  # must provide .services.*.load(), and optional .nats
loader = EngineServiceLoader(config)

module_deps = {
    "my_module": ModuleDependencies(services=[ObjectStorageService]),
}

services = loader.load_services(module_deps)
# ObjectStorageService implies EventService and BusService via transitive dependencies.
# Always available: services.model_registry, services.coding_environment, services.source_control
```

## Caveats
- In NATS mode (`configuration.nats is not None`), the loader does **not** call `services.wire_services()`.
- Only dependencies encoded in `SERVICES_DEPENDENCIES` and the configuration-driven rules (cache/activity_log) are auto-added; other relationships must be declared by modules.
