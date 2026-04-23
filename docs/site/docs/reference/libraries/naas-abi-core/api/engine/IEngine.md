# IEngine

## What it is
- Defines the core engine interface/container for:
  - A set of shared services (`IEngine.Services`)
  - A registry of loaded modules (`modules`)
- Provides a small wiring mechanism to let services reference each other when they implement a known protocol (`ServicesAware`).

## Public API

### `ServicesAware` (Protocol)
- `set_services(self, services: IEngine.Services) -> None`
  - Implement on a service to receive the engine’s `Services` container.

### `IEngine`
- `services: IEngine.Services` (property)
  - Returns the engine service container.
- `modules: Dict[str, BaseModule]` (property)
  - Returns the module registry keyed by module name.

### `IEngine.Services`
Container for optional engine services, with guarded accessors.

**Constructor**
- `Services(object_storage=None, triple_store=None, vector_store=None, secret=None, bus=None, kv=None)`

**Service accessors (raise `AssertionError` if missing)**
- `kv -> KeyValueService`
- `object_storage -> ObjectStorageService`
- `triple_store -> TripleStoreService`
- `vector_store -> VectorStoreService`
- `secret -> Secret`
- `bus -> BusService`

**Other methods/properties**
- `triple_store_available() -> bool`
  - Returns `True` if a triple store service was provided.
- `all -> List[Union[...]]`
  - Returns a list of all service instances (including `None` entries) in a fixed order.
- `wire_services() -> None`
  - For each non-`None` service in `all`, if it implements `ServicesAware`, calls `service.set_services(self)`.

## Configuration/Dependencies
- Depends on service types from `naas_abi_core.services.*`:
  - `ObjectStorageService`, `TripleStoreService`, `VectorStoreService`, `Secret`, `BusService`, `KeyValueService`
- `BaseModule` is only imported for typing (`TYPE_CHECKING`) from `naas_abi_core.module.Module`.

## Usage

```python
from naas_abi_core.engine.IEngine import IEngine, ServicesAware

class MyService(ServicesAware):
    def set_services(self, services: IEngine.Services) -> None:
        # Can now access other services via `services`
        if services.triple_store_available():
            _ = services.triple_store

# Provide service instances as available in your environment
services = IEngine.Services(
    object_storage=None,
    triple_store=None,
    vector_store=None,
    secret=None,
    bus=None,
    kv=None,
)

# Wire cross-service references (no-op unless services implement ServicesAware)
services.wire_services()
```

## Caveats
- Accessing a missing service via its property (e.g., `services.kv`) raises `AssertionError` with a clear message.
- `wire_services()` only calls `set_services` for services that are runtime-checkable instances of `ServicesAware`.
