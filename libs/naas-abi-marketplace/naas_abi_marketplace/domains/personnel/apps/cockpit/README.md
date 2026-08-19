# Personnel Cockpit

Lightweight S1 workforce analytics example - same *registration / data / page*
shape as [Financial Cockpit](../../finance/apps/financial_cockpit), without the
Next.js surface. SPARQL-shaped JSON, static UI, FastAPI dataset layer.

```bash
cd domains/personnel && make demo-data              # regenerate apps/cockpit/data from ontology graph
cd domains/personnel && make app-personnel-cockpit  # API + static UI dev server
```

## Configuration

`config.yaml` controls the runtime shell:

- `brand`: product name, rail label/mark, favicon, and font stylesheet
- `app.default_page`: landing page
- `app.pages`: page URL, label, order, enabled state, permissions, icon, banner
- `theme`: CSS variables, banner icons, BFO colours, and process-slide colours
- `graph`: initial person/distance/view, canvas sizing, and parameter controls

The server validates this file at startup and exposes only its public UI fields
through `GET /api/personnel-cockpit/config`. Page components still have to exist
in `web/lib/registry.js`. This static demo has no authenticated user session, so
`public` is the only granted permission; other permissions are denied by the
dataset API.

The default entity is data-driven: set `"is_default": true` on an organization
in `data/globals/entities.json`, or the first organization is used.

---

## What the graph can represent (analysis)

```
              [KPIs]
     active headcount · status mix · open roles · by job family
     ─────────────────────────────────────────────────────────
           [Slices]
      org · title · tenure · age × sex pyramid (from birth)
     ─────────────────────────────────────────────────────────
              [Trace]
   person card · employment record · birth lineage · kinship · trust
```

| View | Graph basis | Ready today? |
|---|---|---|
| Active headcount | `EmploymentRecord` without `termination_date` | Query yes · **no writer yet** → demo JSON |
| Status mix | `EmploymentStatus.status_value` | Query yes · demo JSON |
| Headcount by job family | `JobPosition.job_family` | Query yes · demo JSON |
| Open requisitions | vacant `JobPosition` | Query yes · demo JSON |
| Age pyramid | Birth `TemporalRegion` + `BiologicalSex` | Pipeline can write · aggregate in app |
| Birth registry | Birth + site + time + record + trust | Query + `register_birth` |
| Kinship / lineage | `hasMother` / `hasFather` / `updatesPriorRegistration` | Query + pipeline |
| Manager org chart | - | **Not in ontology** - do not invent |

---

## Pages (example)

| Page | Shows | Agent questions |
|---|---|---|
| **Workforce** | KPIs, roster, status mix, job-family bars, age pyramid | Who works here? Who is on leave? Headcount by job family? |
| **Hiring** | Open positions, filled vs vacant by title | What are we hiring for? Who fills “Data Engineer”? |
| **Graph** | Person → process canvas | Which Birth Registration / Employment processes link to Jeremy? |
| **Processes** | BFO 7-buckets process docs | Explain BirthProcess. EmployeeRole vs JobPosition? |
| **Logs** | Graph mutation audit by transaction, actor and target graph | Which triples were added or deleted? |

---

## Data layout

Committed app datasets (canonical for local dev and fallback):

```
apps/cockpit/data/
├── globals/entities.json
└── entities/demo/
    ├── manifest.json           # page → dataset paths (+ build metadata)
    ├── workforce/
    ├── logs/
    ├── graph/
    └── processes/
```

Production ObjectStorage keys mirror the same shape under
``personnel/apps/cockpit/`` (fs: ``storage/datastore/personnel/apps/cockpit/``).

Build pipeline:

```
data/graph/personnel_demo.ttl   ← sandbox/generate_demo_graph.py
        ↓ SPARQL export
data/entities/demo/        ← apps/cockpit/scripts/export_demo_apps_from_graph.py
```

---

## URL map

Browser paths use `url_slug`; datasets use `entity_id` (hyphens → underscores).

| URL | Page module | Data folder |
|---|---|---|
| `/demo/workforce` | `web/components/pages/workforce/` | `data/entities/demo/workforce/` |
| `/demo/graph` | `web/components/pages/graph/` | `data/entities/demo/graph/` |
| `/demo/processes` | `web/components/pages/processes/` | `data/entities/demo/processes/` |
| `/demo/logs` | `web/components/pages/logs/` | `data/entities/demo/logs/` |

Page ids and dataset paths are joined in `data/entities/<id>/manifest.json`.

---

## Layout

```
cockpit/
├── api/                 # FastAPI routes → data/
├── data/                # committed datasets (globals/, entities/)
├── paths.py             # canonical filesystem paths
├── graph_payload.py     # Graph page JSON builder
├── web/                 # static UI (fetch /api/personnel-cockpit/…)
│   ├── app/[entitySlug]/[pageId]/page.js
│   ├── components/pages/{workforce,graph,processes,logs}/
│   ├── lib/{api,config,routes,registry}.js
│   ├── js/shell.js
│   ├── index.html
│   └── css/app.css
├── AGENTS.md
└── README.md
```

Enable in `config.yaml`:

```yaml
modules:
  - module: naas_abi_marketplace.domains.personnel.apps.cockpit
    enabled: true
```
