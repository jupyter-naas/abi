# `chat` (FastAPI router export)

## What it is
- A backward-compatible module that re-exports the FastAPI `router` for the chat endpoint.
- The primary FastAPI adapter implementation lives in the chat domain package.

## Public API
- `router`
  - FastAPI `APIRouter` imported from `naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI`.

## Configuration/Dependencies
- Depends on the chat primary adapter module:
  - `naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI`
- Exports only `router` via `__all__`.

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.chat import router as chat_router

app = FastAPI()
app.include_router(chat_router)
```

## Caveats
- This module contains no endpoint definitions itself; it only re-exports `router` from the primary adapter.
