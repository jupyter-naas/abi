# workspaces__http_handler

## What it is
A minimal module that re-exports the `router` object used as the primary HTTP adapter for the workspaces service.

## Public API
- `router`
  - Imported from: `naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary`
  - Purpose: Exposed for external modules to include/register the workspaces HTTP routes.

## Configuration/Dependencies
- Depends on `naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary` providing a `router` object.
- Uses `__all__ = ["router"]` to define the module’s public export surface.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.workspaces.handlers.workspaces__http_handler import router

# Example: include it in your application/router setup (framework-specific)
# app.include_router(router)
```

## Caveats
- This module only re-exports `router`; no routing behavior is defined here.
