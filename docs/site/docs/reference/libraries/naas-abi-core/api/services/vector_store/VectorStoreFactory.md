# VectorStoreFactory

## What it is
- A small factory/singleton helper that:
  - Builds a vector store adapter based on environment variables.
  - Provides a singleton `VectorStoreService` instance using that adapter.
  - Allows resetting the singleton for reconfiguration/testing.

## Public API
- `class VectorStoreFactory`
  - `create_adapter() -> IVectorStorePort`
    - Creates and returns a vector store adapter selected by `VECTOR_STORE_ADAPTER`.
    - Currently supports: `qdrant` (default).
    - Raises `ValueError` for unknown adapter types.
  - `get_service() -> VectorStoreService`
    - Returns a singleton `VectorStoreService` initialized with the adapter from `create_adapter()`.
    - Lazily constructs the singleton on first call.
  - `reset() -> None`
    - Clears the cached singleton so the next `get_service()` call creates a new instance.

## Configuration/Dependencies
- Environment variables:
  - `VECTOR_STORE_ADAPTER` (default: `"qdrant"`)
  - When `VECTOR_STORE_ADAPTER=qdrant`:
    - `QDRANT_HOST` (default: `"localhost"`)
    - `QDRANT_PORT` (default: `"6333"`, converted to `int`)
    - `QDRANT_API_KEY` (optional)
    - `QDRANT_HTTPS` (default: `"false"`, `"true"` enables HTTPS)
    - `QDRANT_TIMEOUT` (default: `"30"`, converted to `int`)
- Dependencies (imported/used):
  - `VectorStoreService` (constructed with an `IVectorStorePort`)
  - `IVectorStorePort` (adapter interface)
  - `QdrantAdapter` (lazy imported from `.adapters.QdrantAdapter` when selected)
- Logging:
  - Uses module logger to log adapter creation and singleton lifecycle events.

## Usage
```python
import os
from naas_abi_core.services.vector_store.VectorStoreFactory import VectorStoreFactory

# Configure (optional; defaults shown)
os.environ["VECTOR_STORE_ADAPTER"] = "qdrant"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"

service = VectorStoreFactory.get_service()

# Reset to force recreation with new environment configuration
VectorStoreFactory.reset()
service2 = VectorStoreFactory.get_service()
```

## Caveats
- Only the `"qdrant"` adapter type is supported; any other value in `VECTOR_STORE_ADAPTER` raises `ValueError`.
- `QDRANT_PORT` and `QDRANT_TIMEOUT` must be valid integers; invalid values will raise `ValueError` during conversion.
- `get_service()` returns a process-wide singleton; use `reset()` if you need to reinitialize with different environment settings.
