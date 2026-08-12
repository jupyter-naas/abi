# OpenRouterAPIIntegration_list_models

## What it is
- A small CLI script that lists all OpenRouter models via the project’s OpenRouter integration.
- Optionally persists the models JSON to object storage (enabled by default).

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Parses CLI arguments, calls the OpenRouter integration to list models, prints the result as pretty JSON, and returns exit code `0`.
- `_parser() -> argparse.ArgumentParser`
  - Internal helper to build the CLI argument parser (not intended as a public API).

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
  - Provides an integration instance with a `list_models(save_json: bool)` method.
- Standard library: `argparse`, `json`, `sys`.
- CLI option:
  - `--no-save`: disables persisting the models JSON to object storage.

## Usage
### As a script (module execution)
```bash
python -m naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_list_models
```

### Disable saving to object storage
```bash
python -m naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_list_models --no-save
```

### Programmatic call
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_list_models import main

raise SystemExit(main(["--no-save"]))
```

## Caveats
- Output is printed to stdout as JSON; the structure depends on the integration’s `list_models()` implementation.
- Saving behavior is controlled solely by `save_json=not --no-save`; persistence details are handled inside the integration.
