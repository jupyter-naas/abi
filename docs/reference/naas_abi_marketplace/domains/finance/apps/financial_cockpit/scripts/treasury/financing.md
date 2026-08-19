# financing.py

## What it is
- Standalone script that generates a **fake financing (loan book) dataset** for the Financial Cockpit demo.
- Reads each entity’s balance sheet and splits total borrowings into predefined loan facilities (fixed weights), producing **one record per facility per month** plus a memo record for total assets.
- Writes output to `web/data/entities/<entity_id>/financing/loans.json` and updates each entity’s `manifest.json` to include the financing dataset.

## Public API
- `main() -> None`
  - Entry point: discovers entities with a balance sheet, builds financing records, writes `loans.json`, and patches entity manifests.

### Data structures/constants (module-level)
- `@dataclass(frozen=True) LoanDef`
  - Defines a loan facility template:
    - `key`, `label`, `lender`, `instrument`, `bucket`, `weight`, `annual_rate`, `is_floating`, `origination`, `maturity`, `covenant`
- `LOANS: list[LoanDef]`
  - Fixed facility book used to split borrowings.
- `EURIBOR_BY_YEAR: dict[str, float]`, `DEFAULT_EURIBOR`
  - Reference rate used for floating-rate facilities.
- Output and input locations:
  - `ENTITIES_DIR`, `BS_RELATIVE_PATH`, `FIN_RELATIVE_PATH`, `FIN_PAGE_ID`

## Configuration/Dependencies
- **Python stdlib only**: `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`.
- Requires pre-existing balance sheet dataset per entity:
  - `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
- Script searches for entities by scanning:
  - `web/data/entities/*/manifest.json`
  - and checking existence of the balance sheet file above.
- Balance sheet categories used:
  - Borrowings:
    - `"Long-term borrowings"` → bucket `"long"`
    - `"Short-term borrowings"` → bucket `"short"`
  - Asset lines (summed to compute memo “Total assets”):
    - `ASSET_LINES` (e.g., `"Cash & equivalents"`, `"Inventory"`, ...)

## Usage
Run from the app root (after generating upstream demo data):
```python
# terminal command (run from app root)
# python scripts/treasury/financing.py
```

Minimal programmatic usage:
```python
from naas_abi_marketplace.domains.finance.apps.financial_cockpit.scripts.treasury.financing import main

main()
```

Outputs per entity:
- `web/data/entities/<entity_id>/financing/loans.json`
- Updates `web/data/entities/<entity_id>/manifest.json`:
  - Adds `datasets.pages["financing"] = ["financing/loans.json"]`
  - Updates `data_version`

## Caveats
- Designed for **demo data generation**; outputs are deterministic per entity (seeded by entity id) but weights/rates are predefined in code.
- Facilities are allocated by normalized weights within each bucket; totals reconcile to the balance sheet borrowings lines.
- If `period > loan.maturity`, the record is marked `is_matured=True` and `outstanding`/`interest` are forced to `0.0` (repayment/drawdown still computed from prior period balances).
