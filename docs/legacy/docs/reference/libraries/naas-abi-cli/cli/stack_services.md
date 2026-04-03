# stack_services

## What it is
Service catalog and readiness evaluation utilities for a local “stack” of services. It maps known service names to HTTP/TCP checks and uses container state (from `ComposeServiceState`) to decide if a service is ready.

## Public API
- `ABI_REQUIRED_URL: str`
  - Constant URL required for ABI readiness (`http://127.0.0.1:9879`).

- `ServiceDefinition` (dataclass, frozen)
  - Defines a service’s metadata and readiness probes.
  - Fields:
    - `key: str`
    - `display_name: str`
    - `category: str`
    - `description: str`
    - `urls: tuple[str, ...] = ()` (HTTP endpoints to probe)
    - `tcp_targets: tuple[tuple[str, int], ...] = ()` (host/port pairs to probe)
    - `is_one_shot: bool = False` (init containers that “complete” by exiting 0)

- `ReadinessResult` (dataclass, frozen)
  - Readiness outcome container.
  - Fields:
    - `ready: bool`
    - `source: str` (e.g., `"compose"`, `"docker-health"`, `"http"`, `"tcp"`)
    - `detail: str` (human-readable reason)

- `SERVICE_CATALOG: dict[str, ServiceDefinition]`
  - Known services and their readiness probes (e.g., `abi`, `postgres`, `minio`, `rabbitmq`, etc.).

- `evaluate_service_readiness(service_name: str, state: ComposeServiceState | None, http_timeout: float = 1.5, tcp_timeout: float = 1.2) -> ReadinessResult`
  - Computes readiness for a service based on:
    - Compose state (`state.state`, `state.health`, `state.exit_code`)
    - Service-specific rules:
      - `abi` requires the container to be running *and* `ABI_REQUIRED_URL` to pass an HTTP check.
      - `is_one_shot` services are ready only when `state.state == "exited"` and `state.exit_code == 0`.
      - Other services may be considered ready if:
        - Docker health is `"healthy"`, or
        - Any configured HTTP URL responds with status < 500, or
        - Any configured TCP target accepts a connection, or
        - Fallback: container is running.

## Configuration/Dependencies
- Depends on `ComposeServiceState` from `.stack_runtime`.
- Uses standard library networking:
  - `urllib.request` / `urllib.error` for HTTP probing.
  - `socket.create_connection` for TCP probing.
- Timeouts:
  - HTTP probes default to `1.5s` (`http_timeout`).
  - TCP probes default to `1.2s` (`tcp_timeout`).

## Usage
```python
from naas_abi_cli.cli.stack_services import evaluate_service_readiness

# ComposeServiceState comes from naas_abi_cli.cli.stack_runtime
# This example assumes you already have a `state` for the service.
result = evaluate_service_readiness("postgres", state)

print(result.ready, result.source, result.detail)
```

## Caveats
- If `state` is `None`, readiness is always `False` (`"Container not created"`).
- If `state.health == "unhealthy"`, readiness is always `False` regardless of probes.
- Services not in `SERVICE_CATALOG` fall back to `"Container is running"` when `state.state == "running"` (no HTTP/TCP checks applied).
- For HTTP checks, responses with status `< 500` are treated as ready (including 4xx).
