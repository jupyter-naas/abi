# `files` Endpoint Export

## What it is
- A backward-compatible module that re-exports a FastAPI `router` for the “files” endpoints.

## Public API
- `router`
  - Imported from: `naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI`
  - Purpose: FastAPI router containing the files-related endpoints (actual routes are defined in the imported adapter module).

## Configuration/Dependencies
- Depends on the FastAPI adapter module:
  - `naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI`

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.files import router

app = FastAPI()
app.include_router(router)
```

## Caveats
- This module only re-exports `router`; it does not define any endpoints itself.
