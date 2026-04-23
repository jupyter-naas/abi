# stack_runtime

## What it is
Utilities for interacting with a Docker Compose stack at runtime:
- Run `docker compose ...` commands with Click-friendly error reporting
- List services, inspect service/container states, and fetch/follow logs

## Public API
- `@dataclass ComposeServiceState`
  - Immutable container/service status snapshot with fields:
    - `service: str`
    - `container_name: str | None`
    - `state: str` (lowercased; defaults to `"unknown"`)
    - `health: str | None`
    - `exit_code: int | None`
    - `status: str | None`

- `run_compose(args: list[str], capture_output: bool = False) -> subprocess.CompletedProcess`
  - Executes `docker compose <args>` with `check=True`.
  - Raises `click.ClickException` when Docker is missing or the command fails.

- `compose_service_list() -> list[str]`
  - Returns service names from `docker compose config --services`.

- `compose_service_states() -> dict[str, ComposeServiceState]`
  - Returns a mapping `{service_name: ComposeServiceState}` based on `docker compose ps -a --format json`.
  - Handles both JSON arrays and newline-delimited JSON objects.

- `compose_service_logs(service: str, tail: int = 120) -> str`
  - Returns recent logs (`--tail`) for a service via `docker compose logs --no-color`.

- `compose_logs_follow(service: str | None) -> None`
  - Streams logs (`docker compose logs -f`) for all services or a specific service.

## Configuration/Dependencies
- Requires Docker CLI with the `docker compose` subcommand available in `PATH`.
- Uses `click.ClickException` for user-facing errors.

## Usage
```python
from naas_abi_cli.cli.stack_runtime import (
    compose_service_list,
    compose_service_states,
    compose_service_logs,
)

print("Services:", compose_service_list())

states = compose_service_states()
for name, st in states.items():
    print(name, st.state, st.exit_code)

print(compose_service_logs("web", tail=20))
```

## Caveats
- Commands run in the current working directory; Compose project/stack selection is determined by the local Compose files and environment.
- `compose_logs_follow(...)` does not capture output; it streams directly to the terminal.
- Parsing of `docker compose ps --format json` is best-effort; non-JSON lines are ignored.
