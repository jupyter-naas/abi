# agents__http_handler

## What it is
A thin module that re-exports the HTTP `router` for the agents service, sourced from the primary adapter layer.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary`.
  - Intended to be included/registered in the application’s HTTP routing configuration.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.router`
- `__all__ = ["router"]` limits wildcard exports to `router`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.agents.handlers.agents__http_handler import router

# Example (framework-specific): include/register `router` in your app.
# app.include_router(router)
```

## Caveats
- This module contains no logic; behavior is entirely defined by the imported `router`.
