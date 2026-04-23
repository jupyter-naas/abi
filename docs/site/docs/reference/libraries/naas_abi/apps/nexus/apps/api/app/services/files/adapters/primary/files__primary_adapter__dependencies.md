# files__primary_adapter__dependencies

## What it is
FastAPI dependency providers for the Files API:
- Lazily resolves and caches an `ObjectStorageService` on `request.app.state`.
- Constructs a `FilesService` using that storage.

## Public API
- `get_object_storage(request: Request) -> ObjectStorageService`
  - Returns an initialized `ObjectStorageService`.
  - Caches the instance on `request.app.state.object_storage`.
  - Raises `HTTPException(500)` if storage cannot be initialized via `naas_abi.ABIModule`.

- `get_files_service(storage: ObjectStorageService = Depends(get_object_storage)) -> FilesService`
  - Returns a `FilesService(storage=...)` for use in route handlers.

## Configuration/Dependencies
- Requires FastAPI request context (`Request`) and dependency injection (`Depends`).
- Looks for `request.app.state.object_storage` first.
- Fallback initialization path:
  - Imports `naas_abi.ABIModule`
  - Uses `ABIModule.get_instance().engine.services.object_storage`

## Usage
```python
from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

router = APIRouter()

@router.get("/files")
def list_files(files: FilesService = Depends(get_files_service)):
    # Use files service methods here (not shown in this module)
    return {"ok": True}
```

## Caveats
- If the API is not loaded through `naas_abi.ABIModule` and `app.state.object_storage` is not set, `get_object_storage` raises `HTTPException` with status code `500`.
- Storage initialization is cached per FastAPI app instance via `app.state`.
