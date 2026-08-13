# AGENTS — cockpit

Lightweight example. Prefer editing demo JSON / SPARQL stubs over growing the UI.

## Naming
- Python package: `cockpit`
- Catalog id / kebab: `personnel-cockpit`
- Object-storage prefix (personnel module datastore): `personnel/apps/cockpit/`

## Data
Committed datasets live under ``web/data/`` and are served to the UI through
``api/`` (``GET /api/personnel-cockpit/entities/_demo/...``).

- ``web/data/entities/_demo/source/`` — one JSON file per SPARQL tool
- ``web/data/entities/_demo/<page>/`` — page-ready aggregates the UI reads
- ``web/data/globals/`` — entity registry
- Build input graph: ``domains/personnel/data/graph/personnel_demo.ttl``

Regenerate with ``make demo-data`` (from ``domains/personnel``). Dev server:
``make app-personnel-cockpit``. Do not invent manager hierarchies — not in the ontology.

## Pages
| page_id | SPARQL tools / content |
|---|---|
| workforce | `find_active_employees`, `find_employees_by_status`, `find_headcount_by_job_family` |
| graph | person search + distance 1–3 hop filter on process graph |
| logs | birth registrations → `logs/ledger.json` (SPO triples + source; URI-only types/properties) |
| processes | BFO 7-buckets process docs (`processes/processes.json`) |
