# `api_router`

## What it is
- A FastAPI `APIRouter` instance that aggregates and mounts all endpoint routers for the Nexus API application.

## Public API
- `api_router: fastapi.APIRouter`
  - Main router that includes sub-routers under specific URL prefixes and OpenAPI tags:
    - `/auth` (`tags=["auth"]`)
    - `/organizations` (`tags=["organizations"]`)
    - `/organizations` public router (`tags=["organizations-public"]`)
    - `/workspaces` (`tags=["workspaces"]`)
    - `/chat` (`tags=["chat"]`)
    - `/search` (`tags=["search"]`)
    - `/ontology` (`tags=["ontology"]`)
    - `/graph` (`tags=["graph"]`)
    - `/agents` (`tags=["agents"]`)
    - `/files` (`tags=["files"]`)
    - `/secrets` (`tags=["secrets"]`)
    - `/providers` (`tags=["providers"]`)
    - `/websocket` (`tags=["websocket"]`)
    - `/abi` (`tags=["abi"]`)
    - `/abi` (`tags=["abi-sync"]`)
    - `/tenant` (`tags=["tenant"]`)

## Configuration/Dependencies
- Depends on:
  - `fastapi.APIRouter`
  - Endpoint modules imported from `naas_abi.apps.nexus.apps.api.app.api.endpoints`:
    - `abi`, `abi_sync`, `agents`, `auth`, `chat`, `files`, `graph`, `ontology`,
      `organizations`, `providers`, `search`, `secrets`, `tenant`, `websocket`, `workspaces`

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.router import api_router

app = FastAPI()
app.include_router(api_router, prefix="/api")
```

## Caveats
- Two routers are mounted under the same prefix `"/abi"` (one tagged `"abi"`, one tagged `"abi-sync"`). Route conflicts depend on the endpoints defined in those routers.
