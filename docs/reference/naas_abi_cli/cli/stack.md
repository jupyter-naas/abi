# stack (CLI)

## What it is
Click-based CLI commands to manage and inspect the local ABI Docker Compose stack: start/stop the stack, stream logs, show status, and run a text UI.

## Public API
### Click commands
- `stack` (group): Manage and inspect the local ABI stack.
  - `stack start`: Bring the Compose stack up (`docker compose up -d`), retry on failure, open the service portal URL on success.
  - `stack stop [--volumes/-v]`: Bring the stack down (`docker compose down`), optionally removing volumes (`-v`).
  - `stack logs [service]`: Follow logs for all services or a specific service.
  - `stack status`: Print a Rich table showing service state/health/readiness.
  - `stack tui [--interval FLOAT]`: Run a terminal UI, refreshing at the given interval (default `1.5s`).

Also exposed as standalone click commands (likely for alternate CLI wiring):
- `start`: Same as `stack start`.
- `stop [--volumes/-v]`: Same as `stack stop`.
- `logs [service]`: Same as `stack logs`.

### Internal helpers (module-private)
- `_start_stack()`: Implements stack startup with retries; checks for error containers; opens `SERVICE_PORTAL_URL` on success.
- `_stop_stack(volumes: bool)`: Implements shutdown; adds `-v` when requested.
- `_show_status()`: Builds and prints the status table.
- `_get_error_services()`: Returns services considered “in error” based on Compose state.
- `_show_error_logs(error_services: list[str])`: Prints recent logs (tail 160) for failing services.
- `_is_container_in_error(service_name, state)`: Determines whether a service is in an error state (health/state/exit code; special handling for one-shot services).

## Configuration/Dependencies
- **External tools**: Docker Compose available via the underlying `run_compose(...)` integration.
- **Python deps**:
  - `click` for CLI
  - `rich` (`Console`, `Table`) for status output
  - `webbrowser` to open the portal URL
- **Internal modules**:
  - `.stack_runtime`: `run_compose`, `compose_service_list`, `compose_service_states`, `compose_service_logs`, `compose_logs_follow`, `ComposeServiceState`
  - `.stack_services`: `SERVICE_CATALOG`, `evaluate_service_readiness`
  - `.stack_tui`: `StackTUI`
- **Constant**:
  - `SERVICE_PORTAL_URL = "http://127.0.0.1:8080/"` (opened on successful `start`)

## Usage
### As a Click command group
```python
import click
from naas_abi_cli.cli.stack import stack

@click.group()
def cli():
    pass

cli.add_command(stack)

if __name__ == "__main__":
    cli()
```

Then:
- `python your_cli.py stack start`
- `python your_cli.py stack status`
- `python your_cli.py stack logs` (or `... stack logs <service>`)
- `python your_cli.py stack tui --interval 1.0`
- `python your_cli.py stack stop -v`

## Caveats
- `start` retries `docker compose up -d` up to 2 times after the initial attempt (3 total attempts). If services remain in error on the last attempt, it prints recent logs and raises a `click.ClickException`.
- A service is treated as “in error” if:
  - health is `unhealthy`, or
  - state is `dead`/`removing`, or
  - state is `exited` with non-zero exit code (except “one-shot” services in `SERVICE_CATALOG` that exit with code `0`).
- `stack status` includes services from both the Compose definition and `SERVICE_CATALOG` (union), so it may show catalog entries that are not created.
