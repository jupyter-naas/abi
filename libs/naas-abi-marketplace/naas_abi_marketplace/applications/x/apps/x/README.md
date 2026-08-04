# X · Recent Tweets

Nexus catalog app that follows an X query over time. Pick a query and a scenario
(time window) to see count KPIs + trend, ingested-tweet KPIs (capped at 2 000),
author/location bars, and Excel-like tables — styled in the X (Twitter) theme.
Ingested-tweet **KPI counts are uncapped**; tweet tables/bars still sample at
most 2 000 rows.

## Layout (`api` / `web` — same split as Nexus `apps/api` + `apps/web`)

```
apps/x/
├── api/                          # Python snapshot publishers (SPARQL → JSON)
│   ├── common.py
│   ├── publish.py
│   ├── globals/
│   ├── count_recent_tweets/
│   ├── search_recents_tweets/
│   └── search_users/
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
├── search_recents_tweets/
│   ├── kpis.json
│   ├── barcharts.json
│   ├── linecharts.json
│   └── tables.json
└── search_users/
    └── users.json
```

## Navigation

The sidebar holds **sections**; a second bar lists the active section's
subpages:

| Section | Subpages |
|---|---|
| Posts | Count Recent Tweets · Search Recent Tweets |
| Users | Search Users |
| Parameters | — (no second bar) |

## Search Users

The Users page is **not** scoped by the Scenario / Query filters — those are
hidden there. Searching an author reaches every author in the tweet graph, and
selecting one lists *all* their posts, newest first, paged 100 at a time:

| Route | Returns |
|---|---|
| `GET /app-html/x/apps/x/api/users?contains=` | Authors matching a username substring, with all-time post counts |
| `GET /app-html/x/apps/x/api/users/posts?username=&limit=&offset=` | One page of an author's posts + graph totals |

Counts (`posts`, `last_post_at`, `first_post_at`) are SPARQL aggregates over the
whole graph, so the KPIs describe the author rather than the page on screen.
Paging uses `LIMIT`/`OFFSET` with `?url` as the ORDER BY tie-breaker, so pages
stay stable when tweets share a timestamp.

`search_users/users.json` publishes the busiest `DEFAULT_USER_LIMIT` (2 000)
authors as the offline fallback for the picker; with a backend the page always
searches the graph live instead.

## Scenarios

Each Scenario filter value has:

| Field | Meaning |
|---|---|
| `id` | `24h` / `48h` / `7d` / `30d` |
| `label` | Human label |
| `start_time` | ISO window start (UTC, computed at publish, floored to the hour) |
| `end_time` | ISO window end (UTC, computed at publish, floored to the hour) |

Both edges are floored to the clock hour. `aggregate_buckets` keeps a count
bucket only when its `start` falls inside the window, so an unaligned window
dropped the partially-overlapped first bucket whole — a publish at 13:02 lost
the entire 13:00–14:00 hour from the line chart. Flooring also makes a window
reproducible across publishes in the same hour. The in-progress hour is
excluded, which matches the count workflow (it only ingests complete hours).

## Tweets ingested KPI (uncapped)

`search_recents_tweets/kpis.py` runs **one SPARQL count query** parameterized by
`start_time` / `end_time` with no row cap. That query is executed **once per
scenario** (4× for the default Scenario filter) per followed query. Tweet
tables and author/location bars still use `DEFAULT_TWEET_LIMIT` (1 000).

`tweets_in_window` orders the full graph match by recency *before* applying that
LIMIT, so a capped read is the newest N tweets in the window — never an
arbitrary sample.

## Column filters (live graph search)

The Search page's **Tweets fetched** table filters per column, Excel-style: a
dropdown on each header with a search box, plus checkboxes of distinct values on
the faceted columns (`username`, `location`, `verified_type`).

Filters are **not** applied to the published snapshot — they are pushed into
SPARQL through two read-only routes, so a keyword search returns the newest
1 000 tweets that *match* rather than the matches inside the newest 1 000
tweets overall:

| Route | Returns |
|---|---|
| `GET /app-html/x/apps/x/api/tweets` | Rows for `query` + window + `filters` |
| `GET /app-html/x/apps/x/api/tweets/values` | Distinct values + counts for one column |

`filters` is JSON: `{column: {contains, values}}` — substring OR exact set,
OR within a column, AND across columns. Unknown columns are dropped by
`normalize_tweet_filters` before any SPARQL is built.

Both routes need `triple_store`, passed to `register_x_count_app_routes`. When
it is absent (or a request fails) the table falls back to filtering the rows
already loaded from the snapshot, so a static copy of `out/` still works.
See `docs/adr/20260728_x_app_live_tweet_search.md`.

## Rebuild snapshots

```bash
# Uses config.local.yaml when present in the CWD:
cd /path/to/axi-ai
# Ensure web export exists first (pnpm build in apps/x/web)
uv run python -m naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml
```

Orchestrations call `publish_x_app()` → `XAppHubBuilder.publish()` which
delegates to `api.publish.publish_app`.
