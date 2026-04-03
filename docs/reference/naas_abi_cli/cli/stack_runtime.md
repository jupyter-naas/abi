# stack_runtime

## What it is
Utilities for interacting with a Docker Compose stack at runtime:
- Run `docker compose` commands with consistent error handling.
- List configured services, inspect service/container states, and fetch/follow logs.

## Public API
- `@dataclass(frozen=True) ComposeServiceState`
  - Immutable representation of a Compose service’s runtime state.
  - Fields:
    - `service: str` - service name.
    - `container_name: str | None` - container name (if available).
    - `state: str` - normalized container state (lowercased; defaults to `"unknown"`).
    - `health: str | None` - health status (if provided by Compose output).
    - `exit_code: int | None` - parsed exit code when available.
    - `status: str | None` - status string (if provided).

- `run_compose(args: list[str], capture_output: bool = False) -> subprocess.CompletedProcess`
  - Runs `docker compose <args>`.
  - Raises `click.ClickException` if Docker is missing or the command fails.

- `compose_service_list() -> list[str]`
  - Returns service names from `docker compose config --services`.

- `compose_service_states() -> dict[str, ComposeServiceState]`
  - Returns a mapping `{service_name: ComposeServiceState}` from `docker compose ps -a --format json`.

- `compose_service_logs(service: str, tail: int = 120) -> str`
  - Returns recent logs for a service (`docker compose logs --no-color --tail=<tail> <service>`).

- `compose_logs_follow(service: str | None) -> None`
  - Streams logs (`docker compose logs -f [service]`) until interrupted.

## Configuration/Dependencies
- Requires:
  - Docker CLI with the `docker compose` subcommand available in `PATH`.
  - Python packages: `click` (for `ClickException`).
- Assumes commands are executed in a directory where a Compose project/config is resolvable (e.g., contains `compose.yaml`/`docker-compose.yml` or equivalent environment).

## Usage
```python
from naas_abi_cli.cli.stack_runtime import (
    compose_service_list,
    compose_service_states,
    compose_service_logs,
)

services = compose_service_list()
print("Services:", services)

states = compose_service_states()
for name, st in states.items():
    print(name, st.state, st.health, st.exit_code)

if services:
    print(compose_service_logs(services[0], tail=20))
```

## Caveats
- Failures in Docker invocation or non-zero exit codes are surfaced as `click.ClickException`.
- `compose_service_states()` depends on the JSON format emitted by `docker compose ps --format json`; parsing tolerates either:
  - a JSON list/dict, or
  - newline-delimited JSON objects.
