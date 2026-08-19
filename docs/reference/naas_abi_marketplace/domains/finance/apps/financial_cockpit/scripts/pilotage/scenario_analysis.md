# scenario_analysis

## What it is
A standalone Python script that generates a **fake** “Scenario Analysis” demo dataset for the Financial Cockpit. It:
- Reads each entity’s `forecast/forecast.json`
- Computes a full-year **base case** from forecast totals (actuals where present)
- Produces multiple record types (`scenario`, `driver`, `sensitivity`, `assumption`) as **monthly snapshots**
- Writes `scenario_analysis/scenario_analysis.json` per entity and patches the entity `manifest.json` to include the dataset.

## Public API
### Entry point
- `main() -> None`
  - Discovers entities with a forecast dataset and generates scenario analysis output files.

### Data structures (module-level)
- `ScenarioDef` (dataclass)
  - Fields: `key`, `label`, `probability`, `revenue_factor`, `cost_factor`, `description`
- `DriverDef` (dataclass)
  - Fields: `key`, `label`, `unit`, `base`, `low`, `high`, `elasticity`, `hint`

### Internal helpers (not intended as public API)
- `_seed_for(entity_id: str) -> int`: deterministic RNG seed per entity
- `_load(entity_id: str, relative_path: str) -> dict | None`: JSON loader from `web/data/entities/<entity>/...`
- `_base_case_by_year(forecast: dict) -> dict[str, dict[str, float]]`: compute yearly totals (revenue/EBITDA flows; cash as last month stock; margin derived)
- `_periods(forecast: dict) -> list[tuple[str, str, str]]`: unique periods with `(period, scenario, scenario_year)`
- `_outcome(base: dict[str, float], scenario: ScenarioDef) -> dict[str, float]`: apply scenario factors to base revenue/costs; compute cash and margin
- `_build_records(entity_id: str, forecast: dict) -> list[dict]`: generate all output records per period
- `_scenarios_option_list(payload: dict, records: list[dict]) -> list[dict[str, str]]`: reuse upstream `scenarios` options if present; otherwise rebuild
- `_patch_manifest(entity_id: str, data_version: str) -> None`: add dataset path and update `data_version` in `manifest.json`
- `_entities_with_sources() -> list[str]`: find entities having `forecast/forecast.json`

## Configuration/Dependencies
- **Python standard library only**: `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`
- Filesystem layout assumptions:
  - App root is derived from script location: `.../financial_cockpit/`
  - Input: `web/data/entities/<entity_id>/forecast/forecast.json`
  - Output: `web/data/entities/<entity_id>/scenario_analysis/scenario_analysis.json`
  - Manifest patched: `web/data/entities/<entity_id>/manifest.json`
- Key constants:
  - `SCENARIOS`: Upside/Base/Downside/Severe with probability and revenue/cost factors
  - `DRIVERS`: set of business drivers used for tornado, matrix, and assumptions
  - Sensitivity matrix configuration: `MATRIX_ROW="volume"`, `MATRIX_COL="input_costs"`, `MATRIX_STEPS=5`

## Usage
Run from the Financial Cockpit app root (after generating the forecast dataset):
```bash
python scripts/pilotage/scenario_analysis.py
```

Minimal programmatic invocation:
```python
from scripts.pilotage.scenario_analysis import main

main()
```

Outputs (per entity):
- `web/data/entities/<entity_id>/scenario_analysis/scenario_analysis.json`
- Updates `web/data/entities/<entity_id>/manifest.json` to include:
  - dataset page id `scenario-analysis` pointing to `scenario_analysis/scenario_analysis.json`

## Caveats
- Requires a forecast dataset; otherwise exits with:
  - `"No forecast found — run scripts/pilotage/forecast.py first."`
- Data is intentionally **fake/demo** and includes seeded randomness per entity (stable per `entity_id`).
- Records are emitted **per forecast period** and are filtered out when the computed base-year revenue is `<= 0`.
