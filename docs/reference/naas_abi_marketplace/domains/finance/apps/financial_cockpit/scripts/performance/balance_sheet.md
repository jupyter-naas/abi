# `balance_sheet.py`

## What it is
- Standalone stdlib-only script that generates a deterministic **fake balance sheet** dataset for Financial Cockpit demo entities.
- Writes monthly period-end snapshots from **Jan 2023 → Dec 2026**.
- Ensures the balance sheet identity holds exactly: **Assets = Equity + Liabilities** (with **Reserves** as the balancing plug).
- Integrates output into each entity’s `manifest.json` so the app can discover the dataset.

## Public API
- `main() -> None`
  - Discovers eligible entities (those whose manifest declares a `pnl` page), generates balance sheet data for each, writes JSON output, and patches entity manifests.
- `LineDef` (`@dataclass(frozen=True)`)
  - Internal structure describing a balance sheet line (section/group/category plus flags like `is_cash`, `is_debt`, `is_current`).

Internal helpers (not intended as public API):
- `_entities_with_pnl() -> list[str]`: returns entity IDs that have a `pnl` dataset page in their manifest.
- `_build_records(entity_id: str) -> list[dict]`: creates per-line monthly records for the entity (deterministic via seeded RNG).
- `_months() -> list[tuple[str, str, str]]`: generates `(period_end_date, scenario_month, scenario_year)` tuples for the configured year range.
- `_scenarios(months) -> list[dict[str, str]]`: builds scenario options (years and month labels) used by the portal period picker.
- `_patch_manifest(entity_id: str, data_version: str) -> None`: adds the balance sheet page to the entity manifest and updates `data_version`.

## Configuration/Dependencies
- Dependencies: Python standard library only (`calendar`, `glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`).
- Key paths/constants:
  - `APP_ROOT` is computed as two directories above this script.
  - Output root: `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
  - Manifest patched at: `web/data/entities/<entity_id>/manifest.json`
  - Manifest page key: `balance-sheet`
  - Manifest relative dataset path: `balance_sheet/balance_sheet.json`
- Time range:
  - `START_YEAR = 2023`, `END_YEAR = 2026`

## Usage
Run from the Financial Cockpit app root (as indicated by the module docstring):

```bash
python scripts/performance/balance_sheet.py
```

If you need to invoke it programmatically:

```python
from scripts.performance.balance_sheet import main

main()
```

## Caveats
- Only entities whose `manifest.json` contains a `datasets.pages.pnl` entry are processed.
- The script overwrites `balance_sheet/balance_sheet.json` and updates each entity’s `manifest.json` (`data_version` and `datasets.pages["balance-sheet"]`).
- Generated values are deterministic per `entity_id` (seeded by MD5 of the ID), but `data_version` is the current timestamp.
