# Personnel Cockpit

Lightweight S1 workforce analytics example — same *registration / data / page*
shape as [Financial Cockpit](../../finance/apps/financial_cockpit), without the
Next.js surface. SPARQL-shaped JSON, static UI, FastAPI dataset layer.

```bash
cd domains/personnel && make demo-data              # regenerate web/data from ontology graph
cd domains/personnel && make app-personnel-cockpit  # API + static UI dev server
```

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
| Manager org chart | — | **Not in ontology** — do not invent |

---

## Pages (example)

| Page | Shows | Agent questions |
|---|---|---|
| **Workforce** | KPIs, roster, status mix, job-family bars, age pyramid | Who works here? Who is on leave? Headcount by job family? |
| **Hiring** | Open positions, filled vs vacant by title | What are we hiring for? Who fills “Data Engineer”? |
| **Graph** | Person → process canvas | Which Birth Registration / Employment processes link to Jeremy? |
| **Logs** | Births, kinship, trust | List birth registrations. Reconstruct Emma Petit’s lineage. |
| **Processes** | BFO 7-buckets process docs | Explain BirthRegistrationProcess. EmployeeRole vs JobPosition? |

---

## Data layout

Committed app datasets (canonical for local dev and fallback):

```
apps/cockpit/web/data/
├── globals/entities.json
└── entities/_demo/
    ├── manifest.json
    ├── entity.json
    ├── source/                 # one file per SPARQL tool
    ├── workforce/
    ├── hiring/
    ├── logs/
    ├── graph/
    └── processes/              # static BFO process docs
```

Production ObjectStorage keys mirror the same shape under
``personnel/apps/cockpit/`` (fs: ``storage/datastore/personnel/apps/cockpit/``).

Build pipeline:

```
data/graph/personnel_demo.ttl   ← generate_demo_graph.py
        ↓ SPARQL export
web/data/entities/_demo/        ← export_demo_apps_from_graph.py
```

---

## Layout

```
cockpit/
├── api/                 # FastAPI routes → web/data
├── paths.py             # canonical filesystem paths
├── graph_payload.py     # Graph page JSON builder
├── web/                 # static UI (fetch /api/personnel-cockpit/…)
│   ├── index.html
│   ├── css/app.css
│   ├── js/
│   └── data/            # committed datasets
├── AGENTS.md
└── README.md
```

Enable in `config.yaml`:

```yaml
modules:
  - module: naas_abi_marketplace.domains.personnel.apps.cockpit
    enabled: true
```
