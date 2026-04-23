# EngineServiceLoader

## What it is
- A small loader that instantiates engine services based on module-declared service dependencies.
- Uses an `EngineConfiguration` to `load()` only the services that are needed, then wires them via `IEngine.Services.wire_services()`.

## Public API
- `class EngineServiceLoader`
  - `__init__(configuration: EngineConfiguration)`
    - Stores the engine configuration used to load services.
  - `load_services(module_dependencies: Dict[str, ModuleDependencies]) -> IEngine.Services`
    - Collects requested service types from `module_dependencies`.
    - Loads only those services (plus any implicit dependencies defined in `SERVICES_DEPENDENCIES`).
    - Calls `wire_services()` on the resulting `IEngine.Services` and returns it.

## Configuration/Dependencies
- Requires:
  - `EngineConfiguration` with `services.<service>.load()` factories for:
    - `object_storage`, `triple_store`, `vector_store`, `secret`, `bus`, `kv`, `email`, `cache`
  - `module_dependencies: Dict[str, ModuleDependencies]` where each `ModuleDependencies.services` is a list of service types (classes).
- Implicit service dependencies (auto-loaded when needed):
  - If `TripleStoreService` is requested, `BusService` will also be loaded.
  - (Defined by `SERVICES_DEPENDENCIES = { TripleStoreService: [BusService] }`)

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.module.Module import ModuleDependencies

config = EngineConfiguration(...)  # must provide .services.*.load()
loader = EngineServiceLoader(config)

module_deps = {
    "my_module": ModuleDependencies(services=[TripleStoreService]),
}

services = loader.load_services(module_deps)

# services.triple_store is loaded, and services.bus is also loaded due to dependency
```

## Caveats
- Only dependencies encoded in `SERVICES_DEPENDENCIES` are automatically loaded (currently only `TripleStoreService -> BusService`).
- Services not requested (directly or via `SERVICES_DEPENDENCIES`) are set to `None` in `IEngine.Services`.
