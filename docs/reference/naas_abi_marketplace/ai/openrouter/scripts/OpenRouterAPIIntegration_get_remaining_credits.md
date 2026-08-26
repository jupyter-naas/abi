# OpenRouterAPIIntegration_get_remaining_credits

## What it is
- A small CLI-style script that fetches remaining OpenRouter credits via an integration object and prints the result as pretty-printed JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Retrieves an OpenRouter integration via `get_integration()`
  - Calls `integration.get_remaining_credits()`
  - Prints the returned value as JSON (`indent=2`)
  - Returns exit code `0`

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
  - Must return an object exposing `get_remaining_credits()`
- Standard library:
  - `json` for serialization
  - `sys` for CLI exit handling

## Usage
### Run as a module/script
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_get_remaining_credits import main

raise SystemExit(main())
```

### Typical CLI entrypoint behavior
When executed directly, it runs:
```python
if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## Caveats
- `argv` is accepted by `main()` but is not used.
- The script prints whatever `integration.get_remaining_credits()` returns; it assumes the result is JSON-serializable.
