# ServiceBase

## What it is
- A small base class for services that need access to an engine-provided `Services` container.
- Supports “wiring” dependencies after instantiation and provides a guard to ensure wiring happened.

## Public API
- `class ServiceBase`
  - `__init__(self) -> None`
    - Initializes the service with no wired services (`_services = None`).
  - `set_services(self, services: IEngine.Services) -> None`
    - Wires an `IEngine.Services` container into the service.
  - `services_wired(self) -> bool` (property)
    - Returns `True` if services have been wired; otherwise `False`.
  - `services(self) -> IEngine.Services` (property)
    - Returns the wired services container.
    - Raises an `AssertionError` if services are not wired.

## Configuration/Dependencies
- Type dependency (for typing only): `naas_abi_core.engine.IEngine.IEngine`, specifically `IEngine.Services`.
- No runtime imports from `IEngine` due to `TYPE_CHECKING`.

## Usage
```python
from naas_abi_core.services.ServiceBase import ServiceBase

class MyService(ServiceBase):
    def do_something(self):
        # Access wired services
        return self.services  # replace with actual service usage

svc = MyService()
assert not svc.services_wired

# Later: wire dependencies (engine would typically do this)
services_container = object()  # placeholder for IEngine.Services
svc.set_services(services_container)

assert svc.services_wired
_ = svc.services
```

## Caveats
- Accessing `services` before calling `set_services(...)` triggers:
  - `AssertionError: Services are not wired`.
