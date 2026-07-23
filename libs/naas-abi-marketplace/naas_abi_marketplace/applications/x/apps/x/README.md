# X · Post Count Following

Nexus catalog app that follows how many X posts match a query over time. Pick a
followed query and a time range to see the total, mean, peak and lowest, plus an
hourly/daily trend chart — styled in the X (Twitter) theme.

## Layout

```
apps/x/x/
├── manifest.json   # catalog entry (url → storage-backed /app-html/ path)
├── hub.py          # SPARQL → JSON snapshots + dashboard HTML, published to object storage
├── build.py        # CLI: publish the dashboard to object storage
├── routes.py       # middleware serving index + data snapshots from object storage
├── index.html      # stub fallback when the dashboard is not published yet
└── README.md
```

Object storage layout (`x/apps/x/`):

```
x/apps/x/
├── index.html          # published dashboard (source of truth for the UI)
└── data/
    ├── catalog.json    # followed queries (dropdown 1)
    └── <slug>.json     # hourly {start,end,count} series per followed query
```

## Data flow

The hourly `XCountRecentTweetsOrchestration` runs, per configured
`count_recent_tweets_workflow` query:

1. `XCountRecentTweetsWorkflow` — fetch the newly completed clock hour(s) of
   counts (7-day backfill on the first run) and persist an envelope under
   `x/count_recent_tweets/<slug>/`.
2. `XCountRecentTweetsPipeline` — map each envelope into
   `GRAPH <http://ontology.naas.ai/graph/x_recent_posts_count>` as
   `CountRecentTweets` / `TweetCountResultSet` / `TweetCountBucket` /
   `CountInterval` individuals.
3. `XCountAppHubBuilder.publish(...)` — run the count SPARQL against that graph
   and (re)publish `index.html` + the JSON snapshots to `x/apps/x/`.

The dashboard is fully client-side: it embeds each series, filters by the
selected window (Last 24h / 48h / 7d / 30d), aggregates **hourly** for ≤48h and
**daily** for 7d/30d, and derives the KPIs (total / mean / peak / lowest) and
line chart from the filtered series.

## Serving

- Dashboard: `manifest.json` → `/app-html/x/apps/x/index.html` (object storage)
- Snapshots: `/app-html/x/apps/x/data/<file>.json`
- Stub fallback: filesystem `apps/x/x/index.html` only when storage has no
  dashboard yet

The module registers `XCountAppMiddleware` (see `routes.py`) on the ABI API via
`ABIModule.api()`, so these paths resolve before the Nexus static
`/app-html/{path}` handler. Restart the API after adding routes or the manifest.

The app id exposed by the API is `naas_abi_marketplace.applications.x:x`.

## Rebuild manually

```bash
# Publish every configured (count_recent_tweets_workflow) query:
python -m naas_abi_marketplace.applications.x.apps.x.build

# Or an ad-hoc query:
python -m naas_abi_marketplace.applications.x.apps.x.build \
  --query "(drone OR drones OR uas OR uav) lang:en -is:retweet"
```
