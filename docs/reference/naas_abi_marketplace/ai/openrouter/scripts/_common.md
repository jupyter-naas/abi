# `_common` (OpenRouter CLI shared helpers)

## What it is
Shared helper functions used by OpenRouter integration CLI scripts to:
- Load the OpenRouter module through the `naas_abi_core` engine when configured.
- Build a ready-to-use `OpenRouterAPIIntegration` from either module configuration or environment variables.

## Public API
- `ensure_module_loaded() -> BaseModule | None`
  - Returns the OpenRouter module instance if enabled/available; otherwise returns `None`.
  - If the module is not already available, it attempts to load it via the engine using `MODULE_NAME`.

- `get_integration()`
  - Builds and returns an `OpenRouterAPIIntegration` instance.
  - Source of configuration:
    - If the OpenRouter module is enabled: uses module configuration (`openrouter_api_key`, `datastore_path`) and the engine’s `object_storage` service.
    - Otherwise: uses `OPENROUTER_API_KEY` from environment, loads object storage via engine configuration, and defaults `datastore_path` to `"openrouter"`.
  - Raises `ValueError` if module is not enabled and `OPENROUTER_API_KEY` is not set.

## Configuration/Dependencies
- Environment
  - `.env` is automatically loaded at import time via `dotenv.load_dotenv()`.
  - `OPENROUTER_API_KEY` is required when the OpenRouter module is not enabled in `config.yaml`.

- Engine / module
  - Uses `naas_abi_core.engine.Engine` to load modules.
  - Loads configuration via `EngineConfiguration.load_configuration()`.
  - Uses object storage via `configuration.services.object_storage.load()` or `module.engine.services.object_storage`.

- Module name constant
  - `MODULE_NAME = "naas_abi_marketplace.applications.openrouter"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.scripts._common import get_integration

integration = get_integration()
# integration is an OpenRouterAPIIntegration instance
```

Environment-based fallback (when module is not enabled):
```bash
export OPENROUTER_API_KEY="your-key"
```

## Caveats
- Importing this module loads `.env` immediately (`load_dotenv()`), which may affect environment variable resolution.
- `get_integration()` raises `ValueError` if:
  - the OpenRouter module is not enabled/available, and
  - `OPENROUTER_API_KEY` is not set.
