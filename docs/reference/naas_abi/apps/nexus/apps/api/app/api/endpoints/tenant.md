# `tenant` (public tenant configuration endpoint)

## What it is
- A FastAPI router module exposing a **public (no-auth)** endpoint that returns tenant branding/configuration (e.g., tab title, favicon) for frontend initialization.

## Public API
- **`router: fastapi.APIRouter`**
  - Router instance registering the endpoint(s) in this module.
- **`get_tenant_config() -> TenantResponse`**
  - `GET ""` (router root)
  - Returns tenant configuration as `TenantResponse` by delegating to `TenantService.get_tenant_config()`.

## Configuration/Dependencies
- **FastAPI**
  - `APIRouter` for route registration.
- **Internal services/models**
  - `TenantService.get_tenant_config()` (async)
  - `TenantResponse` (response model)
- Branding values are described as configured in `config.yaml` (loaded/handled by the service layer, not this module).

## Usage
Minimal FastAPI app wiring:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import tenant

app = FastAPI()
app.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
```

Request:

```bash
curl http://localhost:8000/tenant
```

## Caveats
- This endpoint is **public** (“no auth required”); ensure it only returns non-sensitive configuration.
