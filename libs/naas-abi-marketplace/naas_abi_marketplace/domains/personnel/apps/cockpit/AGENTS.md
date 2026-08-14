# AGENTS — cockpit

Lightweight example. Prefer editing demo JSON / SPARQL stubs over growing the UI.

## Naming
- Python package: `cockpit`
- Catalog id / kebab: `personnel-cockpit`
- Object-storage prefix (personnel module datastore): `personnel/apps/cockpit/`
- Entity ids mirror url slugs with hyphens → underscores (``demo`` → ``demo``)

## Data
Committed datasets live under ``data/`` and are served to the UI through
``api/`` (``GET /api/personnel-cockpit/entities/demo/...``).

- ``data/entities/<id>/manifest.json`` — page → dataset paths for that entity
- ``data/entities/<id>/<page>/`` — page-ready aggregates the UI reads
- ``data/globals/entities.json`` — sidebar entity dropdown (organization perimeters)
- Build input graph: ``domains/personnel/data/graph/personnel_demo.ttl``

Regenerate with ``make demo-data`` (from ``domains/personnel``). Dev server:
``make app-personnel-cockpit``. Do not invent manager hierarchies — not in the ontology.

## Web layout

Mirrors Financial Cockpit conventions (Next.js-style folders, vanilla ES modules):

```
web/
├── app/[entitySlug]/[pageId]/page.js   # route contract
├── components/pages/<pageId>/          # one module per manifest page
├── lib/{api,routes,pages,registry}.js
└── js/shell.js                         # bootstrap + nav
```

URLs: ``/{url_slug}/{pageId}`` (e.g. ``/demo/graph``). API reads ``entity_id`` paths.

## Pages
| page_id | SPARQL tools / content |
|---|---|
| workforce | `find_active_employees`, `find_employees_by_status`, `find_headcount_by_job_family` |
| graph | person search + distance 1–3 hop filter on process graph |
| logs | birth registrations → `logs/ledger.json` (SPO triples + source; URI-only types/properties) |
| processes | BFO 7-buckets process docs (`processes/processes.json`) |
