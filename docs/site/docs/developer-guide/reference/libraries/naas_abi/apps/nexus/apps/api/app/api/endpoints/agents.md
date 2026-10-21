# `agents` endpoint module

## What it is
A backward-compatible export module that re-exports the FastAPI `router` for the agents endpoint.

## Public API
- `router`
  - FastAPI router imported from `naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI`.
- `__all__ = ["router"]`
  - Limits wildcard exports to `router`.

## Configuration/Dependencies
- Depends on the upstream module:
  - `naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI`
- Requires FastAPI (transitively, via the imported router).

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import agents

app = FastAPI()
app.include_router(agents.router)
```

## Caveats
- This module only re-exports `router`; all endpoint definitions and behavior live in the imported adapter module.
