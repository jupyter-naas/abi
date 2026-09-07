# fixed_assets

## What it is

Standalone Python script that generates a **fake fixed-asset register** dataset for the Financial Cockpit demo. It reads each entity’s balance sheet dataset and produces `fixed_assets/fixed_assets.json` such that:

- Monthly **net book value totals** for:
  - **Intangible assets**
  - **Property, plant & equipment**
- match the balance sheet **exactly** (by scaling a relative-unit asset register per month).

It emits two record kinds:
- `kind="asset"`: per-asset **period-end snapshot** (stock; do not sum across months).
- `kind="memo"`: per-period aggregates (`gross_value`, `net_value`, `accumulated_depreciation`, `depreciation_charge`, `acquisitions`, `disposals`) where some metrics are flows.

## Public API

This module is intended to be run as a script; there is no stable library API.

- `main() -> None`
  - Discovers entities that have a balance sheet dataset.
  - Builds fixed-asset records per entity.
  - Writes JSON to `web/data/entities/<entity_id>/fixed_assets/fixed_assets.json`.
  - Updates `web/data/entities/<entity_id>/manifest.json` to register the dataset.

Internal helpers (implementation detail):
- `CategoryDef` (dataclass): defines asset categories (class, useful life, weights, counts, names).
- `Asset` (dataclass): represents an asset in the generated register.
- `_build_records(entity_id: str, balance_sheet: dict) -> list[dict]`: creates all `asset` and `memo` records for all periods.
- `_entities_with_sources() -> list[str]`: finds entity folders with a balance sheet file.
- `_patch_manifest(entity_id: str, data_version: str) -> None`: adds the fixed-assets dataset to the manifest.

## Configuration/Dependencies

- **Runtime dependencies**: Python standard library only (`glob`, `hashlib`, `json`, `os`, `random`, `dataclasses`, `datetime`).
- **Input required** (must exist per entity):
  - `web/data/entities/<entity_id>/balance_sheet/balance_sheet.json`
- **Output written**:
  - `web/data/entities/<entity_id>/fixed_assets/fixed_assets.json`
  - `web/data/entities/<entity_id>/manifest.json` (patched)
- Key constants:
  - `FA_PAGE_ID = "fixed-assets"`
  - `SCHEMA_VERSION = "1.0"`
  - Balance sheet lines used:
    - `Intangible assets`
    - `Property, plant & equipment`
- Determinism:
  - Data generation is seeded per entity via MD5 of `fa-<entity_id>` (`_seed_for`).

## Usage

Run from the Financial Cockpit app root (after generating the balance sheet dataset):

```python
import subprocess
import sys

subprocess.check_call([sys.executable, "scripts/comptabilite/fixed_assets.py"])
```

Or directly in a shell:

```bash
python scripts/comptabilite/fixed_assets.py
```

## Caveats

- Requires the balance sheet dataset to exist first; otherwise the script exits with:
  - `No balance sheet found — run scripts/performance/balance_sheet.py first.`
- `kind="asset"` records are **snapshots**; summing them across periods is incorrect.
- `kind="memo"` metrics include both stocks and flows:
  - Stocks: `gross_value`, `net_value`, `accumulated_depreciation` (interpret per period)
  - Flows: `depreciation_charge`, `acquisitions`, `disposals` (sum over a window)
- Asset disposals are only scheduled for legacy assets and only when they still have sufficient remaining life (see `DISPOSAL_MIN_MONTHS`).
