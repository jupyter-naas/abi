# `catalog`

## What it is
- A generated catalog of the supported RPC surface.
- Exposes a single module-level constant, `OPERATIONS`, mapping service names to lists of supported operation names.

## Public API
- `OPERATIONS: dict[str, list[str]]`
  - Inventory of RPC operations grouped by service.
  - Keys include (non-exhaustive): `activity_log`, `cache`, `coding_environment`, `dataset`, `document`, `email`, `event`, `keyvalue`, `model_registry`, `object_storage`, `secret`, `source_control`, `tool_registry`, `triple_store`, `vector_store`.

## Configuration/Dependencies
- None.
- Pure-Python module; no imports.

## Usage
```python
from naas_abi_sdk.catalog import OPERATIONS

# List available services
print(sorted(OPERATIONS.keys()))

# List operations for a specific service
print(OPERATIONS["cache"])

# Check whether an operation is supported
service = "dataset"
op = "query"
print(op in OPERATIONS.get(service, []))
```

## Caveats
- This module only provides an inventory list; it does not implement or validate RPC calls.
- Contents are static data; any runtime availability/permissions are not represented here.
