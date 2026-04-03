# ServiceBase

## What it is
- A minimal base class for services that need access to an engine’s service container (`IEngine.Services`).
- Provides wiring (`set_services`) and safe access (`services` property with an assertion).

## Public API
- `class ServiceBase`
  - `__init__(self) -> None`
    - Initializes the instance with no services wired.
  - `set_services(self, services: IEngine.Services) -> None`
    - Wires the service container into this service.
  - `services_wired(self) -> bool` (property)
    - Returns `True` if services have been wired; otherwise `False`.
  - `services(self) -> IEngine.Services` (property)
    - Returns the wired service container.
    - Asserts if services are not wired.

## Configuration/Dependencies
- Type dependency (for typing only): `naas_abi_core.engine.IEngine.IEngine`, specifically `IEngine.Services`.
- No runtime imports required for `IEngine` due to `TYPE_CHECKING`.

## Usage
```python
from naas_abi_core.services.ServiceBase import ServiceBase

svc = ServiceBase()
print(svc.services_wired)  # False

# In real usage, `engine_services` should be an instance of IEngine.Services.
engine_services = object()  # placeholder for example purposes
svc.set_services(engine_services)

print(svc.services_wired)   # True
print(svc.services)         # returns engine_services
```

## Caveats
- Accessing `services` before calling `set_services(...)` triggers an `AssertionError` with message `"Services are not wired"`.
