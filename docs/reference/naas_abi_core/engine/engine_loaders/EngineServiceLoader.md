# EngineServiceLoader

## What it is
- A small loader that builds an `IEngine.Services` container based on which services are required by loaded modules.
- It consults an `EngineConfiguration` to instantiate services and wires them via `services.wire_services()`.

## Public API
- `class EngineServiceLoader`
  - `__init__(configuration: EngineConfiguration)`
    - Stores the engine configuration used to load service instances.
  - `load_services(module_dependencies: Dict[str, ModuleDependencies]) -> IEngine.Services`
    - Collects requested service types from each module’s `ModuleDependencies.services`.
    - Loads only the required services from `EngineConfiguration.services.*.load()`.
    - Calls `wire_services()` on the resulting `IEngine.Services` container.
  - `_should_load_service(service_type: type, services_to_load: List[type]) -> bool`
    - Helper to decide whether a given service should be loaded.
    - Also loads implicit dependencies defined in `SERVICES_DEPENDENCIES`.

## Configuration/Dependencies
- Requires an `EngineConfiguration` instance that exposes loaders under:
  - `configuration.services.object_storage.load()`
  - `configuration.services.triple_store.load()`
  - `configuration.services.vector_store.load()`
  - `configuration.services.secret.load()`
  - `configuration.services.bus.load()`
  - `configuration.services.kv.load()`
- Uses module requirements from `ModuleDependencies.services` (a list of service types).
- Implicit service dependency map:
  - `TripleStoreService` depends on `BusService`
    - If `TripleStoreService` is requested, `BusService` will also be loaded (even if not explicitly requested).
- Logs the resolved unique service types list via `naas_abi_core.logger.debug`.

## Usage
```python
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

# module_dependencies must map module names to ModuleDependencies instances,
# each containing a `.services` list of service types to request.
module_dependencies = {
    # "my_module": ModuleDependencies(services=[...], ...)
}

configuration = EngineConfiguration(...)  # must be properly constructed for your environment
loader = EngineServiceLoader(configuration)

services = loader.load_services(module_dependencies)
# services is an IEngine.Services container with requested services loaded (others are None).
```

## Caveats
- Any service not requested (directly or via `SERVICES_DEPENDENCIES`) is set to `None` in `IEngine.Services`.
- Only the dependency `TripleStoreService -> BusService` is handled; no other dependency relationships are defined in this file.
