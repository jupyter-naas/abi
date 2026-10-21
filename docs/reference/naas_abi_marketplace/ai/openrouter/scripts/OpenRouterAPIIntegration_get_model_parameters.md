# OpenRouterAPIIntegration_get_model_parameters

## What it is
- A small CLI script that fetches a model’s supported parameters from OpenRouter via an integration object and prints the result as pretty-printed JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Parses CLI args (`--author`, `--slug`), calls the OpenRouter integration, prints JSON, and returns exit code `0`.
- `_parser() -> argparse.ArgumentParser`
  - Internal helper to build the argument parser.

## Configuration/Dependencies
- Python standard library:
  - `argparse`, `json`, `sys`
- Internal dependency:
  - `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
    - Must return an object that implements:
      - `get_model_parameters(author: str, slug: str)`

## Usage
### Run as a CLI module/script
```bash
python OpenRouterAPIIntegration_get_model_parameters.py --author openai --slug gpt-4.1-mini
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_get_model_parameters import main

# Equivalent to: --author openai --slug gpt-4.1-mini
raise SystemExit(main(["--author", "openai", "--slug", "gpt-4.1-mini"]))
```

## Caveats
- `--author` and `--slug` are required; missing either will cause argparse to exit with an error.
- Output is printed to stdout as JSON; the script does not handle or suppress integration errors/exceptions.
