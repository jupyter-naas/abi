# websocket

## What it is
- A thin, backward-compatible module that re-exports a WebSocket `router` used by the API app.

## Public API
- `router`: Imported from `naas_abi.apps.nexus.apps.api.app.services.websocket.handlers`
  - Purpose: Exposes the WebSocket routes/handlers via a single import path.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.websocket.handlers.router`

## Usage
```python
# Import the websocket router from the backward-compatible endpoint module
from naas_abi.apps.nexus.apps.api.app.api.endpoints.websocket import router

# Example integration (FastAPI)
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
```

## Caveats
- This module only re-exports `router`; all behavior is defined in `...services.websocket.handlers`.
