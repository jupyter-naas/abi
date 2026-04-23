# workspaces

## What it is
A minimal endpoint module that re-exports the `router` used for workspace-related API routes.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.workspaces.handlers`
  - Intended to be included in the main API application/router composition.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.workspaces.handlers.router`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.api.endpoints.workspaces import router

# Example (FastAPI-style): include into your main app/router
# app.include_router(router)
```

## Caveats
- This module defines no routes itself; all route definitions live in `...services.workspaces.handlers`.
