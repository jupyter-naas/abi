# cash_position

## What it is
- Standalone Python script that generates a **fake Cash Position** demo dataset for the Financial Cockpit app.
- Reads each entity’s balance sheet dataset and splits the **“Cash & equivalents”** line across a fixed set of bank accounts using weighted allocations (with small monthly jitter).
- Writes one record per **account per month**, plus a **memo** record for short-term debt used by Net Cash KPIs.

## Public API
- `main() -> None`
  - Entry point when run as a script.
  - Finds entities that have a balance sheet dataset, generates cash position records, writes JSON output, and patches the entity manifest.

### Internal (non-public) helpers
- `AccountDef` (dataclass): defines account metadata and allocation parameters.
- `_entities_with_sources() -> list[str]`: returns entity IDs that have `balance_sheet/balance_sheet.json`.
- `_load(entity_id: str, relative_path: str) -> dict | None`: loads JSON for an entity dataset file.
- `_cash_by_period(balance_sheet: dict) -> list[tuple[str, str, str, float, float]]`: extracts `(period, scenario, scenario_year, cash, short_term_debt)` from the balance sheet records.
- `_build_records(entity_id: str, balance_sheet: dict) -> list[dict]`: builds per-period account records and memo short-term debt records.
- `_scenarios(payload: dict, records: list[dict]) -> list[dict[str, str]]`: reuses upstream `scenarios` if present, otherwise rebuilds scenario options from records.
- `_patch_manifest(entity_id: str, data_version: str) -> None`: updates `manifest.json` to include the cash-position dataset and sets `data_version`.
- `_seed_for(entity_id: str) -> int`: deterministic RNG seed per entity.

## Configuration/Dependencies
- **Dependencies:** Python standard library only (`glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`).
- **Input dataset (required):**
  - `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
  - Must contain `records` with at least categories:
    - `"Cash & equivalents"`
    - `"Short-term borrowings"` (used for memo record; defaulted to 0.0 if missing)
- **Output dataset (written):**
  - `web/data/entities/<entity_id>/cash_position/bank_accounts.json`
  - Manifest patched at:
    - `web/data/entities/<entity_id>/manifest.json` (if it exists)
- Key constants:
  - `CP_PAGE_ID = "cash-position"`
  - `CP_RELATIVE_PATH = "cash_position/bank_accounts.json"`
  - `SCHEMA_VERSION = "1.0"`

## Usage
Run from the app root (after generating the balance sheet data):

```bash
python scripts/treasury/cash_position.py
```

Minimal Python invocation:

```python
from scripts.treasury.cash_position import main

main()
```

## Caveats
- Requires balance sheet files to exist; otherwise exits with:
  - `"No balance sheet found — run scripts/performance/balance_sheet.py first."`
- Data is **fake/demo**:
  - Account allocations are based on fixed weights with random jitter, seeded deterministically per entity.
- Adds a memo record per period with `account_type: "memo"` and `account: "_short_term_debt"` to carry short-term debt context.
