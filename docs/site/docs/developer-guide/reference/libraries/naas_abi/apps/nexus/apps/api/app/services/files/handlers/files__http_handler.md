# `files__http_handler` (router export)

## What it is
- A thin module that re-exports the `router` object used as the primary HTTP adapter for the files service.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary`.
  - Intended to be included in an API application as the files HTTP router.

## Configuration/Dependencies
- Depends on: `naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary` providing a `router` symbol.
- Exposes: `__all__ = ["router"]` for explicit export control.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.files.handlers.files__http_handler import router

# Example integration (framework-specific wiring depends on what `router` is):
# app.include_router(router)
```

## Caveats
- This module contains no logic; behavior is entirely defined by the imported `router`.
