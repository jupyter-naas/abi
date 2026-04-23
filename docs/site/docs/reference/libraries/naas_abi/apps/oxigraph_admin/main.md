# OxigraphAdmin

## What it is
A terminal-based administrative interface for managing and monitoring an Oxigraph triple store running at `http://localhost:7878`. It provides a dashboard (health + basic counts), a menu of SPARQL query templates, and basic Docker-based service controls.

## Public API
- `class OxigraphAdmin(triple_store_service: ITripleStoreService)`
  - Purpose: interactive TUI for Oxigraph operations using a provided triple store service.
  - Methods:
    - `check_oxigraph_health() -> bool`: Checks whether the Oxigraph `/query` endpoint responds with HTTP 200.
    - `get_triple_count() -> int`: Returns total triples via `triple_store_service.query(...)` (returns `0` on error).
    - `get_class_count() -> int`: Returns count of distinct `owl:Class` (returns `0` on error).
    - `get_property_count() -> int`: Returns count of distinct `owl:ObjectProperty` and `owl:DatatypeProperty` (returns `0` on error).
    - `display_dashboard() -> None`: Clears screen, prints welcome/health, and shows counts in a table.
    - `query_templates_menu() -> None`: Displays built-in SPARQL templates (including a custom search placeholder) and optionally executes them.
    - `service_control_menu() -> None`: Docker Compose actions: restart Oxigraph, `docker compose ps`, and show logs.
    - `data_management_menu() -> None`: Stub menu; “Show recent changes” currently prints “Feature coming soon...”.
    - `run() -> None`: Main loop; routes to dashboards/menus and can spawn other tools or print URLs.
- `main() -> None`
  - Purpose: Loads `triple_store_service` from `naas_abi.ABIModule` and starts the interactive admin UI.

## Configuration/Dependencies
- Oxigraph endpoint:
  - Hardcoded as `http://localhost:7878` in `OxigraphAdmin.__init__`.
- Required services/libraries:
  - `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` (must provide `.query(str)`).
  - `requests` for health checks.
  - `rich` (`Console`, `Table`) for formatted output.
  - `naas_abi.apps.oxigraph_admin.terminal_style` for UI helpers:
    - `clear_screen`, `get_user_input`, `print_*` functions.
- External commands (must be available on PATH for related features):
  - `docker compose ...` for service control.
  - `uv run python -m src.core.abi.apps.sparql_terminal.main` for “Open SPARQL terminal”.

## Usage
Run as a module/script (requires the broader `naas_abi` environment so `ABIModule` can provide the triple store service):

```python
from naas_abi.apps.oxigraph_admin.main import OxigraphAdmin
from naas_abi import ABIModule

triple_store_service = ABIModule.get_instance().engine.services.triple_store
OxigraphAdmin(triple_store_service).run()
```

Or execute the file directly:

```bash
python libs/naas-abi/naas_abi/apps/oxigraph_admin/main.py
```

## Caveats
- The Oxigraph URL is not configurable via arguments/environment in this file (fixed to `http://localhost:7878`).
- Several options exit the UI loop after launching/printing target tools/URLs (SPARQL terminal, YasGUI URL, unified explorer URL).
- Query execution output prints the `results` object directly; formatting depends on the underlying `ITripleStoreService.query()` return type.
- Data management features are largely placeholders (only one option implemented, and it’s “coming soon”).
- Docker-based actions assume a Docker Compose setup with a service named `oxigraph` and (for restart) a `dev` profile.
