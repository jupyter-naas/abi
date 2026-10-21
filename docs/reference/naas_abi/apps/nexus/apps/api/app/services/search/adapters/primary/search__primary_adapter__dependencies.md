# search__primary_adapter__dependencies

## What it is
- A small FastAPI dependency provider that retrieves a `SearchService` instance from a shared `ServiceRegistry`.

## Public API
- `get_search_service(registry: ServiceRegistry = Depends(get_service_registry)) -> SearchService`
  - FastAPI dependency function that returns `registry.search`.

## Configuration/Dependencies
- **FastAPI**
  - Uses `fastapi.Depends` for dependency injection.
- **Service registry**
  - `get_service_registry()` provides a `ServiceRegistry`.
  - The registry must expose a `.search` attribute that is a `SearchService`.

## Usage
```python
from fastapi import FastAPI, Depends
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.search__primary_adapter__dependencies import (
    get_search_service,
)
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService

app = FastAPI()

@app.get("/search")
def search_endpoint(search_service: SearchService = Depends(get_search_service)):
    # Use search_service here (methods depend on SearchService implementation)
    return {"service": search_service.__class__.__name__}
```

## Caveats
- This module assumes `ServiceRegistry.search` is available and returns a valid `SearchService`; otherwise dependency resolution will fail at runtime.
