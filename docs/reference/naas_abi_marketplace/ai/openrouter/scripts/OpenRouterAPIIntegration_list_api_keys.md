# OpenRouterAPIIntegration_list_api_keys

## What it is
- A small CLI script that lists OpenRouter API keys via an integration object and prints the result as pretty-formatted JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Gets an integration via `get_integration()`
  - Calls `integration.list_api_keys()`
  - Prints the returned value as JSON (`indent=2`)
  - Returns exit code `0`

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
  - Must return an object exposing `list_api_keys()`.
- Standard library:
  - `json` for formatting output
  - `sys` for CLI exit handling

## Usage

### Run as a script
```bash
python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/scripts/OpenRouterAPIIntegration_list_api_keys.py
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_list_api_keys import main

raise SystemExit(main())
```

## Caveats
- `argv` is accepted by `main()` but not used.
- Any authentication/configuration required by `get_integration()` is handled outside this script (by `_common.get_integration()`).
