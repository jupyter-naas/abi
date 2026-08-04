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
│   ├── tables.json
│   └── facets.json         # column-filter value lists, whole window
└── search_users/
    ├── users.json          # picker index: every author, compact rows
    ├── shards.json         # shard manifest (content hashes + counts)
    └── posts/<shard>.json  # profile + every post, per shard of authors
```

## Everything is served from object storage

The app runs **no SPARQL at request time**. `routes.py` mounts middleware that
answers `/app-html/x/apps/x/…` purely out of the published objects above, so the
API process needs no triple store and a page load is a handful of GETs. The
publisher is the only thing that touches the graph, and the ingestion
orchestrations run it after every pipeline run (see *Rebuild snapshots*).

The trade-off is that a page can only be as fresh, and as complete, as its last
publish — most visibly on the Search page, whose tweet table is the newest
`DEFAULT_TWEET_LIMIT` (1 000) rows per query + window. Column filters narrow
those rows in the browser; the *option lists* behind the checkboxes come from
`facets.json`, which is aggregated over the whole window at publish time, so
ticking a username still offers every author in the window.

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
selecting one lists *all* their posts, newest first, paged 100 at a time.

The whole page is one published dataset:

| Object | Holds |
|---|---|
| `search_users/users.json` | Every author (~60k), as compact arrays: `[username, posts, last_post_at, location, verified_type, shard]` |
| `search_users/posts/<shard>.json` | For each author in the shard: `profile` + every post, newest first |
| `search_users/shards.json` | Per-shard content hash, author count, post count, byte size |

Authors are grouped into 256 shards by `sha1(username)` (`user_shard`), so
selecting an author downloads one file of a few hundred KB instead of the whole
~110 MB dataset, and paging by 100 is a slice of an array already in memory. The
index carries each author's `shard` so the browser never has to hash anything —
`crypto.subtle` is undefined on a page served over plain http from a
non-localhost host, which would otherwise break the page in exactly the
deployments that need it.

Counts (`posts`, `last_post_at`, `first_post_at`) are SPARQL aggregates over the
whole graph, so the KPIs describe the author rather than the page on screen.
Posts are sorted newest-first with `url` as the tie-breaker, so authors who post
several times in the same second keep a stable order.

Each author's `profile` is the tweet aggregates merged with their `XUser`
individual — display name, bio, location, URL, join date,
verification/protected flags, pinned + most-recent tweet ids, profile image and
banner, plus the `XUserPublicMetrics` counts (followers, following, tweets,
listed, likes, media). Those render as a profile card between the KPIs and the
post table. Empty fields are **dropped** rather than published as `""`/`null`:
most authors are ingested as tweet-author stubs carrying just `author_id` and
`username`, and at 60k of them the placeholders would be a large share of the
dataset. Every field is optional on the web side as a result.

The post table shows **Media** instead of the author location: attached media
are joined through `x:hasAttachedMedia`, taking `media_url` and falling back to
`preview_image_url` (videos and GIFs only ever have the preview). A tweet can
carry several, so the query groups on `?tweet` and concatenates them into one
space-separated `media_url` — grouping is also what keeps one row per tweet
despite the join. The cell renders the assets as thumbnails (up to four, then
`+N`), each linking to the full image; a thumbnail that fails to load falls
back to a plain link so the media stays reachable.

### Incremental republish

The ingestion orchestrations rebuild this dataset after **every** pipeline run,
so writing 256 shards each time would be wasteful. Each shard is serialized
once, hashed, and compared against `shards.json` from the previous publish;
identical shards are not re-uploaded. A typical tick touches a handful of
authors, so it writes a handful of shards. The graph reads still happen in full
(~60 s at 110k posts) — only the uploads are skipped.

Reads are batched: `posts_for_usernames` / `accounts_for_usernames` bind
`AUTHOR_BATCH_SIZE` (2 000) usernames per query with `VALUES`, so peak memory is
a function of the batch rather than of the graph. A single unbounded dump of
110k posts parses into hundreds of MB of rdflib terms, which is not something to
do on every ingest tick.

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

## Column filters

The Search page's **Tweets fetched** table filters per column, Excel-style: a
dropdown on each header with a search box, plus checkboxes of distinct values on
the faceted columns (`username`, `location`, `verified_type`).

Filtering itself runs in the browser over the rows the snapshot carries. The
checkbox **options** do not: `search_recents_tweets/facets.json` publishes, per
query × scenario × faceted column, the distinct values and counts aggregated
over the whole window (capped at `MAX_FACET_VALUES`, 500, most frequent first).
So the values on offer are the window's, even though the rows being narrowed are
the newest 1 000. When a publish predates `facets.json`, the options fall back
to the distinct values of the loaded rows.

`filters` is `{column: {contains, values}}` — substring OR exact set, OR within
a column, AND across columns.

This replaced two live SPARQL routes (`api/tweets`, `api/tweets/values`); see
`docs/adr/20260728_x_app_live_tweet_search.md` for the design that preceded it.

### Serving is middleware, not routes

`XCountAppMiddleware` answers `/app-html/x/apps/x/…` **before the router**.
Nexus registers a `/app-html/{path:path}` static catch-all ahead of this
module's routes, so anything left to normal routing is answered with
`{"detail": "App HTML not found: …"}` before it reaches us. Middleware is the
only ordering that holds — worth remembering if a newly published path ever
needs serving: add it to `_SNAPSHOT_RE` (which allows one optional nested
directory, for `search_users/posts/<shard>.json`) rather than to a route table.

## Rebuild snapshots

```bash
# Uses config.local.yaml when present in the CWD:
cd /path/to/axi-ai
# Ensure web export exists first (pnpm build in apps/x/web)
uv run python -m naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml
```

Orchestrations call `publish_x_app()` → `XAppHubBuilder.publish()` which
delegates to `api.publish.publish_app`.

### Rebuilt after a pipeline run — opt-in

The app serves published objects and queries nothing itself, so a republish is
the *only* thing that moves the dashboard forward. Both orchestrations that run
`XSearchRecentTweetsPipeline` can do that republish on the same tick they change
the graph, via `republish_x_app_after_pipeline()`:

| Orchestration | When (with `app_publish: true`) |
|---|---|
| `XSearchRecentTweetsEventOrchestration` | After each envelope is mapped (one per `ObjectPut`) |
| `XSearchRecentTweetsFilesOrchestration` | Once after a sweep, when at least one envelope was reprocessed |

**`app_publish` defaults to `false`** on both config entries, so ingestion does
not rebuild the app unless you ask it to. A rebuild reads the whole graph
(~60 s at 110 k posts) regardless of how little changed, and the hourly
`x_build_app` schedule already republishes from the same graph state — so the
dashboard is at most an hour behind with this off. Turn it on per entry when the
dashboard must follow ingestion, or per run from the launchpad:

```yaml
ops:
  x_search_recent_tweets_files_op_reprocess_envelopes:
    config:
      app_publish: true
```

The files sweep publishes once rather than per file — it can map hundreds of
envelopes in a run, and the dataset is rebuilt from the final graph state
anyway. The event sensor publishes per envelope, which is why leaving it off is
the sane default there.

The helper never raises: a failed publish is logged and reported in the op's
summary (`{"failed": true, "error": …}`), because ingestion is what the run is
for and must not be undone by a storage hiccup. Shard hashing (above) is what
keeps an enabled republish cheap — a no-change rebuild uploads nothing.

### Web assets vs. snapshots in production

`web/out/` is a gitignored build artifact and the deployment image ships no
Node/pnpm, so a production checkout never has one. The two publish paths differ in
what they demand:

`.deploy/docker/images/Dockerfile` therefore builds it in a `node:20-slim`
stage (`x-web-builder`) and copies the result to **`/opt/x-app-web/out`**,
exposed as `X_APP_WEB_EXPORT_DIR`. It must live outside `/app`, because compose
bind-mounts the repo there at runtime and would hide a baked copy underneath.

`resolve_export_dir()` searches, most specific first:

1. `X_APP_WEB_EXPORT_DIR` (explicit override)
2. `web/out/` in the repo — a developer's fresh `pnpm build` wins locally
3. `/opt/x-app-web/out` — the image-baked export used in production

If none exists, the two callers differ:

| Caller | `require_web` | No export anywhere |
|---|---|---|
| `build.py` CLI | `True` | Raises — you were meant to `pnpm build` first |
| `XAppHubBuilder.publish()` (orchestration) | `False` | Logs a warning, publishes the JSON snapshots, leaves the already-uploaded web assets untouched |

So production ships UI by **rebuilding the image**; the scheduled run then
publishes those assets along with the snapshots. Publishing from a dev host
still works too:

```bash
cd applications/x/apps/x/web && pnpm install && pnpm build
cd /path/to/axi-ai
uv run python -m naas_abi_marketplace.applications.x.apps.x.build --config config.remote.yaml
```

Changes to `routes.py` / `api/` additionally need the ABI service restarted:
route registration happens at startup, so a running process keeps serving the
code it imported.
