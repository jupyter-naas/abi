# X · Recent Tweets

Nexus catalog app that follows an X query over time. Pick a query and a scenario
(time window) to see count KPIs + trend, ingested-tweet KPIs (capped at 2 000),
author/location bars, and Excel-like tables — styled in the X (Twitter) theme.

## Layout (`api` / `web` — same split as Nexus `apps/api` + `apps/web`)

```
apps/x/
├── api/
│   ├── common.py                 # scenarios + SPARQL helpers + storage I/O
│   ├── publish.py                # orchestrates every page/element script
│   ├── globals/
│   │   ├── scenarios.py          # → globals/scenarios.json
│   │   ├── queries.py            # → globals/queries.json
│   │   └── timezone.py           # → globals/timezone.json
│   ├── count_recent_tweets/
│   │   ├── kpis.py               # → count_recent_tweets/kpis.json
│   │   ├── barcharts.py          # → count_recent_tweets/barcharts.json
│   │   └── linecharts.py         # → count_recent_tweets/linecharts.json
│   └── search_recents_tweets/
│       ├── kpis.py               # → search_recents_tweets/kpis.json (tweets_ingested ≤ 2000)
│       ├── barcharts.py
│       ├── linecharts.py
│       └── tables.py             # page-specific (column names differ)
├── web/
│   └── dashboard.py              # HTML that loads the JSON snapshots
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
├── globals/
│   ├── scenarios.json    # [{id, label, start_time, end_time}, …] × 4
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

## Rebuild

```bash
# Uses config.local.yaml when present in the CWD:
cd /path/to/axi-ai
uv run python -m naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml

# Or an ad-hoc query:
uv run python -m naas_abi_marketplace.applications.x.apps.x.build \
  --config config.local.yaml \
  --query '(drone OR drones OR UAS OR UAV) lang:en -is:retweet'
```

The hourly count orchestration and search ticks with `count_recent_tweets: true`
still call `publish_x_app()` → `XAppHubBuilder.publish()` which now
delegates to the same `api.publish` publisher.
