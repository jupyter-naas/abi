# supplier_invoices

## What it is
A standalone script that generates a **fake Accounts Payable (supplier invoices) demo dataset** for the Financial Cockpit app.

- Reads upstream demo datasets:
  - `balance_sheet/balance_sheet.json` (Trade payables stock per period)
  - `cash_flow/cash_flow.json` (memo P&L to derive purchases)
- Outputs, per entity:
  - `payables/payables.json` containing:
    - `bill` records: open supplier invoices at each period end (stock snapshot)
    - `memo` records: per-period aggregates (`purchased`, `paid`, `payables`, `dpo`)
- Updates each entity `manifest.json` to register the dataset page.

## Public API
This module is primarily a script; only `main()` is intended for direct use.

- `main() -> None`
  - Finds entities with required sources, builds payables records, writes `payables/payables.json`, patches manifests.

Internal helpers (not intended as stable API):
- `SupplierDef` (dataclass): supplier configuration (weights, payment terms, aging profile, etc.)
- `_entities_with_sources()`: list entities that have both balance sheet and cash flow sources.
- `_build_records(entity_id, balance_sheet, cash_flow)`: generates all `bill` and `memo` records for an entity.
- `_supplier_bills(...)`: splits a supplier’s balance into multiple bills across aging buckets.
- `_patch_manifest(entity_id, data_version)`: registers `supplier-invoices` dataset in entity manifest.

## Configuration/Dependencies
- **Python stdlib only**: `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`.
- Assumes repo layout relative to this file:
  - `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
  - `web/data/entities/<entity_id>/cash_flow/cash_flow.json`
  - Writes to `web/data/entities/<entity_id>/payables/payables.json`
- Key constants:
  - `PAYABLES_LINE = "Trade payables"` (balance sheet category used)
  - `DPO_TRAILING_MONTHS = 3` and `DAYS_PER_MONTH = 30.4375` (DPO computation)
  - `AGING_BUCKETS` (aging bucket boundaries)
  - `CALENDAR_WEEKS = 8` (payment calendar horizon)
  - `SUPPLIERS` (fixed supplier book: weights/terms/aging profiles/bill counts)

## Usage
Run from the Financial Cockpit app root (after generating upstream datasets):

```bash
python scripts/operations/supplier_invoices.py
```

Minimal programmatic invocation:

```python
from naas_abi_marketplace.domains.finance.apps.financial_cockpit.scripts.operations import supplier_invoices

supplier_invoices.main()
```

## Caveats
- Requires upstream demo data to exist; otherwise exits with:
  - “run scripts/performance/balance_sheet.py and scripts/performance/cash_flow.py first.”
- Generated bills are **period-end snapshots** (stock), not a full transaction ledger.
- Randomization is deterministic per entity (`md5("ap-<entity_id>")`), so results are stable for the same entity ID and source data.
