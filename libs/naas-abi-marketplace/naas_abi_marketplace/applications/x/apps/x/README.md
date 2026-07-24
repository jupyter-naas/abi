# X · Recent Tweets

Nexus catalog app that follows an X query over time. Pick a query and a time
range to see count KPIs (total / mean / peak / lowest) and an hourly/daily trend
chart, an Excel-like table of the tweets ingested in that window, and a
per-author tweet-count ranking — styled in the X (Twitter) theme.

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
├── index.html              # published dashboard (source of truth for the UI)
└── data/
    ├── catalog.json        # followed queries (dropdown 1)
    ├── <slug>.json         # hourly {start,end,count} series per followed query
    └── <slug>_tweets.json  # tweets ingested for the query (the table below the chart)
```

## Data flow

The counts + dashboard are (re)built hourly. This happens two ways — use either
or both:

- **Standalone schedule** — `XCountRecentTweetsOrchestration` (cron `0 * * * *`)
  runs per enabled `count_recent_tweets_workflow` entry.
- **On the search tick** — a `search_recent_tweets_workflow` filter with
  `count_recent_tweets: true` also fetches counts + republishes the app right
  after it fetches tweets, so stats and result content stay in sync.

Both paths run the same steps (shared helpers in `orchestrations/utils/_common.py`):

1. `XCountRecentTweetsWorkflow` — fetch the newly completed clock hour(s) of
   counts (7-day backfill on the first run) and persist an envelope under
   `x/count_recent_tweets/<slug>/`.
2. `XCountRecentTweetsPipeline` — map each envelope into
   `GRAPH <http://ontology.naas.ai/graph/x_recent_posts_count>` as
   `CountRecentTweets` / `TweetCountResultSet` / `TweetCountBucket` /
   `CountInterval` individuals.
3. `XCountAppHubBuilder.publish(...)` — run the count + tweet SPARQL and
   (re)publish `index.html` + the JSON snapshots for **every** followed query
   (union of enabled count entries and search filters that opted in).

The dashboard is client-side. It embeds each count series (chart + KPIs render
with no fetch), and for the two tables fetches the per-query tweet snapshot on
demand. Everything reacts to the shared window dropdown (Last 24h / 48h / 7d /
30d); the chart aggregates **hourly** for ≤48h and **daily** for 7d/30d.

- **Tweets in range** — an Excel-like table of the tweets whose `created_at`
  falls in the window: columns **Date**, **Text** (full text, then the permalink
  on a new line), **Author** (`@handle` → profile), **Location**, **Verified**.
  Supports a global search, per-column filters, column show/hide checkboxes,
  click-to-sort headers and 50-row pagination.
- **Top authors** — authors ranked by tweet count in the window (rank, author,
  location, verified, tweet count), same table controls.

Tweet content is read from the tweet-content graph (`…/graph/x`, populated by
`XSearchRecentTweetsPipeline`) via SPARQL and saved per query as
`data/<slug>_tweets.json`. The tables need the matching search filter ingesting
tweets for the query; the count chart works independently.

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
