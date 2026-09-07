# journal_entries.py

## What it is
- Standalone script that generates a **fake** `journal_entries.json` demo dataset for the Financial Cockpit “Journal Entries” page.
- It **does not invent entries**: it reads `general_ledger.json`, keeps only ledger lines with `source: "manual"`, and folds them into one row per journal entry.
- Adds workflow metadata (status/approver/approval date), and flags entries as **late** if posted more than `CLOSE_DEADLINE_DAYS` after the period end.
- Also emits monthly **memo** records (`kind: "memo"`) with the total number of ledger entries posted in the period (manual or not) as a denominator for “manual share” KPIs.

## Public API
This file is primarily a script; only `main()` is intended as an entry point.

- `main() -> None`
  - Finds entities that have `accounting/general_ledger.json`.
  - Builds journal entry records from the ledger.
  - Writes `web/data/entities/<entity_id>/accounting/journal_entries.json`.
  - Patches each entity `manifest.json` to register the dataset and updates `data_version`.

Internal helpers (not intended as public API):
- `_entities_with_sources()` — lists entity IDs that have a general ledger source file.
- `_load(entity_id, relative_path)` — loads JSON from an entity data path.
- `_build_records(entity_id, ledger)` — builds `kind: "entry"` (manual) and `kind: "memo"` records.
- `_scenarios(payload, records)` — reuses upstream scenarios or rebuilds from records.
- `_patch_manifest(entity_id, data_version)` — registers the dataset path in `manifest.json`.
- `_seed_for(entity_id)` / `_pick(rng, outcomes)` — deterministic RNG seeding and weighted status selection.

## Configuration/Dependencies
- Python standard library only (`glob`, `hashlib`, `json`, `os`, `random`, `datetime`).
- Expected directory layout (relative to this script):
  - `web/data/entities/<entity_id>/accounting/general_ledger.json` (input)
  - `web/data/entities/<entity_id>/accounting/journal_entries.json` (output)
  - `web/data/entities/<entity_id>/manifest.json` (patched if present)
- Key constants:
  - `CLOSED_THROUGH = "2026-06-30"`: periods after this are treated as “open” for workflow status probabilities.
  - `CLOSE_DEADLINE_DAYS = 6`: posting delay window before an entry is marked late.
  - `JE_PAGE_ID = "journal-entries"` and `JE_RELATIVE_PATH = "accounting/journal_entries.json"`: manifest registration.

## Usage
Run from the app root (after generating the general ledger dataset):
```python
import subprocess, sys

subprocess.check_call([sys.executable, "scripts/comptabilite/journal_entries.py"])
```

Or directly in a shell:
```bash
python scripts/comptabilite/journal_entries.py
```

## Caveats
- Requires `accounting/general_ledger.json` to exist per entity; otherwise the script exits with an error instructing you to run the upstream generator first.
- Output workflow fields (status/approver/approval timing) are **randomized but deterministic per entity** (seeded by entity ID); they are not derived from the ledger.
- Lateness is computed as:
  - `deadline = period_end + CLOSE_DEADLINE_DAYS`
  - `days_late = max(0, posted_date - deadline)` and `is_late = days_late > 0`
- Only manual lines (`source == "manual"`) are turned into `kind: "entry"` records; non-manual lines only contribute to monthly `ledger_entries` memo counts.
