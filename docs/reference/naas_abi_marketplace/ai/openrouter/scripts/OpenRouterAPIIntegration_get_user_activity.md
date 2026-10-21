# OpenRouterAPIIntegration_get_user_activity

## What it is
- A small CLI script that fetches OpenRouter user activity grouped by endpoint and prints the result as pretty-formatted JSON.

## Public API
- `main(argv: list[str] | None = None) -> int`
  - Parses CLI args, calls the OpenRouter integration to fetch user activity, prints JSON to stdout, returns `0`.
- `_parser() -> argparse.ArgumentParser`
  - Internal helper that defines CLI arguments.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.ai.openrouter.scripts._common.get_integration`
    - Returns an integration object exposing `get_user_activity(date=...)`.
  - Standard library: `argparse`, `json`, `sys`
- CLI options:
  - `--date` (optional): UTC date string `YYYY-MM-DD` (intended to be within the last 30 days)

## Usage

### Run as a script
```bash
python OpenRouterAPIIntegration_get_user_activity.py
```

### Filter by date
```bash
python OpenRouterAPIIntegration_get_user_activity.py --date 2025-01-15
```

### Call from Python
```python
from naas_abi_marketplace.ai.openrouter.scripts.OpenRouterAPIIntegration_get_user_activity import main

raise SystemExit(main(["--date", "2025-01-15"]))
```

## Caveats
- No validation is performed on `--date`; it is passed directly to `integration.get_user_activity(date=...)`.
- Output is printed to stdout as JSON; errors from integration setup/call are not handled in this script.
