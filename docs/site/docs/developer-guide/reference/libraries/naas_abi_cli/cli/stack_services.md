# `stack_services`

## What it is
Static service metadata and readiness evaluation utilities for local “stack” services (typically Docker Compose services). Readiness is determined using:

- Docker Compose container state (`running`, `exited`, etc.)
- Docker health status (`healthy` / `unhealthy`)
- HTTP checks against localhost endpoints
- TCP connectivity checks against localhost host/port targets

## Public API

### Constants
- `ABI_REQUIRED_URL: str`
  - Required HTTP readiness endpoint for the `abi` service: `http://127.0.0.1:9879`.

- `SERVICE_CATALOG: dict[str, ServiceDefinition]`
  - Catalog of known services with display metadata plus readiness probes (`urls`, `tcp_targets`) and one-shot semantics.

### Data classes
- `ServiceDefinition`
  - Service metadata and readiness configuration.
  - Fields:
    - `key: str`
    - `display_name: str`
    - `category: str`
    - `description: str`
    - `urls: tuple[str, ...] = ()` — HTTP endpoints to probe
    - `tcp_targets: tuple[tuple[str, int], ...] = ()` — TCP `(host, port)` to probe
    - `is_one_shot: bool = False` — one-shot/init container behavior

- `ReadinessResult`
  - Readiness decision output.
  - Fields:
    - `ready: bool`
    - `source: str` — where the decision came from (`compose`, `docker-health`, `http`, `tcp`)
    - `detail: str` — operator-readable status message

### Functions
- `evaluate_service_readiness(service_name: str, state: ComposeServiceState | None, http_timeout: float = 1.5, tcp_timeout: float = 1.2) -> ReadinessResult`
  - Evaluates readiness using:
    - `state is None` → not ready (`"Container not created"`)
    - `state.health == "unhealthy"` → not ready
    - one-shot services (`ServiceDefinition.is_one_shot`) → ready only when `state.state == "exited"` and `state.exit_code == 0`
    - special case `service_name == "abi"`:
      - must be `running`
      - must pass HTTP check to `ABI_REQUIRED_URL`
    - otherwise:
      - `state.health == "healthy"` → ready
      - must be `running` (else not ready)
      - if service exists in `SERVICE_CATALOG`:
        - tries HTTP URLs in order; first success marks ready
        - then tries TCP targets in order; first success marks ready
      - fallback: running container is considered ready

## Configuration/Dependencies
- Depends on `.stack_runtime.ComposeServiceState` (must provide at least `state`, `health`, `exit_code` attributes as used here).
- Standard library:
  - `urllib.request`, `urllib.error` for HTTP probes
  - `socket` for TCP probes
- All probe endpoints are hard-coded to `127.0.0.1` (static catalog).

## Usage

```python
from naas_abi_cli.cli.stack_services import evaluate_service_readiness
from naas_abi_cli.cli.stack_runtime import ComposeServiceState

state = ComposeServiceState(state="running", health=None, exit_code=None)
result = evaluate_service_readiness("postgres", state)

print(result.ready, result.source, result.detail)
```

## Caveats
- `abi` readiness is stricter than other services:
  - it must be `running` and pass `GET http://127.0.0.1:9879`, regardless of any other URLs in `SERVICE_CATALOG`.
- If a container is `running` and no HTTP/TCP checks succeed (or none are configured), readiness defaults to **ready** with:
  - `source="compose"`, `detail="Container is running"`.
