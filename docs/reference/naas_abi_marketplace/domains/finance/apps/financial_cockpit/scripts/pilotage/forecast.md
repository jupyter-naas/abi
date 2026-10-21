# forecast.py

## What it is
- Standalone Python script (stdlib-only) that generates a **fake Forecast** demo dataset for the Financial Cockpit.
- Reads existing demo datasets for **balance sheet** and **cash flow**, then produces `forecast/forecast.json` per entity under `web/data/entities/<entity_id>/`.
- Mixes **historical actuals** (up to `ACTUALS_THROUGH`) with **future forecasts** and confidence bands, and writes/updates the entity `manifest.json` to reference the forecast dataset.

## Public API
- `main() -> None`
  - Discovers entities with required source files and generates forecast datasets for each.
- `MetricDef` (`@dataclass(frozen=True)`)
  - Internal metric definition used to build records (`key`, `label`, `unit`, `is_stock`).

> Other functions are module-internal helpers: `_seed_for`, `_load`, `_actual_series`, `_extrapolate`, `_build_records`, `_scenarios`, `_patch_manifest`, `_entities_with_sources`.

## Configuration/Dependencies
### File layout expectations
- Script assumes it is run from within the Financial Cockpit app tree; it computes:
  - `APP_ROOT = .../domains/finance/apps/financial_cockpit`
  - `DATA_ROOT = <APP_ROOT>/web/data`
  - `ENTITIES_DIR = <DATA_ROOT>/entities`
- For each entity directory `web/data/entities/<entity_id>/`, the script requires:
  - `balance_sheet/balance_sheet.json`
  - `cash_flow/cash_flow.json`
  - Optional: `manifest.json` (patched if present)

### Key constants affecting output
- `ACTUALS_THROUGH = "2026-07-31"`: last period-end treated as “actual”.
- `TREND_WINDOW = 6`: trailing months used for extrapolation.
- Confidence band widening:
  - `BAND_BASE = 0.035`
  - `BAND_PER_MONTH = 0.022`
- Metrics emitted (`METRICS`):
  - `revenue` (currency)
  - `ebitda` (currency)
  - `cash` (currency, stock)
  - `margin` (percent)

### Inputs used for actuals
- Cash flow: reads `records` where `activity == "memo"` and `category in {"Revenue","EBITDA"}`.
- Balance sheet: reads `records` where `category == "Cash & equivalents"` for cash levels.
- Margin is computed as `ebitda / revenue` (0 if revenue <= 0).

## Usage
Run after generating the upstream demo data (balance sheet and cash flow), from the app root:

```bash
python scripts/pilotage/forecast.py
```

Minimal programmatic invocation:

```python
from scripts.pilotage.forecast import main

main()
```

Output per entity:
- Writes: `web/data/entities/<entity_id>/forecast/forecast.json`
- Patches (if present): `web/data/entities/<entity_id>/manifest.json` to include:
  - `datasets.pages["forecast"] = ["forecast/forecast.json"]`
  - updates `data_version`

## Caveats
- Requires upstream source files to exist; otherwise exits with an error instructing you to run:
  - `scripts/performance/balance_sheet.py`
  - `scripts/performance/cash_flow.py`
- Forecasts are **synthetic**:
  - Past months include both `actual` and a “forecast standing at the time” with randomized error.
  - Future months are extrapolated from trailing history with randomized noise and widening confidence bands.
- The “actual vs forecast” split is purely string-based (`period <= ACTUALS_THROUGH`) and depends on `period` being comparable as `YYYY-MM-DD`.
