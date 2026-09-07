# `general_ledger.py`

## What it is

A standalone script that generates a **fake General Ledger** demo dataset for the Financial Cockpit app. It converts memo P&L figures (from the cash flow dataset) into balanced double-entry postings across sales, purchases, payroll, bank, and miscellaneous journals, and writes them to `web/data/entities/<entity>/accounting/general_ledger.json`.

## Public API

- `main() -> None`
  - Entry point when run as a script.
  - Discovers entities that have a cash flow source file, generates ledger records, writes `general_ledger.json`, and updates each entity’s `manifest.json`.

Internal helpers (module-private; not intended as stable API):

- `_load(entity_id: str, relative_path: str) -> dict | None`: load JSON from an entity dataset path.
- `_pnl_by_period(cash_flow: dict) -> list[tuple[period, scenario, scenario_year, revenue, cost_base]]`: extract period revenue and derive cost base from Revenue and EBITDA memos.
- `_build_records(entity_id: str, cash_flow: dict) -> list[dict]`: generate line and memo records for the entity.
- `LedgerBuilder.entry(...) -> None`: append balanced posting lines for one accounting entry (rounding drift absorbed on last line).
- `_patch_manifest(entity_id: str, data_version: str) -> None`: register the dataset page in the entity manifest.
- `_entities_with_sources() -> list[str]`: list entities with `cash_flow/cash_flow.json`.
- `_scenarios(payload: dict, records: list[dict]) -> list[dict[str,str]]`: reuse upstream scenarios or rebuild from generated records.

## Configuration/Dependencies

- **Python stdlib only**: `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`.
- **Input dataset required** (per entity):
  - `web/data/entities/<entity_id>/cash_flow/cash_flow.json`
  - Must contain memo records with:
    - `activity: "memo"`
    - `category: "Revenue"` and `category: "EBITDA"`
    - `period`, `scenario`, `scenario_year`, `amount`
- **Output written** (per entity):
  - `web/data/entities/<entity_id>/accounting/general_ledger.json`
  - Updates: `web/data/entities/<entity_id>/manifest.json` (`datasets.pages["general-ledger"]`)
- Key constants affecting generated data:
  - `CLOSED_THROUGH = "2026-06-30"`: months after this are marked open via memo `open_period`.
  - `VAT_RATE`, `PAYROLL_SHARE`, `SOCIAL_CHARGE_SHARE`, `DEPRECIATION_SHARE`
  - Entry counts per month: `SALES_ENTRIES`, `PURCHASE_ENTRIES`, `COLLECTION_ENTRIES`, `PAYMENT_ENTRIES`, `MANUAL_ENTRIES`
  - `LATE_POSTING_RATE`: share of manual entries posted after the close deadline window.

## Usage

Run from the app root (after generating cash flow):

```python
# From a shell:
# python scripts/performance/cash_flow.py
# python scripts/comptabilite/general_ledger.py
```

Or invoke programmatically:

```python
from naas_abi_marketplace.domains.finance.apps.financial_cockpit.scripts.comptabilite import general_ledger

general_ledger.main()
```

## Caveats

- The dataset is **deterministic per entity** (seeded from `entity_id`) but will differ across entities.
- If no entities contain `cash_flow/cash_flow.json`, the script exits with:
  - `No cash flow found — run scripts/performance/cash_flow.py first.`
- The script generates **demo** accounting data:
  - Posts are balanced to the cent by adjusting the last line of each entry.
  - Manual entries are flagged with `source: "manual"` and may be posted late based on `LATE_POSTING_RATE`.
- Period “open/closed” status is encoded as a **memo record** (`metric: "open_period"`) based on string comparison to `CLOSED_THROUGH` (ISO dates).
