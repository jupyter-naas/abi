# EngineProxy

## What it is
A restricted view of an `IEngine` for a specific module. It:
- Exposes only the modules and services declared in the module’s dependencies (unless `unlocked=True`).
- Provides access to the engine API configuration (if available).

## Public API

### `class ServicesProxy`
Service accessor wrapper that enforces module-level service permissions.

- `object_storage -> ObjectStorageService`  
  Returns `engine.services.object_storage` if allowed.
- `triple_store -> TripleStoreService`  
  Returns `engine.services.triple_store` if allowed.
- `vector_store -> VectorStoreService`  
  Returns `engine.services.vector_store` if allowed.
- `secret -> Secret`  
  Returns `engine.services.secret` if allowed.
- `bus -> BusService`  
  Returns `engine.services.bus` if allowed.
- `kv -> KeyValueService`  
  Returns `engine.services.kv` if allowed.
- `email -> EmailService`  
  Returns `engine.services.email` if allowed.
- `cache -> CacheService`  
  Returns `engine.services.cache` if allowed.

Access control:
- If `unlocked=False` (default), accessing a service not listed in `module_dependencies.services` raises `ValueError`.

---

### `class EngineProxy`
Engine wrapper that enforces module-level module/service permissions.

- `modules -> Dict[str, BaseModule]`  
  Returns accessible modules:
  - If `unlocked=True`: all engine modules except the caller module itself.
  - If `unlocked=False`: only modules listed in `module_dependencies.modules`.
    - Supports soft dependencies via `"<name>#soft"`: if missing in `engine.modules`, it is ignored.
- `services -> ServicesProxy`  
  Returns the service proxy enforcing service access control.
- `api_configuration -> ApiConfiguration`  
  Returns `engine.configuration.api`.  
  Raises `RuntimeError` if the engine has no `.configuration` or it lacks `.api`.

## Configuration/Dependencies
- Requires an `engine` implementing `naas_abi_core.engine.IEngine`.
- Requires module dependency data (`ModuleDependencies`) providing:
  - `services`: a collection of allowed service types (e.g., `ObjectStorageService`, `BusService`, etc.).
  - `modules`: a collection of allowed module names (strings), optionally suffixed with `#soft`.
- `api_configuration` depends on `engine.configuration.api` being present.

## Usage
```python
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.services.bus.BusService import BusService

# engine: IEngine
# module_dependencies: has attributes:
#   - services: e.g., {BusService}
#   - modules: e.g., {"other_module", "optional_module#soft"}

proxy = EngineProxy(engine, module_name="my_module", module_dependencies=module_dependencies)

# Allowed service access
bus = proxy.services.bus

# Allowed module access (filtered by dependencies)
deps_modules = proxy.modules

# Engine API configuration (if engine.configuration.api exists)
api_cfg = proxy.api_configuration
```

## Caveats
- Unauthorized service access raises `ValueError`.
- `api_configuration` raises `RuntimeError` when `engine.configuration.api` is not available.
- Soft module dependencies (`#soft`) are silently skipped if the module is not present in `engine.modules`; non-soft missing modules will raise a `KeyError` when accessed during proxy module collection.
