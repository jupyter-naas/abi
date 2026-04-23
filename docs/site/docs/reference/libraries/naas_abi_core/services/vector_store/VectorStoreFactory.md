# VectorStoreFactory

## What it is
- A small factory/singleton provider for `VectorStoreService`.
- Creates a vector store adapter based on environment variables (currently only Qdrant).
- Lazily imports the Qdrant adapter to avoid importing `qdrant_client` at module import time.

## Public API
- `class VectorStoreFactory`
  - `create_adapter() -> IVectorStorePort`
    - Creates and returns an adapter instance based on `VECTOR_STORE_ADAPTER`.
    - Currently supports: `"qdrant"` only.
    - Raises `ValueError` for unknown adapter types.
  - `get_service() -> VectorStoreService`
    - Returns a singleton `VectorStoreService` instance.
    - On first call, creates an adapter via `create_adapter()` and wraps it in `VectorStoreService`.
  - `reset() -> None`
    - Clears the cached singleton so the next `get_service()` call rebuilds it.

## Configuration/Dependencies
- Environment variables:
  - `VECTOR_STORE_ADAPTER` (default: `"qdrant"`)
  - Qdrant-specific (used when adapter is `"qdrant"`):
    - `QDRANT_HOST` (default: `"localhost"`)
    - `QDRANT_PORT` (default: `"6333"`, parsed as `int`)
    - `QDRANT_API_KEY` (optional)
    - `QDRANT_HTTPS` (default: `"false"`, `"true"` enables HTTPS)
    - `QDRANT_TIMEOUT` (default: `"30"`, parsed as `int`)
- Dependencies (imported/used by this module):
  - `VectorStoreService`
  - `IVectorStorePort`
  - `.adapters.QdrantAdapter` (lazy-imported when needed)

## Usage
```python
import os
from naas_abi_core.services.vector_store.VectorStoreFactory import VectorStoreFactory

# Optional configuration
os.environ["VECTOR_STORE_ADAPTER"] = "qdrant"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"
os.environ["QDRANT_HTTPS"] = "false"
os.environ["QDRANT_TIMEOUT"] = "30"

service = VectorStoreFactory.get_service()

# To force re-creation (e.g., after changing env vars)
VectorStoreFactory.reset()
service2 = VectorStoreFactory.get_service()
```

## Caveats
- Only `"qdrant"` is supported; any other `VECTOR_STORE_ADAPTER` value raises `ValueError`.
- `QDRANT_PORT` and `QDRANT_TIMEOUT` must be valid integers or `int(...)` will raise an exception.
- `get_service()` returns a singleton; changes to environment variables won’t take effect unless `reset()` is called first.
