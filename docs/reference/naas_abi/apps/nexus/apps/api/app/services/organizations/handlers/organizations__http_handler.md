# organizations__http_handler

## What it is
A minimal HTTP handler module that re-exports organization-related API routers for use by the application.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary`
  - Purpose: internal/primary API router for organization endpoints (implementation defined in the adapter module).
- `public_router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary`
  - Purpose: public-facing API router for organization endpoints (implementation defined in the adapter module).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary` providing `router` and `public_router`.
- `__all__ = ["router", "public_router"]` restricts what is exported on `from ... import *`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.organizations.handlers.organizations__http_handler import (
    router,
    public_router,
)

# Example: include in a FastAPI app (if these are FastAPI APIRouters)
# from fastapi import FastAPI
# app = FastAPI()
# app.include_router(router)
# app.include_router(public_router)
```

## Caveats
- This module contains no routing logic itself; behavior is entirely defined by the imported routers in the adapter module.
