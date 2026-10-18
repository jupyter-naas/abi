# `secrets__http_handler`

## What it is
- A thin HTTP handler module that re-exports a FastAPI `router` for the secrets service.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.primary.secrets__primary_adapter__FastAPI`.
  - Intended to be included in a FastAPI application.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.primary.secrets__primary_adapter__FastAPI.router` (the actual FastAPI router instance).

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.secrets.handlers.secrets__http_handler import router

app = FastAPI()
app.include_router(router)
```

## Caveats
- This module defines no routes itself; behavior is entirely determined by the imported `router`.
