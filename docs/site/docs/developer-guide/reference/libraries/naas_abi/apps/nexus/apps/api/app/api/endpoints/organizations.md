# organizations

## What it is
- A backward-compatible export module for the Organizations API endpoints.
- Re-exports FastAPI routers from the `services.organizations.handlers` module.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.organizations.handlers`.
  - Intended as the primary Organizations endpoints router.
- `public_router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.organizations.handlers`.
  - Intended as a public-facing Organizations endpoints router.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.organizations.handlers` providing `router` and `public_router`.
- Exports controlled via:
  - `__all__ = ["router", "public_router"]`

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.organizations import router, public_router

app = FastAPI()

app.include_router(router)
app.include_router(public_router)
```

## Caveats
- This module defines no routes itself; it only re-exports routers from `services.organizations.handlers`.
