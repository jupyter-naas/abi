# `stack_services`

## What it is
Utilities and static metadata for evaluating “readiness” of local stack services (typically Docker Compose services) via:
- Docker Compose container state/health
- HTTP health endpoints on localhost
- TCP connectivity checks on localhost ports

## Public API

### Constants
- `ABI_REQUIRED_URL: str`
  - Hard-coded HTTP endpoint used as the required readiness check for the `abi` service (`http://127.0.0.1:9879`).

- `SERVICE_CATALOG: dict[str, ServiceDefinition]`
  - Static catalog of known services and their readiness targets (URLs and/or TCP ports), plus display metadata.

### Data classes
- `ServiceDefinition`
  - Service metadata and readiness configuration.
  - Fields:
    - `key: str`
    - `display_name: str`
    - `category: str`
    - `description: str`
    - `urls: tuple[str, ...] = ()` (HTTP endpoints to probe)
    - `tcp_targets: tuple[tuple[str, int], ...] = ()` (TCP host/port to probe)
    - `is_one_shot: bool = False` (init/one-shot container semantics)

- `ReadinessResult`
  - Result of a readiness evaluation.
  - Fields:
    - `ready: bool`
    - `source: str` (e.g., `compose`, `docker-health`, `http`, `tcp`)
    - `detail: str` (human-readable detail/status)

### Function
- `evaluate_service_readiness(service_name: str, state: ComposeServiceState | None, http_timeout: float = 1.5, tcp_timeout: float = 1.2) -> ReadinessResult`
  - Determines whether a service should be considered “ready” based on:
    - missing container (`state is None`) → not ready
    - Docker health `unhealthy` → not ready
    - one-shot services (`ServiceDefinition.is_one_shot`) → ready only when `state.state == "exited"` and `exit_code == 0`
    - special-case `abi`:
      - must be `running`
      - must pass HTTP check to `ABI_REQUIRED_URL`
    - otherwise:
      - Docker health `healthy` → ready
      - must be `running` (else not ready)
      - if in `SERVICE_CATALOG`, attempts:
        - HTTP checks in order; first success marks ready
        - then TCP checks in order; first success marks ready
      - if no checks succeed (or none configured), running container is considered ready

## Configuration/Dependencies
- Depends on `ComposeServiceState` from `.stack_runtime` (must provide at least `state`, `health`, `exit_code` attributes used here).
- Uses standard library:
  - `urllib.request` / `urllib.error` for HTTP probing
  - `socket` for TCP probing
- Service endpoints/ports are hard-coded to `127.0.0.1` with fixed ports in `SERVICE_CATALOG`.

## Usage

```python
from naas_abi_cli.cli.stack_services import evaluate_service_readiness

# ComposeServiceState comes from naas_abi_cli.cli.stack_runtime.
# This call returns a ReadinessResult describing readiness status.
result = evaluate_service_readiness(service_name="postgres", state=None)

print(result.ready)   # False
print(result.source)  # "compose"
print(result.detail)  # "Container not created"
```

## Caveats
- `abi` readiness is stricter than other services:
  - it must be `running` *and* respond successfully on `http://127.0.0.1:9879`, regardless of other URLs in the catalog.
- If a container is `running` but all configured HTTP/TCP checks fail (or no checks exist), the function returns **ready** with source `compose` and detail `Container is running`.
