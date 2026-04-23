# `providers` endpoint module

## What it is
- A thin, backward-compatible export for the **providers** API router.
- Re-exports the `router` defined in `naas_abi.apps.nexus.apps.api.app.services.providers.handlers`.

## Public API
- `router`
  - Purpose: FastAPI/APIRouter object containing providers-related endpoints (implemented in the handlers module).

## Configuration/Dependencies
- Imports:
  - `naas_abi.apps.nexus.apps.api.app.services.providers.handlers.router`
- Export control:
  - `__all__ = ["router"]` limits what gets exported on `from ... import *`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.api.endpoints.providers import router

# Example (FastAPI):
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
```

## Caveats
- This module does not define endpoints itself; it only re-exports `router` from the handlers module.
