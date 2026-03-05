# EngineProxy

## What it is
- A proxy around an `IEngine` instance that enforces per-module access control.
- Provides:
  - Filtered access to other modules (`EngineProxy.modules`)
  - Controlled access to engine services via `ServicesProxy` (`EngineProxy.services`)

## Public API

### `class EngineProxy`
- **Constructor**
  - `EngineProxy(engine: IEngine, module_name: str, module_dependencies: ModuleDependencies, unlocked: bool = False)`
  - Purpose: create an engine view scoped to a module and its declared dependencies.
- **Properties**
  - `modules -> Dict[str, BaseModule]`
    - Purpose: access other modules allowed by `module_dependencies.modules`.
    - Behavior:
      - If `unlocked=True`: returns all engine modules except the requesting module itself.
      - If locked: returns only modules listed in `module_dependencies.modules`, supporting optional `#soft` suffix.
  - `services -> ServicesProxy`
    - Purpose: access engine services through a dependency-checked proxy.
  - `api_configuration -> ApiConfiguration`
    - Purpose: read API runtime configuration shared by the engine (for example `cors_origins`).
    - Behavior:
      - Returns `engine.configuration.api`.
      - Raises `RuntimeError` when API configuration is not available from the wrapped engine.

### `class ServicesProxy`
- **Constructor**
  - `ServicesProxy(engine: IEngine, module_name: str, module_dependencies: ModuleDependencies, unlocked: bool = False)`
  - Purpose: provide service access with dependency enforcement.
- **Service properties** (each returns the corresponding engine service; when locked, access is allowed only if the service type is listed in `module_dependencies.services`)
  - `object_storage -> ObjectStorageService`
  - `triple_store -> TripleStoreService`
  - `vector_store -> VectorStoreService`
  - `secret -> Secret`
  - `bus -> BusService`
  - `kv -> KeyValueService`

## Configuration/Dependencies
- Requires an `IEngine` that exposes:
  - `engine.modules: Dict[str, BaseModule]`
  - `engine.services.<service_name>` attributes for:
    - `object_storage`, `triple_store`, `vector_store`, `secret`, `bus`, `kv`
  - `engine.configuration.api`
- Requires `ModuleDependencies` with:
  - `services`: a collection of allowed service *types* (e.g., `ObjectStorageService`)
  - `modules`: a collection of module names (strings), optionally suffixed with `#soft`

## Usage

```python
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

# engine: IEngine (provided by your runtime)
# deps: ModuleDependencies (provided by your module system)

proxy = EngineProxy(
    engine=engine,
    module_name="my_module",
    module_dependencies=deps,
)

# Access allowed services (raises ValueError if not declared in deps.services)
obj_store = proxy.services.object_storage  # requires ObjectStorageService in deps.services

# Access allowed modules (filtered by deps.modules)
other_modules = proxy.modules
```

## Caveats
- When `unlocked=False` (default):
  - Accessing a service not declared in `module_dependencies.services` raises `ValueError`.
  - Accessing a module not present in `module_dependencies.modules` is not possible via `EngineProxy.modules`.
- `#soft` module dependency behavior:
  - If a dependency is listed as `"some_module#soft"` and that module is not present in `engine.modules`, it is silently skipped.
  - Without `#soft`, missing modules will result in a `KeyError` when building the returned mapping.
