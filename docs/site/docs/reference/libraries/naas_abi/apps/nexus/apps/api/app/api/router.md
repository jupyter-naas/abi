# api_router

## What it is
- A FastAPI `APIRouter` instance that aggregates and mounts all API endpoint routers for the Nexus API application.

## Public API
- `api_router: fastapi.APIRouter`
  - Main router that includes sub-routers with defined URL prefixes and tags.

Included sub-routers (mounted on `api_router`):
- `/auth` (`tags=["auth"]`) from `auth_router`
- `/organizations` (`tags=["organizations"]`) from `organizations.router`
- `/organizations` (`tags=["organizations-public"]`) from `organizations.public_router`
- `/workspaces` (`tags=["workspaces"]`) from `workspaces_router`
- `/chat` (`tags=["chat"]`) from `chat_router`
- `/search` (`tags=["search"]`) from `search.router`
- `/ontology` (`tags=["ontology"]`) from `ontology.router`
- `/graph` (`tags=["graph"]`) from `graph.router`
- `/view` (`tags=["view"]`) from `view.router`
- `/agents` (`tags=["agents"]`) from `agents_router`
- `/files` (`tags=["files"]`) from `files_router`
- `/secrets` (`tags=["secrets"]`) from `secrets.router`
- `/providers` (`tags=["providers"]`) from `providers_router`
- `/websocket` (`tags=["websocket"]`) from `websocket.router`
- `/abi` (`tags=["abi"]`) from `abi.router`
- `/tenant` (`tags=["tenant"]`) from `tenant.router`
- `/transcribe` (`tags=["transcribe"]`) from `transcribe.router`

## Configuration/Dependencies
- Requires `fastapi` (uses `fastapi.APIRouter`).
- Depends on multiple internal routers imported from:
  - `naas_abi.apps.nexus.apps.api.app.api.endpoints.*`
  - `naas_abi.apps.nexus.apps.api.app.services.*.handlers`

## Usage
Minimal example mounting this router in a FastAPI application:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.router import api_router

app = FastAPI()
app.include_router(api_router)
```

## Caveats
- Two routers are mounted under the same prefix `/organizations` with different tags; path conflicts (if any) are determined by FastAPI routing rules and the order of inclusion in this file.
