# `naas_abi_cli.cli.stack`

## What it is
Click-based CLI commands for managing and inspecting a local “ABI stack” running under Docker Compose:
- Start/stop the stack
- Follow logs (optionally per-service)
- Show a Rich table status view
- Launch a terminal UI (TUI)

## Public API
### Click command groups/commands
- `stack()` (Click group: `stack`)
  - Top-level group for stack-related subcommands.
- `stack_start()`
  - Starts the stack (runs `docker compose up -d` via `run_compose`), retries on failure, checks for container errors, opens the service portal URL on success.
- `stack_stop(volumes: bool)`
  - Stops the stack (`docker compose down`), with optional volume removal (`-v`).
- `stack_logs(service: str | None)`
  - Follows Docker Compose logs. If `service` is provided, follows that service’s logs.
- `stack_status()`
  - Prints a Rich table with service state, health, readiness, and readiness probe/source.
- `stack_tui(interval: float)`
  - Runs an interactive TUI (`StackTUI`) refreshing every `interval` seconds.

### Top-level commands (non-grouped)
These duplicate the grouped functionality under different command names:
- `start()` → same behavior as `stack_start()`
- `stop(volumes: bool)` → same behavior as `stack_stop()`
- `logs(service: str | None)` → same behavior as `stack_logs()`

## Configuration/Dependencies
- **Browser opening**
  - Opens `SERVICE_PORTAL_URL = "http://127.0.0.1:8080/"` via `webbrowser.open()` after a successful start.
- **Runtime/stack integrations**
  - Uses `run_compose`, `compose_service_list`, `compose_service_states`, `compose_service_logs`, `compose_logs_follow` from `naas_abi_cli.cli.stack_runtime`.
  - Uses `SERVICE_CATALOG`, `evaluate_service_readiness` from `naas_abi_cli.cli.stack_services`.
  - Uses `StackTUI` from `naas_abi_cli.cli.stack_tui`.
- **Third-party libraries**
  - `click` for CLI
  - `rich` for the status table output

## Usage
Minimal Python usage (invoking command functions directly):

```python
from naas_abi_cli.cli.stack import stack_status, stack_start, stack_stop

stack_start()
stack_status()
stack_stop(volumes=False)
```

Typical CLI usage (as provided by Click entrypoints in your app) will expose commands similar to:
- `stack start`
- `stack stop [-v|--volumes]`
- `stack logs [service]`
- `stack status`
- `stack tui [--interval SECONDS]`

## Caveats
- Startup retries:
  - `docker compose up -d` is retried up to **2** times on failure.
  - After a successful `up`, services are checked for error conditions; if any are in error, `up -d` is retried up to the same limit.
- Error detection rules:
  - A service is considered “in error” if:
    - health is `"unhealthy"`, or
    - state is `"dead"` or `"removing"`, or
    - state is `"exited"` with a non-zero exit code,
    - except: “one-shot” services (from `SERVICE_CATALOG`) exiting with code `0` are not treated as errors.
- On final failure due to service errors, recent logs are printed (tail=160 lines) for each erroring service.
