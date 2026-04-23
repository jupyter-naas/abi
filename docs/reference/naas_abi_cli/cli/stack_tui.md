# StackTextualApp / StackTUI

## What it is
A terminal UI (TUI) built with `textual` to monitor and manage a Docker Compose “stack”:
- Lists services and their compose state.
- Probes per-service readiness (HTTP/TCP) using a service catalog.
- Shows selected service details and streams or fetches its logs.
- Provides key bindings to run common `docker compose` actions (up/down/stop/restart) and open a service URL.

## Public API
### Classes
- `class StackTextualApp(App[None])`
  - Textual application implementing the TUI.
  - Key actions (invoked via bindings):
    - `action_cursor_down()` / `action_cursor_up()`: move selection.
    - `action_toggle_pause()`: pause/resume UI refresh rendering.
    - `action_restart_service()`: `docker compose restart <service>`.
    - `action_up_service()`: `docker compose up -d <service>`.
    - `action_up_stack()`: `docker compose up -d`.
    - `action_stop_service()`: `docker compose stop <service>`.
    - `action_down_service()`: `docker compose rm -s -f <service>`.
    - `action_down_stack()`: `docker compose down -v`.
    - `action_open_url()`: open first URL from `SERVICE_CATALOG[service].urls` in a browser.
  - Lifecycle hooks:
    - `compose()`: builds layout (services table, selected panel, logs panel, header/footer).
    - `on_mount()`: initializes table, starts background threads, schedules UI refresh.
    - `on_unmount()`: stops threads and terminates any log-follow process.

- `class StackTUI`
  - Thin wrapper around `StackTextualApp`.
  - Methods:
    - `__init__(refresh_interval: float = 1.5)`: store refresh interval.
    - `run()`: instantiate and run `StackTextualApp`.

### Key bindings
- Navigation: `j`/`down`, `k`/`up`
- Actions:
  - `u`: up service
  - `U`: up stack
  - `r`: restart selected service
  - `s` or `S`: stop selected service
  - `d`: down (rm) selected service
  - `D`: down stack with volumes (`down -v`)
  - `o`: open service URL (first URL in catalog)
  - `p`: pause UI rendering
  - `q`: quit

## Configuration/Dependencies
- Runtime dependencies:
  - `textual` (UI framework)
  - Docker Compose available via `docker compose` on PATH
- Internal dependencies (same package):
  - `.stack_runtime`:
    - `compose_service_list()`, `compose_service_states()`, `run_compose()`, `ComposeServiceState`
  - `.stack_services`:
    - `SERVICE_CATALOG`, `evaluate_service_readiness()`, `ReadinessResult`
- Notable internal intervals/timeouts (hardcoded in `StackTextualApp`):
  - Service list refresh: `15.0s`
  - State refresh loop: `refresh_interval` (min `0.5s`)
  - Readiness probe refresh: `1.2s` (selected service: `0.25s`)
  - Probe timeouts: HTTP `0.35s`, TCP `0.30s`
  - Logs polling: `0.2s`
- Log retrieval:
  - When running: spawns `docker compose logs -f --no-color --tail=80 <service>` and streams output.
  - When not running: calls `run_compose(["logs", "--no-color", "--tail=120", <service>], capture_output=True)`.

## Usage
Minimal runnable example:

```python
from naas_abi_cli.cli.stack_tui import StackTUI

if __name__ == "__main__":
    StackTUI(refresh_interval=1.5).run()
```

## Caveats
- Requires a working Docker environment; errors are surfaced in the UI as “Docker Error”.
- Uses background threads plus a spawned `docker compose logs -f` subprocess; the log follower is terminated on unmount or when switching to a non-running service.
- “Pause” stops UI rendering updates but background workers continue collecting state/logs/readiness.
