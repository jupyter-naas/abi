# Cockpit data export scripts

Scripts that **write committed cockpit datasets** under `apps/cockpit/data/`.

Graph builders, LinkedIn seed data, and shared helpers live in
[`../../sandbox/`](../../sandbox/) instead — they prepare inputs or compute
metrics but do not emit the JSON the UI serves.

## Layout

```
scripts/
├── export_source_person_files.py   # seed → data/source/person/<slug>/index.json
├── export_demo_apps_from_graph.py    # graph TTL → data/entities/<id>/<page>/
└── README.md                         # this file
```

## Pipeline

Run from the personnel module root (`domains/personnel/`):

```bash
make demo-source   # optional: refresh source JSON from sandbox LinkedIn seeds
make demo-graph    # sandbox/generate_demo_graph.py → data/graph/personnel_demo.ttl
make demo-data     # export_demo_apps_from_graph.py → apps/cockpit/data/
```

Or the full chain in one step:

```bash
make demo-data
```

Start the dev server after regenerating:

```bash
make app-personnel-cockpit
```

## Scripts

### `export_source_person_files.py`

Materialises per-person build inputs from sandbox seed data
(`sandbox/linkedin_experience.py`).

**Writes:**

```
apps/cockpit/data/source/person/<slug>/index.json
```

Each file holds `person`, optional `employment`, and `records[]` (one row per
process). Edit these JSON files directly when tuning demo people; re-run
`make demo-graph` and `make demo-data` afterward.

### `export_demo_apps_from_graph.py`

Runs personnel SPARQL queries against `data/graph/personnel_demo.ttl` and writes
page-ready aggregates the static UI loads via `api/routes.py`.

**Reads:**

- `data/graph/personnel_demo.ttl` (requires `make demo-graph` first)
- `ontologies/queries/PersonnelSparqlQueries.ttl`
- `config.yaml` (page list, logs defaults)
- `sandbox/workforce_metrics.py` (workforce KPI enrichment)

**Writes:**

```
apps/cockpit/data/entities/<entity_id>/<page_id>/*.json
apps/cockpit/data/entities/<entity_id>/manifest.json
```

When adding a page, register its dataset mapping in this script's
`page_datasets`, then regenerate with `make demo-data`. See
[`../AGENTS.md`](../AGENTS.md) for the full page checklist.

## Direct invocation

From the ABI repository root:

```bash
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/scripts/export_source_person_files.py
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/sandbox/generate_demo_graph.py
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/scripts/export_demo_apps_from_graph.py
```
