# expenses.py

## What it is
- Standalone script that generates a **fake Expenses demo dataset** for the Financial Cockpit.
- Reads each entity’s `cash_flow/cash_flow.json`, derives the monthly **cost base** (`Revenue − EBITDA`), and allocates a fixed **controllable overhead share** into detailed expense lines.
- Writes `web/data/entities/<entity>/expenses/expenses.json` and updates the entity `manifest.json` to include the Expenses page dataset.

## Public API
- `main() -> None`
  - Entry point: generates expenses datasets for all entities that already have a cash flow dataset.

_Internal helpers (module-private, not intended as public API):_
- `_load(entity_id, relative_path)` loads JSON from an entity dataset path.
- `_cost_base_by_period(cash_flow)` extracts per-period cost base from cash flow memo records.
- `_monthly_totals(periods)` computes controllable overhead totals per period (`OVERHEAD_SHARE` of cost base).
- `_build_records(entity_id, cash_flow)` creates:
  - `kind="expense"` detailed lines (category/department/vendor/requester/status/etc.)
  - `kind="memo"` per-period metrics: `cost_base`, `expenses`, `prior_month_expenses`
- `_scenarios(payload, records)` reuses upstream `scenarios` if present, otherwise rebuilds options from records.
- `_patch_manifest(entity_id, data_version)` registers the dataset path in `manifest.json`.
- `_entities_with_sources()` finds entities with an existing cash flow dataset.

## Configuration/Dependencies
- **Python stdlib only** (no ABI runtime).
- Filesystem layout assumptions:
  - App root inferred from script location.
  - Input per entity:
    - `web/data/entities/<entity_id>/cash_flow/cash_flow.json` (must exist)
  - Outputs per entity:
    - `web/data/entities/<entity_id>/expenses/expenses.json`
    - `web/data/entities/<entity_id>/manifest.json` is patched (if it exists)
- Key constants:
  - `OVERHEAD_SHARE = 0.185` (portion of cost base allocated to controllable overhead)
  - `SCHEMA_VERSION = "1.0"`
  - `EXPENSES_PAGE_ID = "expenses"`
  - Category/department/vendor lists are hardcoded in this script.
- Determinism:
  - Random generation is seeded per entity via MD5 of `exp-<entity_id>`.

## Usage
Run from the Financial Cockpit app root **after** generating cash flow data:
```bash
python scripts/operations/expenses.py
```

Minimal programmatic invocation:
```python
from naas_abi_marketplace.domains.finance.apps.financial_cockpit.scripts.operations.expenses import main

if __name__ == "__main__":
    main()
```

## Caveats
- Requires cash flow data to exist; otherwise exits with:
  - `No cash flow found — run scripts/performance/cash_flow.py first.`
- Generated output is **demo/fake** data and is tightly coupled to the expected directory structure under `web/data/entities/`.
- Only “controllable overhead” is modeled; payroll and cost of sales are intentionally excluded.
