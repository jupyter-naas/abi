# api_router

## What it is
- A FastAPI `APIRouter` instance that aggregates and mounts all Nexus API endpoint routers under their respective URL prefixes and tags.

## Public API
- `api_router: fastapi.APIRouter`
  - Main router used to include all sub-routers.

Included sub-routers (mounted on `api_router`):
- `/auth` (`tags=["auth"]`) from `auth_router`
- `/organizations` (`tags=["organizations"]`) from `organizations.router`
- `/organizations` (`tags=["organizations-public"]`) from `organizations.public_router`
- `/workspaces` (`tags=["workspaces"]`) from `workspaces_router`
- `/chat` (`tags=["chat"]`) from `chat_router`
- `/coding-environments` (`tags=["coding-environments"]`) from `coding_environment_router`
- `/slides` (`tags=["slides"]`) from `slides_router`
- `/documents` (`tags=["documents"]`) from `documents_router`
- `/sheets` (`tags=["sheets"]`) from `sheets_router`
- `/v1` (`tags=["openai"]`) from `openai_gateway_router`
- `/code-review` (`tags=["code-review"]`) from `code_review_router`
- `/platform` (`tags=["platform"]`) from `platform_router`
- `/search` (`tags=["search"]`) from `search.router`
- `/ontology` (`tags=["ontology"]`) from `ontology.router`
- `/graph` (`tags=["graph"]`) from `graph.router`
- `/view` (`tags=["view"]`) from `view.router`
- `/agents` (`tags=["agents"]`) from `agents_router`
- `/skills` (`tags=["skills"]`) from `skills_router`
- `/modules` (`tags=["modules"]`) from `modules_router`
- `/apps` (`tags=["apps"]`) from `apps_router`
- `/app-projects` (`tags=["app-projects"]`) from `app_projects_router`
- `/files` (`tags=["files"]`) from `files_router`
- `/datasets` (`tags=["datasets"]`) from `datasets_router`
- `/secrets` (`tags=["secrets"]`) from `secrets.router`
- `/providers` (`tags=["providers"]`) from `providers_router`
- `/websocket` (`tags=["websocket"]`) from `websocket.router`
- `/abi` (`tags=["abi"]`) from `abi.router`
- `/tenant` (`tags=["tenant"]`) from `tenant.router`
- `/transcribe` (`tags=["transcribe"]`) from `transcribe.router`
- `/speech` (`tags=["speech"]`) from `speech.router`
- `/analytics` (`tags=["analytics"]`) from `analytics.router`
- `/admin` (`tags=["admin"]`) from `admin.router`
- `/admin/system` (`tags=["sysadmin"]`) from `sysadmin_router`

## Configuration/Dependencies
- Requires `fastapi` (`APIRouter`).
- Depends on internal routers imported from:
  - `naas_abi.apps.nexus.apps.api.app.api.endpoints.*`
  - `naas_abi.apps.nexus.apps.api.app.services.*.handlers`

## Usage
Minimal example mounting this router in a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.router import api_router

app = FastAPI()
app.include_router(api_router)
```

## Caveats
- Two routers are included under the same prefix `/organizations` with different tags; any route path conflicts are resolved by FastAPI based on registration order and route definitions.
