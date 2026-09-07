# OpenRouterAPIIntegration_create_response

## What it is
- A small CLI script that creates an OpenRouter **beta `/responses`** completion via the marketplace OpenRouter integration.
- Parses command-line arguments, calls `integration.create_response(...)`, and prints the JSON result.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Entry point for running the CLI programmatically.
  - Returns `0` on successful execution.
- `_parser() -> argparse.ArgumentParser`
  - Internal helper to define CLI arguments (not intended as a public API).

## Configuration/Dependencies
- Standard library:
  - `argparse`, `json`, `sys`
- Internal dependency:
  - `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
    - Must return an object exposing `create_response(...)`.

## Usage
### Run as a CLI
```bash
python -m naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_create_response \
  --prompt "Write a haiku about documentation."
```

Optional parameters:
- `--model` (default: `openai/gpt-4.1-mini`)
- `--temperature` (default: `0.7`)
- `--top-p` (default: `0.9`)
- `--tools-json` (JSON array string; optional)

Example with tools:
```bash
python -m naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_create_response \
  --prompt "Call the tool." \
  --tools-json '[{"type":"function","function":{"name":"my_tool","description":"demo","parameters":{"type":"object","properties":{}}}}]'
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_create_response import main

main(["--prompt", "Summarize this in one sentence."])
```

## Caveats
- `--tools-json` must be valid JSON; invalid JSON will raise a `json.JSONDecodeError`.
- Output is printed to stdout as pretty-printed JSON; the script does not post-process or validate the returned structure.
