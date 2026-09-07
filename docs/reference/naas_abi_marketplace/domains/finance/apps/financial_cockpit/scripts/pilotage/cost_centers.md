# cost_centers

## What it is
A standalone Python script that generates a **fake Cost Centers** demo dataset for the Financial Cockpit. It reads each entity’s upstream **cash flow** memo P&L (Revenue and EBITDA) and allocates the implied cost base (Revenue − EBITDA) across predefined cost centers using fixed weights, producing one record per cost center per month.

Outputs JSON under each entity directory and updates the entity `manifest.json` to register the dataset.

## Public API
- `main() -> None`
  - CLI entrypoint. For each entity with an existing cash flow dataset, generates `cost_centers/cost_centers.json` and patches `manifest.json`.

### Internal helpers (module-private)
- `CostCenterDef` (dataclass)
  - Defines a cost center: identifiers, division, cost/revenue allocation weights, and headcount parameters.
- `_entities_with_sources() -> list[str]`
  - Finds entity IDs that have `cash_flow/cash_flow.json`.
- `_load(entity_id: str, relative_path: str) -> dict | None`
  - Loads JSON from an entity’s dataset path.
- `_monthly_pnl(cash_flow: dict) -> list[tuple[str, str, str, float, float]]`
  - Extracts `(period, scenario, scenario_year, revenue, ebitda)` from cash flow `records` where `activity == "memo"` and `category in {"Revenue","EBITDA"}`.
- `_build_records(entity_id: str, cash_flow: dict) -> list[dict]`
  - Builds per-month, per-cost-center records with:
    - `budget`, `actual` allocated from monthly cost base
    - `headcount` via growth curve
    - `revenue_contribution` for revenue-generating centers only
    - `margin_contribution = revenue_contribution - actual`
- `_scenarios(payload: dict, records: list[dict]) -> list[dict[str, str]]`
  - Reuses upstream `scenarios` from the cash flow payload if present; otherwise rebuilds scenario options from the generated records.
- `_patch_manifest(entity_id: str, data_version: str) -> None`
  - Updates `manifest.json` to register the Cost Centers dataset page and set `data_version`.

## Configuration/Dependencies
- **Python**: standard library only (`glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`).
- **Filesystem layout (relative to this script)**:
  - `APP_ROOT = .../financial_cockpit`
  - `ENTITIES_DIR = web/data/entities`
- **Inputs (per entity)**:
  - `web/data/entities/<entity_id>/cash_flow/cash_flow.json`
- **Outputs (per entity)**:
  - `web/data/entities/<entity_id>/cost_centers/cost_centers.json`
  - Patches `web/data/entities/<entity_id>/manifest.json` to include:
    - `datasets.pages["cost-centers"] = ["cost_centers/cost_centers.json"]`
    - `data_version = "<YYYY-MM-DD HH:MM>"`
- **Constants**
  - `SCHEMA_VERSION = "1.0"`
  - Allocation comes from the hardcoded `COST_CENTERS` list (`CostCenterDef` entries).

## Usage
Run from the Financial Cockpit app root (after generating upstream datasets as noted in the script docstring):

```bash
python scripts/pilotage/cost_centers.py
```

Minimal programmatic invocation:

```python
from scripts.pilotage.cost_centers import main

main()
```

## Caveats
- Requires upstream cash flow data to exist; otherwise exits with an error instructing to run the balance sheet and cash flow scripts first.
- Generated values are deterministic per entity (seeded from `md5("cc-<entity_id>")`) but include randomized variance around allocations.
- Cost base per month is `max(0, revenue - ebitda)`; if EBITDA exceeds revenue, costs allocate from zero for that month.
