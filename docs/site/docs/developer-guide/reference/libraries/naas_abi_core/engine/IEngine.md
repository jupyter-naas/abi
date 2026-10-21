# IEngine

## What it is
- Defines an engine interface centered on:
  - A `Services` container holding references to optional infrastructure services (KV, bus, storage, etc.).
  - A `modules` registry (`dict[str, BaseModule]`).
- Provides a `ServicesAware` protocol so services can receive the full `Services` set via wiring.

## Public API

### `ServicesAware` (Protocol)
- `set_services(services: IEngine.Services) -> None`
  - Implement to receive a reference to the engine’s `Services` container.
  - Marked `@runtime_checkable`, enabling `isinstance(obj, ServicesAware)` checks.

### `IEngine`
- `services -> IEngine.Services` (property)
  - Returns the engine’s service container.
- `modules -> dict[str, BaseModule]` (property)
  - Returns registered modules keyed by name.
- `job_owners() -> dict[str, object]`
  - Returns a dict of job owners for this engine; currently `dict(self.modules)`.

### `IEngine.Services`
Container for optional service instances, with guarded accessors, availability checks, and wiring.

**Constructor**
- `IEngine.Services(..., object_storage=None, dataset=None, triple_store=None, vector_store=None, secret=None, bus=None, kv=None, email=None, cache=None, events=None, activity_log=None, model_registry=None, coding_environment=None, source_control=None, document=None)`
  - Stores references to the provided service instances (each may be `None`).

**Service accessors (raise `AssertionError` if not initialized)**
- `kv -> KeyValueService`
- `object_storage -> ObjectStorageService`
- `dataset -> DatasetService`
- `document -> DocumentService`
- `triple_store -> TripleStoreService`
- `vector_store -> VectorStoreService`
- `secret -> Secret`
- `bus -> BusService`
- `email -> EmailService`
- `cache -> CacheService`
- `events -> EventService`
- `activity_log -> ActivityLogService`
- `model_registry -> ModelRegistryService`
- `coding_environment -> CodingEnvironmentService`
- `source_control -> SourceControlService`

**Availability checks**
- `kv_available() -> bool`
- `object_storage_available() -> bool`
- `dataset_available() -> bool`
- `document_available() -> bool`
- `triple_store_available() -> bool`
- `vector_store_available() -> bool`
- `secret_available() -> bool`
- `bus_available() -> bool`
- `email_available() -> bool`
- `cache_available() -> bool`
- `events_available() -> bool`
- `activity_log_available() -> bool`
- `model_registry_available() -> bool`
- `coding_environment_available() -> bool`
- `source_control_available() -> bool`

**Bulk access**
- `all -> list[...]` (property)
  - Returns a list of all service slots (may include `None`) in this order:
    1. object_storage
    2. dataset
    3. document
    4. triple_store
    5. vector_store
    6. secret
    7. bus
    8. kv
    9. email
    10. cache
    11. events
    12. activity_log
    13. model_registry
    14. coding_environment
    15. source_control

**Wiring**
- `wire_services(dependencies: IEngine.Services | None = None) -> None`
  - Iterates over `all`; for each non-`None` service that satisfies `isinstance(service, ServicesAware)`, calls:
    - `service.set_services(dependencies)` if provided
    - otherwise `service.set_services(self)`

## Configuration/Dependencies
- Depends on service types from `naas_abi_core.services.*`, including:
  - `ObjectStorageService`, `DatasetService`, `DocumentService`
  - `TripleStoreService`, `VectorStoreService`
  - `Secret`, `BusService`, `KeyValueService`, `EmailService`, `CacheService`
  - `EventService`, `ActivityLogService`, `ModelRegistryService`
  - `CodingEnvironmentService`, `SourceControlService`
- `BaseModule` is imported only under `TYPE_CHECKING` for typing the `modules` dict.

## Usage
```python
from naas_abi_core.engine.IEngine import IEngine, ServicesAware

class MyService(ServicesAware):
    def set_services(self, services: IEngine.Services) -> None:
        self.services = services

# Create a services container (use real service instances where available)
services = IEngine.Services(
    kv=None,
    bus=None,
    object_storage=None,
    dataset=None,
    document=None,
)

# Wire cross-service references for ServicesAware implementations
services.wire_services()
```

## Caveats
- Accessing a service property (e.g., `services.kv`) when it was not provided raises `AssertionError` with a specific message.
- `wire_services()` only wires services that pass `isinstance(service, ServicesAware)`; other objects are ignored.
