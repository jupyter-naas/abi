# procurement.py

## What it is
- Standalone script (stdlib only) that generates a **fake Procurement demo dataset** for the Financial Cockpit.
- Reads each entity’s cash flow dataset and produces `purchase_orders.json` containing:
  - Synthetic **purchase orders** with milestone dates (`requested → approved → ordered → received → invoiced`)
  - Per-period **memo** aggregates (`cost_base`, `procurement_spend`)
- Ensures PO amounts reconcile to a fixed share of the cash-flow-derived monthly cost base.

## Public API
This file is intended to be run as a script; most helpers are internal.

- `main() -> None`
  - Finds entities with cash flow data.
  - Generates procurement records per entity.
  - Writes `web/data/entities/<entity_id>/procurement/purchase_orders.json`.
  - Patches `web/data/entities/<entity_id>/manifest.json` to register the dataset.

Internal (non-public) helpers:
- `ProcurementCategoryDef` (dataclass): category configuration used for generating orders.
- `_entities_with_sources()`: returns entity IDs that have a cash flow source file.
- `_load(entity_id, relative_path)`: loads JSON from an entity dataset path.
- `_cost_base_by_period(cash_flow)`: extracts `(period, scenario, scenario_year, revenue − EBITDA)` tuples from cash flow memos.
- `_build_records(entity_id, cash_flow)`: generates `order` and `memo` records for all periods.
- `_milestones(...)`: generates milestone dates and optional stall duration.
- `_split(total, weights)`: deterministic splitting that sums exactly back to `total`.
- `_scenarios(payload, records)`: reuses upstream `scenarios` if present; otherwise rebuilds from records.
- `_patch_manifest(entity_id, data_version)`: adds procurement dataset path and updates `data_version`.

## Configuration/Dependencies
- **Input dependency** (must exist per entity):
  - `web/data/entities/<entity_id>/cash_flow/cash_flow.json`
  - If none found, `main()` exits with: “run scripts/performance/cash_flow.py first.”
- **Output**:
  - `web/data/entities/<entity_id>/procurement/purchase_orders.json`
  - Updates `web/data/entities/<entity_id>/manifest.json`:
    - Registers page dataset under `datasets.pages["procurement"]`
    - Updates `data_version`
- Key constants affecting generation:
  - `PO_SHARE = 0.42`: fraction of monthly cost base allocated to PO-covered spend.
  - `STALL_RATE = 0.09`, `STALL_DAYS = (25, 95)`: probability and duration of stalled orders.
  - `DUAL_SIGNATURE_THRESHOLD = 75_000.0`: triggers longer approval time and `requires_dual_signature`.

## Usage
Run from the app root (after generating cash flow):

```bash
python scripts/operations/procurement.py
```

Minimal programmatic invocation:

```python
from naas_abi_marketplace.domains.finance.apps.financial_cockpit.scripts.operations.procurement import main

if __name__ == "__main__":
    main()
```

## Caveats
- The generated dataset is explicitly **fake demo data**.
- The script emits **milestone dates**, not an explicit “current stage”; downstream logic is expected to derive stage relative to a reporting window.
- Requires cash flow memo records for `Revenue` and `EBITDA` to compute `cost_base` (`max(0, Revenue − EBITDA)`).
