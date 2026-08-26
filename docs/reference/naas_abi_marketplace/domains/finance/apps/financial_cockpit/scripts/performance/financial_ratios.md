# `financial_ratios`

## What it is
A standalone Python script that generates a **fake** “Financial Ratios” demo dataset for the Financial Cockpit app by deriving ratios from existing demo datasets:

- **Balance sheet** (`balance_sheet/balance_sheet.json`) for stock-based ratios
- **Cash flow** (`cash_flow/cash_flow.json`) for flow-based ratios (using published memo P&L lines)

It writes `financial_ratios/financial_ratios.json` per entity and patches each entity’s `manifest.json` to include the new page dataset.

## Public API
- `main() -> None`
  - Entry point when executed as a script.
  - Finds eligible entities, generates ratio records, writes output JSON, and patches the manifest.

Internal helpers (not intended as public API, but relevant for operators):
- `_entities_with_sources() -> list[str]`: returns entity IDs that have both balance sheet and cash flow datasets.
- `_load(entity_id: str, relative_path: str) -> dict | None`: loads a JSON dataset for an entity.
- `_build_records(entity_id: str, balance_sheet: dict, cash_flow: dict) -> list[dict]`: computes ratio records per period and ratio definition.
- `_patch_manifest(entity_id: str, data_version: str) -> None`: adds the financial ratios page to the entity manifest and updates `data_version`.

## Configuration/Dependencies
- **Dependencies**: Python standard library only (`glob`, `json`, `os`, `dataclasses`, `datetime`).
- **Filesystem layout assumptions** (relative to this script location):
  - App root: `.../domains/finance/apps/financial_cockpit`
  - Data root: `web/data/entities/<entity_id>/`
  - Inputs required per entity:
    - `balance_sheet/balance_sheet.json`
    - `cash_flow/cash_flow.json`
  - Output per entity:
    - `financial_ratios/financial_ratios.json`
  - Manifest patched:
    - `web/data/entities/<entity_id>/manifest.json`

## Usage
Run from the Financial Cockpit app root **after** generating upstream datasets:

```bash
python scripts/performance/balance_sheet.py
python scripts/performance/cash_flow.py
python scripts/performance/financial_ratios.py
```

Minimal runnable invocation (programmatic):

```python
from scripts.performance.financial_ratios import main

main()
```

## Caveats
- Requires both upstream datasets to exist; otherwise exits with:
  - “No balance sheet + cash flow found — run ... first.”
- Flow-based ratios (gross/EBITDA margin) are derived from cash-flow “memo” lines:
  - `Revenue`, `Gross profit`, `EBITDA`
  - Net income is taken from `activity == "operating"` and `category == "Net income"`.
- Flow figures are computed over a **trailing twelve month** window and **annualized** when fewer than 12 months are available.
- Ratios are only emitted when the denominator is positive; otherwise the ratio is skipped for that period (e.g., zero revenue, zero equity, zero liabilities).
