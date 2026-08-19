# Cockpit demo build scripts

Everything the cockpit demo needs to go from committed source JSON to the
datasets the UI serves. Runtime modules the app imports (config loader, data
store, payload builders, `data_source.py`) live one level up in
[`../`](../) — this folder holds the build-time pieces only.

## Layout

```
scripts/
├── person_sources.py                 # read data/demo/person/<slug>/index.json
├── demo_graph_builder.py             # source JSON → graphs/demo/personnel.ttl
├── workforce_metrics.py              # tenure / seniority / scolarity KPIs
├── workforce_metrics_test.py         # unit tests for the metrics
├── export_demo_apps_from_graph.py    # graph TTL → data/entities/<id>/<page>/
├── validate_graph_layout.mjs         # graph page layout sanity check
└── README.md                         # this file
```

## Pipeline

Run from the personnel module root (`domains/personnel/`):

```bash
make demo-graph    # demo_graph_builder.py → graphs/demo/personnel.ttl
make demo-data     # export_demo_apps_from_graph.py → apps/cockpit/data/ + ObjectStorage
```

Serving:

```bash
make app-personnel-cockpit        # dev server on whatever datasets already exist
make app-personnel-cockpit-demo   # rebuild the demo datasets first, then serve
```

`make app-personnel-cockpit` never rebuilds: with no datasets published the
server still starts and the pages render empty.

## Scripts

### `person_sources.py`

Loads the committed demo inputs from `data/demo/person/<slug>/index.json` and
shapes them for the pipelines:

- `load_person_sources(dir)` — read every `<slug>/index.json`
- `sources_to_employees(payloads)` — HR roster rows from an optional `roster` block (none of the demo files carry one today, so this yields no employment records)
- `sources_to_profile_urls(payloads)` — full name → profile URL
- `sources_to_experiences(payloads)` — `ActOfWorking` / `ActOfStudying` records

These JSON files are the source of truth for the demo — edit them directly,
then re-run `make demo-data`. Each file holds `person` and `records[]` (one row
per process).

### `demo_graph_builder.py`

Runs the `ActOfWorking` / `ActOfStudying` pipelines over the source JSON and
serialises schema + individuals to `graphs/demo/personnel.ttl`.

### `export_demo_apps_from_graph.py`

Runs personnel SPARQL queries against `graphs/demo/personnel.ttl` and writes
page-ready aggregates the static UI loads via `api/routes.py`.

**Reads:**

- `graphs/demo/personnel.ttl` (requires `make demo-graph` first)
- `ontologies/queries/PersonnelSparqlQueries.ttl`
- `config.yaml` (page list, logs defaults)
- `workforce_metrics.py` (workforce KPI enrichment)

**Writes:**

```
apps/cockpit/data/entities/<entity_id>/<page_id>/*.json
apps/cockpit/data/entities/<entity_id>/manifest.json
```

…and publishes the same tree to ObjectStorage under
`personnel/apps/cockpit/data/`, which is what the server reads.

When adding a page, register its dataset mapping in this script's
`page_datasets`, then regenerate with `make demo-data`. See
[`../AGENTS.md`](../AGENTS.md) for the full page checklist.

## Direct invocation

From the ABI repository root:

```bash
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/scripts/demo_graph_builder.py
uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/scripts/export_demo_apps_from_graph.py
```
