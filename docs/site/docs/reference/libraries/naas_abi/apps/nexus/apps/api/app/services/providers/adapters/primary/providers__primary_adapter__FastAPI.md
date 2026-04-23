# providers__primary_adapter__FastAPI

## What it is
- A FastAPI router module exposing an authenticated endpoint to list “available providers”.
- Wires together:
  - Authentication (`get_current_user_required`)
  - Database session (`get_db`)
  - Domain/service layer (`ProviderService`)
  - Postgres-backed secondary adapter (`ProvidersSecondaryAdapterPostgres`)
  - Response schema mapping (`to_provider_schema`)

## Public API
- **`router: fastapi.APIRouter`**
  - Router with a global dependency on `get_current_user_required` (auth required for all routes on this router).

- **`get_provider_service(db: AsyncSession = Depends(get_db)) -> ProviderService`**
  - FastAPI dependency provider that constructs a `ProviderService` using `ProvidersSecondaryAdapterPostgres(db=db)`.

- **`list_available_providers(current_user: User = Depends(get_current_user_required), service: ProviderService = Depends(get_provider_service)) -> list[Provider]`**
  - `GET /available`
  - Returns a list of provider schemas for the authenticated user.
  - Calls `service.list_available_providers(user_id=current_user.id)` and maps results via `to_provider_schema`.

## Configuration/Dependencies
- **FastAPI**
  - Uses `APIRouter`, `Depends`.
- **Auth**
  - `get_current_user_required` provides `current_user: User`.
- **Database**
  - `get_db` provides an `AsyncSession` (SQLAlchemy async).
- **Service/Adapters**
  - `ProviderService` uses `ProvidersSecondaryAdapterPostgres` for persistence access.
- **Schemas**
  - Response type: `list[Provider]`
  - Mapping: `to_provider_schema(domain_provider)`

## Usage
Minimal integration into a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary.providers__primary_adapter__FastAPI import router

app = FastAPI()
app.include_router(router, prefix="/providers", tags=["providers"])
```

This exposes:
- `GET /providers/available` (authentication required)

## Caveats
- The router enforces authentication globally via `dependencies=[Depends(get_current_user_required)]` and also injects `current_user` into the endpoint; missing/invalid auth will prevent access.
- Requires an async SQLAlchemy setup providing `AsyncSession` through `get_db`.
