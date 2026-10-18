# EngineProxy

## What it is
A restricted view of an `IEngine` for a specific module. It:
- Limits access to engine **services** based on the module’s declared dependencies (unless `unlocked=True`).
- Limits access to engine **modules** based on the module’s declared dependencies (with optional `#soft` dependencies).
- Exposes engine configuration and API configuration (if present).
- Provides additional “platform/admin” capabilities only when `unlocked=True`.

---

## Public API

### `class ServicesProxy`
Service accessor wrapper that enforces module-level service permissions.

Constructor:
- `ServicesProxy(engine: IEngine, module_name: str, module_dependencies: ModuleDependencies, unlocked: bool = False)`

Service properties (permission-checked unless noted):
- `object_storage -> ObjectStorageService`
- `dataset -> DatasetService`
- `document -> DocumentService`  
  Returns a per-module scoped view via `engine.services.document._for_namespace(module_name)`; cached and thread-safe.
- `triple_store -> TripleStoreService`
- `vector_store -> VectorStoreService`
- `secret -> Secret`
- `bus -> BusService`
- `kv -> KeyValueService`
- `email -> EmailService`
- `cache -> CacheService`
- `activity_log -> ActivityLogService`
- `events -> EventService`

Service availability helpers:
- `dataset_available() -> bool`
- `document_available() -> bool`
- `activity_log_available() -> bool`
- `events_available() -> bool`

Services exempt from dependency checks:
- `model_registry -> ModelRegistryService` (always accessible)
- `model_registry_available() -> bool`
- `coding_environment -> CodingEnvironmentService` (always accessible)
- `source_control -> SourceControlService` (always accessible)

Platform/admin-only service:
- `document_admin -> DocumentService`  
  Only when `unlocked=True`; otherwise raises `PermissionError`. Returns the engine’s document root service (not namespaced).

Access control behavior:
- If `unlocked=False`, accessing a non-declared service raises `ValueError`.
- `document_admin` requires `unlocked=True` and raises `PermissionError` otherwise.

---

### `class EngineProxy`
Engine wrapper that enforces module-level module/service permissions.

Constructor:
- `EngineProxy(engine: IEngine, module_name: str, module_dependencies: ModuleDependencies, unlocked: bool = False)`

Properties and methods:
- `modules -> dict[str, BaseModule]`  
  - If `unlocked=True`: returns all engine modules except the caller module itself.
  - If `unlocked=False`: returns only modules listed in `module_dependencies.modules`.
    - Supports soft dependencies using `"<name>#soft"`: skipped if absent.
    - Non-soft missing modules will raise `KeyError` during collection.
- `services -> ServicesProxy`  
  Returns the service proxy enforcing service access control.
- `job_owners() -> dict[str, object]`  
  Platform-only (`unlocked=True`). Otherwise raises `PermissionError`. Delegates to `engine.job_owners()`.
- `configuration`  
  Returns `engine.configuration` if present; otherwise raises `RuntimeError("Engine configuration is not available")`.
- `api_configuration -> ApiConfiguration`  
  Returns `engine.configuration.api` if present; otherwise raises `RuntimeError("Engine configuration API is not available")`.

---

## Configuration/Dependencies
- Requires an `engine` implementing `naas_abi_core.engine.IEngine`.
- Requires `module_dependencies` (type `ModuleDependencies`) providing:
  - `services`: a collection of allowed service **types** (e.g., `BusService`, `DocumentService`, …).
  - `modules`: a collection of module names (strings), optionally suffixed with `#soft`.
- `api_configuration` requires `engine.configuration` to exist and to have an `api` attribute.

---

## Usage
```python
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.services.bus.BusService import BusService

# engine: IEngine
# module_dependencies: ModuleDependencies with .services (types) and .modules (names)
proxy = EngineProxy(engine, module_name="my_module", module_dependencies=module_dependencies)

# Access an allowed service
bus = proxy.services.bus  # requires BusService in module_dependencies.services

# Check availability without raising on missing dependency declaration
if proxy.services.dataset_available():
    ds = proxy.services.dataset

# Get dependency-filtered modules (supports "name#soft")
deps_modules = proxy.modules

# Engine API configuration (if engine.configuration.api exists)
api_cfg = proxy.api_configuration
```

---

## Caveats
- Unauthorized service access raises `ValueError` (except for explicitly exempt services).
- `document_admin` and `job_owners()` require `unlocked=True` and raise `PermissionError` otherwise.
- Non-soft module dependencies missing from `engine.modules` cause a `KeyError` when building `modules`.
- `configuration` / `api_configuration` raise `RuntimeError` when the engine configuration (or its `api`) is not available.
