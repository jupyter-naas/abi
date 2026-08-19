# OpenRouterAPIIntegration_list_providers

## What it is
- A small CLI script that lists all OpenRouter providers via an integration object.
- Optionally saves the providers JSON to object storage (enabled by default).

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Parses CLI arguments, calls the integration to list providers, prints JSON to stdout, returns exit code `0`.
- `_parser() -> argparse.ArgumentParser`
  - Builds the CLI argument parser (internal helper).

## Configuration/Dependencies
- Imports `get_integration` from `naas_abi_marketplace.ai.openrouter.scripts._common`.
  - This function is responsible for returning an integration instance with a `list_providers(save_json: bool)` method.
  - Any required configuration (e.g., credentials, endpoints, object storage setup) is handled outside this file by the integration/common code.
- Standard library dependencies: `argparse`, `json`, `sys`.

## Usage
### As a script (CLI)
```bash
python OpenRouterAPIIntegration_list_providers.py
```

Skip saving providers JSON to object storage:
```bash
python OpenRouterAPIIntegration_list_providers.py --no-save
```

### As a module function
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_list_providers import main

raise SystemExit(main(["--no-save"]))
```

## Caveats
- The script always prints the result as pretty-printed JSON to stdout.
- Saving behavior is controlled by `--no-save`; by default it attempts to save (`save_json=True`), which may fail if the underlying integration/object storage is not configured.
