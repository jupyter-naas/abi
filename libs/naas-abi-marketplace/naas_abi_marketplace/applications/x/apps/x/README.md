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
│       ├── app/                  # one route per page (see Deep links)
│       │   ├── layout.tsx        # mounts AppProvider, kept across pages
│       │   ├── page.tsx          # `/` — forwards to the default page
│       │   ├── posts/get-posts-counts-recent/page.tsx
│       │   ├── posts/search-posts-recent/page.tsx
│       │   ├── users/search/page.tsx
│       │   └── parameters/page.tsx
│       ├── components/           # AppProvider, AppView, Shell, UserResults,
│       │                         #   UserDetail, charts, tables
│       └── lib/                  # types, routes, loadSnapshots
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
├── posts/get-posts-counts-recent/index.html   # one page per route, each with
├── posts/search-posts-recent/index.html       #   an index.txt beside it (the
├── users/search/index.html                    #   router payload a click
├── parameters/index.html                      #   fetches — keep it published)
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
    ├── users.json          # search index: every author + bio, compact rows
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

### Deep links

Every page is a **path**, exported as its own HTML file, so a link opens on that
page directly. Only the state a path cannot carry stays in the query string
(`src/lib/routes.ts`):

| Page | Path | Params |
|---|---|---|
| Count Recent Tweets | `/posts/get-posts-counts-recent/` | `scenario`, `query` |
| Search Recent Tweets | `/posts/search-posts-recent/` | `scenario`, `query` |
| Search Users | `/users/search` | `q`, `user`, `post` |
| Parameters | `/parameters/` | — |

So `…/x/apps/x/posts/search-posts-recent/?scenario=last_7d&query=ai` opens the
Search page on that window and query, `…/x/apps/x/users/search?q=grok` opens
that search, adding `&user=grok` opens that author's page, and `&post=<tweet id>`
pins that post to the top of the author page. `scenario` is an
id from `globals/scenarios.json`, `query` a slug from `globals/queries.json`,
`user` a handle from the search index, `q` whatever was typed in the Users
search box, `post` the numeric tweet id. The Users path has **no trailing slash**
before the query string (`search?user=` not `search/?user=`).

`?token=` (the `/app-html/` access credential) is kept on every in-app link and
snapshot fetch so switching pages does not drop authorisation.

Rules the app keeps:

- Only the params a page honours are written — the Users page hides the
  Scenario / Query filters, so its URL carries neither, and its links to Posts
  leave the author behind. A shared URL never advertises state you cannot see.
- Moving between pages, and opening or closing an author, **push** history; the
  filter dropdowns and the Users search box **replace** it, so Back means
  "previous page", not "undo one dropdown" or "one keystroke". The search box
  only writes once typing pauses.
- A pasted URL is normalised in place on arrival: `?user=@grok` becomes
  `?user=grok`, and a `scenario` or `query` this publish no longer carries falls
  back to the first published one and rewrites itself. A bare page URL stays
  bare.
- `/` holds no view: it forwards to `/posts/get-posts-counts-recent/`, translating
  links minted before the pages had paths (`?page=users&user=grok`) on the way
  through. A path this publish does not carry falls back to the app root rather
  than 404-ing (`routes.py`), so old bookmarks still land somewhere useful.
- Navigation is client-side: the pages share one `AppProvider` mounted by the
  root layout, so snapshots are fetched once per session and the filters,
  timezone and sidebar survive a page change. That works because the export's
  `index.txt` payloads are published — dropping them turns every click into a
  full reload.

## Search Users

The Users page is **not** scoped by the Scenario / Query filters — those are
hidden there. It has two exclusive states, both of them URLs:

**The search** (`/users/search?q=grok`) answers with a list of results rather
than a grid of tiles — one row per author: its address, the display name as the
link with the `@handle` under it, the account bio as the snippet when it has
one, then what the graph knows about it (posts ingested, location, verification,
last post). Names and bios come from the search index itself, which is why
`users.json` carries `display_name` and `description` columns (see below)
rather than the page fetching a shard per result. Results are ranked
by how well the handle or display name answers the needle (`rankUsers`
in `lib/userSearch.ts`): exact handle, then exact name, then prefix / substring
on each, then a location match, with the busiest author first inside each band
— so searching "grok" answers with @grok, not with whichever louder account
happens to contain those letters. The box is submitted with Enter (Google
style); typing does not re-filter. An empty query lists everyone, busiest
first, **100 per page**, with a count of `N results in the X graph`. A submitted
query updates that line to `N results for “…”`. The × in the box clears the
query and returns to the full-graph listing.

**One author** (`/users/search?q=grok&user=grok`) replaces the results with
that account's page: profile metadata, KPIs of what was ingested, then the
posts as a feed (URL, date | kind, then the text and image). Clicking a post
URL pins it to the top and sets `?post=<tweet id>`. Closing it — the ✕ or *Back
to search* — drops `user` (and `post`) and lands back on the results it was opened from,
needle intact, which is why `q` rides along in the URL. A handle absent from the
published dataset renders as "not in the published X graph" rather than as an
empty page.

Result rows are real links, so ⌘/ctrl-click opens an author in a new tab while a
plain click opens it in place without a reload, and Back / Forward walk the
authors visited.

### Pinned authors

Either view can pin an author to a **Pinned** group in the second sidebar, under
*Search Users* — quick access to the accounts someone keeps coming back to,
listed where the Users section's own navigation lives (and only there). Pins live
in `localStorage` (`lib/pins.ts`), newest first, capped at `MAX_PINNED_USERS`
(12); blocked storage degrades to pins that do not survive a reload. The links
carry no needle: a pin is a jump to an author, not a search.

The whole page is one published dataset:

| Object | Holds |
|---|---|
| `search_users/users.json` | Every author (~60k) — the search index, as compact arrays: `[username, posts, last_post_at, location, verified_type, shard, description, display_name]` |
| `search_users/posts/<shard>.json` | For each author in the shard: `profile` + every post, newest first |
| `search_users/shards.json` | Per-shard content hash, author count, post count, byte size |

`description` and `display_name` are trailing columns, and `DATASET_FORMAT` is
deliberately *not* bumped for them: an older app ignores extras, a newer one
reads a missing one as empty, and a bump would force all 256 shards to be
re-queried for a change that touches none of them. Bios are capped at
`MAX_DESCRIPTION_CHARS` (160, which is X's own limit) — that cap is what bounds
their share of a ~60k-row index — and names + bios come from one pass each over
the hydrated accounts (`all_descriptions`, `all_display_names`), not from the
per-shard account query.

`DATASET_FORMAT` **is** bumped to 2 when author posts start including referenced
context (not only search matches): index counts and shard payloads both change,
so the next publish rebuilds every shard once.

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
verification/protected flags, pinned tweet id, profile image and
banner, plus the `XUserPublicMetrics` counts (followers, following, tweets,
listed, likes, media). Those render as a profile card between the KPIs and the
post table. Empty fields are **dropped** rather than published as `""`/`null`:
most authors are ingested as tweet-author stubs carrying just `author_id` and
`username`, and at 60k of them the placeholders would be a large share of the
dataset. Every field is optional on the web side as a result.

The post table nests attached media under the **Post** column (below the
text, above the tweet URL). Media are joined through `x:hasAttachedMedia`,
taking `media_url` and falling back to `preview_image_url`. Photos carry a
direct `media_url`; videos and GIFs get their highest-bitrate MP4 from the
X API `variants` field at ingest time, so the cell can embed a `<video>`
player. Image assets keep their natural aspect ratio (no square crop). A
tweet can carry several attachments, so the query groups on `?tweet` and
concatenates them into one space-separated `media_url` — grouping is also
what keeps one row per tweet despite the join. An asset that fails to load
falls back to a plain link so the media stays reachable.

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

The Search page shows four cards: **Total Posts Ingested** (matched + referenced,
delta vs the previous window, hint = coverage period), **Tweets** and
**Referenced Tweets** (each with a delta and share of posts ingested), and
**Coverage** (matched / count-endpoint total; hint is that count, no
period-over-period comparison).

`tweets_in_window` orders the full graph match by recency *before* applying that
LIMIT, so a capped read is the newest N tweets in the window — never an
arbitrary sample.

## Ingested tweets over time

The Search page line chart matches Count's **Posts over time**: per-hour (24h /
48h) or per-day (7d / 30d) **counts**, current vs previous period — not a
cumulative running total, and not the newest-1 000 table sample.

Each point is ingested **matched** tweets whose `created_at` falls in that
bucket (`ingested_timeseries`). Referenced tweets are left out (a quoted original
can be months older than the window). Count-endpoint totals are a different
population and are not used here.

Empty hours/days are kept as zero so the series lines up with the window (and
current vs previous overlay by clock hour, not by rank).

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

Against the docker stack, `config.local.yaml` points at `http://minio:9000`, so
the publisher has to run *inside* the API container — which bind-mounts the repo,
and therefore sees a `web/out/` built on the host:

```bash
cd /path/to/axi-ai
(cd .abi/libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/apps/x/web && pnpm build)
docker compose exec abi uv run --no-dev python -m \
  naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml --web-only
```

`--web-only` uploads `web/out/` and nothing else — no SPARQL, no snapshot
rebuild — which is the loop for changing the UI. Drop it to republish the data
too. Changing `routes.py` needs `docker compose restart abi`; changing the web
app does not. The app is then at
`http://localhost:9879/app-html/x/apps/x/posts/get-posts-counts-recent/`.

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
