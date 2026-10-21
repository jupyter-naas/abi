# `settings` (Administration settings demo-data generator)

## What it is
- A standalone Python script that generates **fake Administration settings datasets** for the Financial Cockpit demo.
- Reads upstream demo datasets from the `_demo` entity (general ledger, cost centers, bank accounts) and writes **global** admin datasets under `web/data/globals/admin/*.json`.
- Uses deterministic seeding for fabricated parts (integrations, logs, etc.) so reruns are stable.

## Public API
- `main() -> None`
  - Entry point that:
    - Loads upstream datasets from `web/data/entities/_demo/...`
    - Derives admin settings datasets (org, accounting settings) from upstream data
    - Fabricates the remaining datasets (roles/permissions, workflows, integrations, logs)
    - Writes multiple JSON files to `web/data/globals/admin/`

Internal helpers (not intended as public API, but useful for operators reading the code):
- `_load_entity(relative_path: str) -> dict | None`: Load an entity JSON dataset from `_demo`.
- `_write(name: str, records: list[dict], data_version: str) -> None`: Write one admin dataset to `globals/admin/{name}.json`.
- `_cost_center_facts(cost_centers: dict) -> (business_units, cost_centers)`: Derive BU and cost center settings from the cost centers roster.
- `_roles_and_permissions() -> (roles, permissions)`: Build role and permission matrices from constants.
- `_accounting_from_ledger(ledger: dict) -> (chart_of_accounts, fiscal_years, accounting_periods, journals)`: Derive accounting settings from posted ledger lines.
- `_workflow_rows() -> (approval_flows, notifications, validation_rules)`: Materialize workflow configuration from constants.
- `_integration_rows(bank_accounts: dict | None, rng: random.Random)`: Build integration settings (ERP, banking, API clients, import/export jobs).
- `_log_rows(rng: random.Random)`: Generate system logs and synchronization history.

## Configuration/Dependencies
- Python standard library only: `json`, `os`, `random`, `datetime`.
- Filesystem layout assumptions (relative to this script):
  - App root: `.../financial_cockpit/`
  - Reads:
    - `web/data/entities/_demo/accounting/general_ledger.json` (**required**)
    - `web/data/entities/_demo/cost_centers/cost_centers.json` (**required**)
    - `web/data/entities/_demo/cash_position/bank_accounts.json` (optional; affects banking integrations only)
  - Writes:
    - `web/data/globals/admin/*.json`
- Key constants affecting output:
  - `SEED = 20260731` (deterministic RNG for fabricated datasets)
  - `CLOSED_THROUGH = "2026-06-30"` (determines which accounting periods are “Closed”)
  - `NOW = datetime(2026, 7, 31, 18, 30)` (timestamp anchor for fabricated logs/sync status)
  - `SCHEMA_VERSION = "1.0"` included in all outputs

## Usage
Run from the Financial Cockpit app root (after generating upstream demo data):
```python
# scripts/run_admin_settings.py
from scripts.administration.settings import main

if __name__ == "__main__":
    main()
```

Or directly:
```bash
python scripts/administration/settings.py
```

Outputs multiple datasets such as:
- `business_units.json`, `cost_centers.json`
- `roles.json`, `permissions.json`
- `chart_of_accounts.json`, `fiscal_years.json`, `accounting_periods.json`, `journals.json`
- `approval_flows.json`, `notifications.json`, `validation_rules.json`
- `integrations_erp.json`, `integrations_banking.json`, `integrations_api.json`, `imports_exports.json`
- `system_logs.json`, `sync_history.json`

## Caveats
- Hard-fails if upstream required datasets are missing (`general_ledger.json` or `cost_centers.json`), with guidance to run the upstream generators first.
- Writes are **global** (`web/data/globals/admin/`), not per-entity.
- Banking integrations are only generated if `bank_accounts.json` exists and contains non-`memo` records with a `bank` field.
