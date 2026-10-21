# `financial_close.py`

## What it is
- Standalone script (stdlib only) that generates a **fake** “Financial Close” demo dataset for the Financial Cockpit app.
- Reads each entity’s General Ledger dataset to determine which periods are open/locked, then produces per-period:
  - close checklist **tasks**
  - close **issues**
  - aggregate **memos**
- Writes output JSON under `web/data/entities/<entity_id>/financial_close/financial_close.json` and patches each entity’s `manifest.json` to register the dataset.

## Public API
- `main() -> None`
  - Entry point: finds entities with a General Ledger source, generates records, writes dataset JSON, and updates manifests.

> Everything else is internal helper code (prefixed with `_`), but relevant constants include:
- `PROGRESS_DAY`: business day cut-off used to simulate the currently in-progress close.
- `TASKS`: checklist task definitions (labels, areas, owners, planned windows).
- `LATE_TASK_RATE`, `VALIDATION_RATE`, `BLOCKED_RATE`, `ISSUES_PER_CLOSE`: parameters controlling randomness.

## Configuration/Dependencies
- **Input dependency (must exist per entity):**
  - `web/data/entities/<entity_id>/accounting/general_ledger.json` (`GL_RELATIVE_PATH`)
- **Output:**
  - `web/data/entities/<entity_id>/financial_close/financial_close.json` (`CLOSE_RELATIVE_PATH`)
  - Updates `web/data/entities/<entity_id>/manifest.json` to include dataset page id `financial-close`.
- **Entity discovery:**
  - Scans `web/data/entities/*/manifest.json` and keeps entities that also have the General Ledger file.
- **Deterministic randomness:**
  - Seed derived from `md5("close-<entity_id>")` for stable outputs per entity.

## Usage
Run from the app root after generating the General Ledger dataset:
```python
# scripts/comptabilite/financial_close.py
if __name__ == "__main__":
    main()
```

Command line:
```bash
python scripts/comptabilite/financial_close.py
```

## Caveats
- Exits with an error if no General Ledger source is found:
  - `"No general ledger found — run scripts/comptabilite/general_ledger.py first."`
- Period “phase” is inferred from the ledger’s `memo` records where `metric == "open_period"`:
  - first open period becomes the “running” close; later open periods are treated as “ahead”.
- Business days skip weekends only (no holiday calendar).
- Data is intentionally synthetic (“fake”) and uses fixed task/issue templates and rates.
