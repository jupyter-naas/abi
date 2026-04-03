# StackTextualApp (stack_tui.py)

## What it is
A Textual-based terminal UI for monitoring and operating a Docker Compose “stack”:
- Lists services, their compose state, and an evaluated readiness status.
- Shows details and recent logs for the currently selected service.
- Provides keybindings to run common `docker compose` actions (up/down/restart/stop) and open a service URL.

## Public API
### Classes
- `class StackTextualApp(App[None])`
  - Textual `App` implementing the interactive UI.
  - Key responsibilities:
    - Background snapshot of compose service states.
    - Per-service readiness probing.
    - Log tailing/streaming for the selected service.
    - UI refresh loop.

- `class StackTUI`
  - Thin wrapper to run the app.
  - `__init__(refresh_interval: float = 1.5)`: sets refresh interval used by the snapshot worker (min enforced inside `StackTextualApp`).
  - `run() -> None`: launches the Textual app.

### User actions / keybindings (StackTextualApp)
These are exposed via Textual action methods:
- Navigation:
  - `action_cursor_down` (`j`, `down`): move selection down
  - `action_cursor_up` (`k`, `up`): move selection up
- Compose operations:
  - `action_up_service` (`u`): `docker compose up -d <service>`
  - `action_up_stack` (`U`): `docker compose up -d`
  - `action_restart_service` (`r`): `docker compose restart <service>`
  - `action_stop_service` (`s`/`S`): `docker compose stop <service>`
  - `action_down_service` (`d`): `docker compose rm -s -f <service>`
  - `action_down_stack` (`D`): `docker compose down -v`
- Other:
  - `action_open_url` (`o`): opens the first URL for the selected service (from `SERVICE_CATALOG`) in a browser
  - `action_toggle_pause` (`p`): pause UI updates (does not stop background workers)
  - `quit` (`q`): exit

## Configuration/Dependencies
- Depends on `textual` (`App`, `DataTable`, `Header`, `Footer`, `Static`, containers, bindings).
- Depends on local modules:
  - `.stack_runtime`: `compose_service_states()`, `compose_service_list()`, `run_compose()`, `ComposeServiceState`
  - `.stack_services`: `evaluate_service_readiness()`, `SERVICE_CATALOG`, `ReadinessResult`
- External runtime tools:
  - Uses `docker compose` via subprocess for log streaming (`docker compose logs -f ...`) and via `run_compose(...)` for actions and non-follow logs.
- Timing knobs (internal defaults in `StackTextualApp`):
  - Snapshot refresh: `refresh_interval` (constructor; minimum 0.5s)
  - Service list refresh: 15s
  - Readiness probe intervals: 1.2s (default), 0.25s (selected service)
  - Probe timeouts: HTTP 0.35s, TCP 0.30s
  - Logs polling: 0.2s

## Usage
Minimal example to run the TUI:

```python
from naas_abi_cli.cli.stack_tui import StackTUI

if __name__ == "__main__":
    StackTUI(refresh_interval=1.5).run()
```

## Caveats
- Requires Docker and `docker compose` to be available on the system PATH.
- Log streaming uses `docker compose logs -f` and only follows logs when the selected service is in `running` state; otherwise it fetches a static tail.
- “Pause” stops UI repainting but background threads (snapshot, probes, logs worker) continue to run.
