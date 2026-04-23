# ServiceBase

## What it is
- A small base class that provides convenient access to the API’s `IAMService` via a shared `ServiceRegistry` singleton.

## Public API
- `class ServiceBase`
  - `iam -> IAMService` (property)
    - Returns the `IAMService` instance from `ServiceRegistry.instance().iam`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.iam.service.IAMService` (type returned)
  - `naas_abi.apps.nexus.apps.api.app.services.registry.ServiceRegistry` (resolved at runtime inside the property)
- The `ServiceRegistry` must be initialized/configured so that `ServiceRegistry.instance().iam` is available.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.service_base import ServiceBase

class MyService(ServiceBase):
    def do_something(self):
        # Use the shared IAM service
        return self.iam

svc = MyService()
iam_service = svc.iam
```

## Caveats
- `iam` is resolved through `ServiceRegistry.instance()`; if the singleton is not set up or lacks an `iam` attribute, accessing `iam` will raise an error at runtime.
