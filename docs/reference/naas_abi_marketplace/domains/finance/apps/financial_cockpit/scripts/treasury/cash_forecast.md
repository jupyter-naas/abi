# `cash_forecast.py`

## What it is

A standalone Python script that generates a **fake cash forecast** demo dataset for the Financial Cockpit “Treasury” page. It reads the monthly cash forecast produced by `forecast/forecast.json`, converts it into **weekly** cash movements (4 weeks per month), and writes `cash_forecast/cash_forecast.json` per entity under `web/data/entities/...`.

Key characteristics:

- Produces **one record per week per scenario**.
- Weekly flows are constructed so the **base case re-anchors to the monthly closing cash** (no drift from the upstream monthly forecast).
- Includes three “cases” (upside/base/downside) with divergence ramping over the forecast horizon.

## Public API

This file is primarily a script. The only intended entry point is:

- `main() -> None`
  - Finds entities with an upstream `forecast/forecast.json`.
  - Generates weekly cash forecast records and writes:
    - `web/data/entities/<entity_id>/cash_forecast/cash_forecast.json`
    - patches `web/data/entities/<entity_id>/manifest.json` to include the dataset.

Internal helpers (not intended as stable API, but present):

- `ScenarioDef` (`@dataclass(frozen=True)`)
  - Scenario metadata used when generating case records (upside/base/downside).

- `_load(entity_id: str, relative_path: str) -> dict | None`
  - Loads JSON from `web/data/entities/<entity_id>/<relative_path>`.

- `_monthly_cash(forecast: dict) -> list[tuple[str, str, str, float, bool]]`
  - Extracts monthly cash records from the upstream forecast payload.

- `_week_ends(period: str) -> list[str]`
  - Computes 4 week-end dates inside the month ending on `period`.

- `_build_records(entity_id: str, forecast: dict) -> list[dict]`
  - Generates weekly cash-flow-like records (inflow/outflow/net/closing_cash) for each month and scenario.

- `_scenarios_option_list(payload: dict, records: list[dict]) -> list[dict[str, str]]`
  - Reuses upstream `scenarios` options when available; otherwise rebuilds options from generated records.

- `_patch_manifest(entity_id: str, data_version: str) -> None`
  - Updates the entity `manifest.json` to register this dataset.

- `_entities_with_sources() -> list[str]`
  - Returns entity IDs that have `forecast/forecast.json`.

## Configuration/Dependencies

- **Python stdlib only**: `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`.
- File layout assumptions (relative to this script):
  - `APP_ROOT = .../financial_cockpit` (two levels up from `scripts/treasury/`)
  - Data root: `web/data/entities/<entity_id>/...`
- Input dependency (must exist per entity):
  - `web/data/entities/<entity_id>/forecast/forecast.json`
- Output:
  - `web/data/entities/<entity_id>/cash_forecast/cash_forecast.json`
  - `web/data/entities/<entity_id>/manifest.json` updated to include `treasury: ["cash_forecast/cash_forecast.json"]`

Notable constants that affect generation:

- `WEEKS_PER_MONTH = 4`
- `SCENARIOS`: upside/base/downside case definitions
- `INFLOW_RHYTHM`, `OUTFLOW_RHYTHM`: weekly distribution of gross inflows/outflows
- `GROSS_TURNOVER`: scales gross flows vs. net change

## Usage

Run from the Financial Cockpit app root **after** generating the upstream forecast dataset:

```bash
python scripts/treasury/cash_forecast.py
```

Minimal Python invocation:

```python
from scripts.treasury.cash_forecast import main

main()
```

## Caveats

- Requires upstream data: if no entities contain `forecast/forecast.json`, the script exits with:
  - `No forecast found — run scripts/pilotage/forecast.py first.`
- The dataset is explicitly **fake/demo data** and uses deterministic randomness seeded per entity.
- Only the **base case** is re-anchored to exactly match the upstream monthly closing cash; other cases diverge according to scenario factors.
