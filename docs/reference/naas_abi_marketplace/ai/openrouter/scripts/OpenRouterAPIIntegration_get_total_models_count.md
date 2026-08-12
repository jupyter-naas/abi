# OpenRouterAPIIntegration_get_total_models_count

## What it is
- A small CLI script that fetches the total count of available OpenRouter models via an integration object and prints the result as formatted JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Creates an OpenRouter integration instance (via `get_integration()`), calls `get_total_models_count()`, prints the JSON result, and returns exit code `0`.

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
  - This function is expected to return an integration object that implements `get_total_models_count()`.
- Uses standard library modules:
  - `json` for pretty-printing output
  - `sys` for CLI exit handling

## Usage
### Run as a script
```bash
python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/scripts/OpenRouterAPIIntegration_get_total_models_count.py
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_get_total_models_count import main

raise SystemExit(main())
```

## Caveats
- `argv` is accepted by `main()` but not used.
- Any required configuration (e.g., credentials) is handled inside `get_integration()`; this script does not validate or set it.
