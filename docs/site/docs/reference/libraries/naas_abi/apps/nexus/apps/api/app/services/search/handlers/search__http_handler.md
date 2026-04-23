# `search__http_handler`

## What it is
- A thin module that re-exports the `router` object for the Search HTTP handler layer.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary`.
  - Exposed via `__all__` so it can be imported from this module.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.router`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.search.handlers.search__http_handler import router
```

## Caveats
- This module defines no handlers itself; it only re-exports `router`.
