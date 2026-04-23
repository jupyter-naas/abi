# IEngine

## What it is
- Defines a lightweight engine interface with:
  - A `Services` container for core infrastructure services (KV, bus, storage, etc.).
  - A `modules` registry.
- Includes a `ServicesAware` protocol for services that need to receive the full `Services` set.

## Public API

### `ServicesAware` (Protocol)
- `set_services(services: IEngine.Services) -> None`
  - Implement to receive a reference to the engine’s `Services` container.

### `IEngine`
- `services: IEngine.Services` (property)
  - Access the engine’s service container.
- `modules: Dict[str, BaseModule]` (property)
  - Access registered modules by name.

### `IEngine.Services`
Container for optional service instances, with guarded accessors.

**Constructor**
- `IEngine.Services(..., object_storage=None, triple_store=None, vector_store=None, secret=None, bus=None, kv=None, email=None, cache=None)`
  - Stores references to provided service instances (each may be `None`).

**Service accessors (raise `AssertionError` if not initialized)**
- `kv -> KeyValueService`
- `object_storage -> ObjectStorageService`
- `triple_store -> TripleStoreService`
- `vector_store -> VectorStoreService`
- `secret -> Secret`
- `bus -> BusService`
- `email -> EmailService`
- `cache -> CacheService`

**Availability checks**
- `triple_store_available() -> bool`
- `cache_available() -> bool`

**Bulk access**
- `all -> List[Union[...]]` (property)
  - Returns a list of all service slots (may include `None`) in this order:
    1. object_storage
    2. triple_store
    3. vector_store
    4. secret
    5. bus
    6. kv
    7. email
    8. cache

**Wiring**
- `wire_services() -> None`
  - Iterates over `all`; for each non-`None` service that satisfies `isinstance(service, ServicesAware)`, calls `service.set_services(self)`.

## Configuration/Dependencies
- Imports service types from `naas_abi_core.services.*`:
  - `BusService`, `CacheService`, `EmailService`, `KeyValueService`
  - `ObjectStorageService`, `Secret`, `TripleStoreService`, `VectorStoreService`
- `modules` values are `BaseModule` (imported only under `TYPE_CHECKING`).

## Usage
```python
from naas_abi_core.engine.IEngine import IEngine, ServicesAware

class MyService(ServicesAware):
    def set_services(self, services: IEngine.Services) -> None:
        # Example: store a reference for later use
        self.services = services

# Instantiate services container with whatever concrete services you have (or None)
services = IEngine.Services(
    kv=None,
    object_storage=None,
    triple_store=None,
    vector_store=None,
    secret=None,
    bus=None,
    email=None,
    cache=None,
)

# Wire cross-service references for ServicesAware implementations
services.wire_services()
```

## Caveats
- Accessing a service property (e.g., `services.kv`) when it was not provided raises `AssertionError` with a clear message.
- `wire_services()` only wires objects that pass `isinstance(service, ServicesAware)`; plain objects without that protocol method are ignored.
