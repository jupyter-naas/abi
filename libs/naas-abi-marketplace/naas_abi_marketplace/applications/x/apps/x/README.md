# X · Recent Tweets

Nexus catalog app that follows an X query over time. Pick a query and a scenario
(time window) to see count KPIs + trend, ingested-tweet KPIs (capped at 2 000),
author/location bars, and Excel-like tables — styled in the X (Twitter) theme.

## Layout (`api` / `web` — same split as Nexus `apps/api` + `apps/web`)

```
apps/x/
├── api/                          # Python snapshot publishers (SPARQL → JSON)
│   ├── common.py
│   ├── publish.py
│   ├── globals/
│   ├── count_recent_tweets/
│   └── search_recents_tweets/
├── web/                          # Next.js App Router (static export)
│   ├── package.json
│   ├── next.config.js            # output: 'export', basePath: /app-html/x/apps/x
│   ├── publish_assets.py         # uploads web/out/… into object storage
│   └── src/
│       ├── app/{layout,page}.tsx
│       ├── components/           # Shell, Filters, KpiGrid, charts, tables
│       └── lib/                  # types + loadSnapshots
├── hub.py                        # thin facade (orchestrations / tests)
├── build.py                      # CLI publisher
├── routes.py                     # /app-html/x/apps/x/… middleware
├── manifest.json
└── index.html                    # stub when not yet published
```

Object storage layout (`x/apps/x/`):

```
x/apps/x/
├── index.html
├── _next/static/…          # Next.js hashed assets
├── globals/
│   ├── scenarios.json
│   ├── queries.json
│   └── timezone.json
├── count_recent_tweets/
│   ├── kpis.json
│   ├── barcharts.json
│   └── linecharts.json
└── search_recents_tweets/
    ├── kpis.json
    ├── barcharts.json
    ├── linecharts.json
    └── tables.json
```

Both pages expose the same element names (`kpis`, `barcharts`, `linecharts`);
only `tables` (and column labels) are page-specific.

## Web (Next.js)

```bash
cd .abi/libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/apps/x/web
pnpm install
pnpm build          # writes out/ (asset URLs use /app-html/x/apps/x/)
pnpm dev            # http://localhost:3045/app-html/x/apps/x/
```

`publish_app` uploads the static export from `web/out/`
alongside the JSON snapshots. Rebuild the web app whenever UI code changes.

## Scenarios

Each Scenario filter value has:

| Field | Meaning |
|---|---|
| `id` | `24h` / `48h` / `7d` / `30d` |
| `label` | Human label |
| `start_time` | ISO window start (UTC, computed at publish) |
| `end_time` | ISO window end (UTC, computed at publish) |

## Tweets ingested KPI (≤ 2 000)

`search_recents_tweets/kpis.py` runs **one SPARQL count query** parameterized by
`start_time` / `end_time`, with an inner `LIMIT 2000`. That query is executed
**once per scenario** (4× for the default Scenario filter) per followed query.

## Rebuild snapshots

```bash
# Uses config.local.yaml when present in the CWD:
cd /path/to/axi-ai
# Ensure web export exists first (pnpm build in apps/x/web)
uv run python -m naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml
```

Orchestrations call `publish_x_app()` → `XAppHubBuilder.publish()` which
delegates to `api.publish.publish_app`.
