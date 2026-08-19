# customer_invoices

## What it is
- Standalone Python script that generates a **fake** Accounts Receivable (AR) / customer open-invoice dataset for the Financial Cockpit demo.
- Reads upstream demo datasets:
  - Balance Sheet (`Trade receivables` line)
  - Cash Flow (memo `Revenue`)
- Produces per-entity output JSON:
  - Open invoice **stock** snapshots per period (`kind="invoice"`)
  - Per-period **memo** aggregates (`kind="memo"`) including `revenue`, `invoiced`, `collected`, `collectible`, `receivables`, `dso`
- Ensures invoice totals reconcile back to the balance sheet AR line, and collections reconcile via:
  - `closing AR = opening AR + invoiced − collected`

## Public API
This file is designed to be run as a script.

- `main() -> None`
  - Discovers entities with required source datasets.
  - Builds receivables records and writes `receivables/receivables.json` per entity.
  - Updates each entity `manifest.json` to include the dataset page entry.

Internal helpers (not intended as public API):
- `CustomerDef` (dataclass): defines demo customer behavior (weights, terms, aging profile, invoice count, disputes).
- `_build_records(entity_id, balance_sheet, cash_flow)`: creates invoice and memo rows per period.
- `_entities_with_sources()`: finds entities that have both balance sheet and cash flow sources.
- `_patch_manifest(entity_id, data_version)`: registers output dataset in the entity manifest.

## Configuration/Dependencies
- Python standard library only.
- File system layout (relative to this script):
  - `APP_ROOT = .../financial_cockpit`
  - Input data:
    - `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
    - `web/data/entities/<entity_id>/cash_flow/cash_flow.json`
  - Output data:
    - `web/data/entities/<entity_id>/receivables/receivables.json`
  - Manifest updated:
    - `web/data/entities/<entity_id>/manifest.json`
- Key constants:
  - `RECEIVABLES_LINE = "Trade receivables"`
  - `DSO_TRAILING_MONTHS = 3` (DSO denominator smoothing window)
  - `AR_PAGE_ID = "customer-invoices"` and `AR_RELATIVE_PATH = "receivables/receivables.json"`

## Usage
Run from the Financial Cockpit app root **after** generating upstream datasets:

```bash
python scripts/operations/customer_invoices.py
```

Minimal Python entrypoint (equivalent to running the script):

```python
from scripts.operations.customer_invoices import main

if __name__ == "__main__":
    main()
```

Outputs (per entity):
- `web/data/entities/<entity_id>/receivables/receivables.json`
- `manifest.json` updated to include the `customer-invoices` dataset page.

## Caveats
- Will exit with an error if no entities contain both required sources (balance sheet and cash flow); upstream scripts must be run first.
- Generated data is deterministic per entity (seeded from `entity_id`), but still “fake” and based on hardcoded demo customer definitions.
- Invoices represent **period-end open invoice snapshots** (stock), not a transactional ledger of invoice creation and settlement events.
