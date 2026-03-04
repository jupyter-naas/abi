# OxigraphAdmin

## What it is
Terminal-based administrative interface for an Oxigraph triple store. It provides:
- A dashboard with health and basic knowledge-graph statistics
- A menu of SPARQL query templates to explore the graph
- Basic Docker-based service controls (restart/status/logs)
- Entry points to related tools (SPARQL terminal, YasGUI, Oxigraph explorer)

## Public API
- `class OxigraphAdmin(triple_store_service: ITripleStoreService)`
  - Purpose: Interactive TUI for monitoring and managing an Oxigraph instance.
  - Key attributes:
    - `oxigraph_url`: Hardcoded to `http://localhost:7878`
    - `triple_store_service`: SPARQL query executor (must implement `ITripleStoreService`)
- `OxigraphAdmin.check_oxigraph_health() -> bool`
  - Purpose: HTTP health check by issuing a simple `/query` request to the Oxigraph endpoint.
- `OxigraphAdmin.get_triple_count() -> int`
  - Purpose: Returns total triple count via SPARQL `COUNT(*)`.
- `OxigraphAdmin.get_class_count() -> int`
  - Purpose: Returns count of distinct `owl:Class` resources.
- `OxigraphAdmin.get_property_count() -> int`
  - Purpose: Returns count of distinct `owl:ObjectProperty` + `owl:DatatypeProperty`.
- `OxigraphAdmin.display_dashboard() -> None`
  - Purpose: Clears screen, prints welcome/health, and renders statistics table.
  - Note: If health check fails, prints an error and returns early.
- `OxigraphAdmin.query_templates_menu() -> None`
  - Purpose: Displays built-in SPARQL templates (1–7), optionally executes selected query.
  - Note: Template #7 replaces `SEARCH_TERM` with user input (lowercased) before querying.
- `OxigraphAdmin.service_control_menu() -> None`
  - Purpose: Docker Compose controls:
    - Restart Oxigraph (`docker compose --profile dev restart oxigraph`)
    - Show `docker compose ps`
    - Tail logs (`docker compose logs --tail=50 oxigraph`)
- `OxigraphAdmin.data_management_menu() -> None`
  - Purpose: Data management menu placeholder; only “Show recent changes” prints “coming soon”.
- `OxigraphAdmin.run() -> None`
  - Purpose: Main interactive loop; displays dashboard and dispatches menu actions.
  - Note: Some options (SPARQL terminal/YasGUI/explorer) print info and then `break` out of the loop.
- `main() -> None`
  - Purpose: CLI entry point; obtains `triple_store_service` from `ABIModule` and launches the UI.

## Configuration/Dependencies
- Network/Service:
  - Oxigraph endpoint assumed at `http://localhost:7878` (hardcoded).
- Python dependencies:
  - `requests` (health check)
  - `rich` (`Console`, `Table`) for formatted output
- Internal dependencies:
  - `naas_abi.apps.oxigraph_admin.terminal_style` (screen clearing, input prompts, styled messages)
  - `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` (SPARQL query interface)
  - `naas_abi.ABIModule` (used by `main()` to locate the triple store service)
- System dependencies (for service control features):
  - `docker` and `docker compose` available on PATH
  - `uv` available on PATH (used to open the SPARQL terminal via `uv run ...`)

## Usage
Run as a module/script (entry point calls `main()`):
```python
from naas_abi.apps.oxigraph_admin.main import main

main()
```

Or instantiate directly if you already have a triple store service:
```python
from naas_abi.apps.oxigraph_admin.main import OxigraphAdmin

admin = OxigraphAdmin(triple_store_service)
admin.run()
```

## Caveats
- Oxigraph URL is not configurable via arguments/environment in this file; it is fixed to `http://localhost:7878`.
- Service control actions assume a Docker Compose project where a service named `oxigraph` exists and (for restart) a `dev` profile is defined.
- Several menu options intentionally exit the main loop (`break`) after launching/printing external tool instructions.
- Query execution prints the `results` object directly; formatting depends on the `ITripleStoreService.query()` return type.
