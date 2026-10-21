# `chat__http_handler`

## What it is
- A thin HTTP handler module that re-exports a FastAPI `router` for the chat service.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI`.
  - Intended to be included in a FastAPI application to expose chat-related endpoints.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI.router`
- The actual routes/endpoints are defined in the referenced adapter module, not here.

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.chat.handlers.chat__http_handler import router

app = FastAPI()
app.include_router(router)
```

## Caveats
- This module defines no routes itself; it only re-exports `router` from the primary FastAPI adapter.
