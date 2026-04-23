# `auth__http_handler`

## What it is
A thin module-level export that re-exports the `router` object for the auth HTTP handler layer.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary`
  - Intended to be used by the API framework to register auth-related HTTP routes.

## Configuration/Dependencies
- Depends on: `naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary`
  - This module must provide a `router` object.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.auth.handlers.auth__http_handler import router

# Example (framework-specific): include the router in your application
# app.include_router(router)
```

## Caveats
- This module only re-exports `router`; it defines no routes or logic itself.
