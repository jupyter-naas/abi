# websocket__http_handler

## What it is
A thin module that re-exports a `router` object from the WebSocket primary adapter layer, making it available under this handler path.

## Public API
- `router`
  - Imported from `naas_abi.apps.nexus.apps.api.app.services.websocket.adapters.primary`.
  - Re-exported via `__all__` for consumers to import from this module.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.websocket.adapters.primary.router`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.websocket.handlers.websocket__http_handler import router

# Use `router` as provided by the adapters.primary module.
```

## Caveats
- This module contains no logic; behavior and type of `router` are defined entirely in the upstream `adapters.primary` implementation.
