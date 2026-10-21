# providers__http_handler

## What it is
A thin module that re-exports the `router` object used for HTTP handling in the providers service.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary`.
  - Intended to be the HTTP router entry-point for this handler module.

## Configuration/Dependencies
- Depends on: `naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary` providing `router`.
- `__all__ = ["router"]` limits wildcard exports to `router`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.providers.handlers.providers__http_handler import router

# Example (framework-specific usage depends on what `router` is):
# app.include_router(router)
print(router)
```

## Caveats
- This module contains no logic; all behavior is defined by the imported `router`.
