# OpenRouterAPIIntegration_get_current_api_key

## What it is
- A small CLI script that fetches metadata about the currently configured OpenRouter API key and prints it as pretty-formatted JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Retrieves the OpenRouter integration via `get_integration()`
  - Calls `integration.get_current_api_key()`
  - Prints the returned object as JSON to stdout
  - Returns exit code `0`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
  - An integration object exposing `get_current_api_key()`
- Runtime dependencies:
  - Python standard library: `json`, `sys`

## Usage
### Run as a script
```bash
python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/scripts/OpenRouterAPIIntegration_get_current_api_key.py
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_get_current_api_key import main

raise SystemExit(main())
```

## Caveats
- Output format is always JSON with `indent=2`; the exact fields depend on what `integration.get_current_api_key()` returns.
- The `argv` parameter is accepted but not used by this script.
