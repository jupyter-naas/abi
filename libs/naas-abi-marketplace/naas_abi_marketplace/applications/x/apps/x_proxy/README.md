# X Proxy

Nexus catalog app that follows an X query over time. Pick a query and a scenario
(time window) to see count KPIs + trend, ingested-tweet KPIs (capped at 2 000),
author/location bars, and Excel-like tables - styled in the X (Twitter) theme.
Ingested-tweet **KPI counts are uncapped**; tweet tables/bars still sample at
most 2 000 rows.

## Layout (`api` / `web` - same split as Nexus `apps/api` + `apps/web`)

```
apps/x_proxy/
├── config.yaml                   # sections / pages / visibility (see Navigation)
├── app_config.py                 # loads it, compiles it into the web app
├── api/                          # Python snapshot publishers (SPARQL → JSON)
│   ├── common.py
│   ├── publish.py
│   ├── globals/
│   ├── count_recent_tweets/
│   ├── search_recents_tweets/
│   └── search_users/
├── web/                          # Next.js App Router (static export)
│   ├── package.json
│   ├── next.config.js            # output: 'export', basePath: /app-html/x/apps/x_proxy
│   ├── publish_assets.py         # uploads web/out/… into object storage
│   └── src/
│       ├── app/                  # one route per page (see Deep links)
│       │   ├── layout.tsx        # mounts AppProvider, kept across pages;
│       │   │                     #   titles are "X Proxy | <page>"
│       │   ├── page.tsx          # `/` - forwards to the default page
│       │   ├── posts/get-posts-counts-recent/{layout,page}.tsx
│       │   ├── posts/search-posts-recent/{layout,page}.tsx
│       │   ├── users/search/{layout,page}.tsx
│       │   └── parameters/{layout,page}.tsx
│       ├── components/           # AppProvider, AppView, Shell, FavoritesBar,
│       │                         #   UserResults, UserDetail, MediaCarousel,
│       │                         #   charts, tables
│       └── lib/                  # appConfig(.generated), types, routes,
│                                 #   loadSnapshots, userSearch
├── hub.py                        # thin facade (orchestrations / tests)
├── build.py                      # CLI publisher
├── routes.py                     # /app-html/x/apps/x_proxy/… middleware
├── manifest.json
└── index.html                    # stub when not yet published
```

Object storage layout (`x/apps/x_proxy/`):

```
x/apps/x_proxy/
├── index.html
├── posts/get-posts-counts-recent/index.html   # one page per route, each with
├── posts/search-posts-recent/index.html       #   an index.txt beside it (the
├── users/search/index.html                    #   router payload a click
├── parameters/index.html                      #   fetches - keep it published)
├── _next/static/…          # Next.js hashed assets
├── globals/
│   ├── scenarios.json
│   ├── queries.json
│   ├── timezone.json
│   └── graph.json          # how many posts the graph holds (matched / context)
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
answers `/app-html/x/apps/x_proxy/…` purely out of the published objects above, so the
API process needs no triple store and a page load is a handful of GETs. The
publisher is the only thing that touches the graph, and the ingestion
orchestrations run it after every pipeline run (see *Rebuild snapshots*).

The trade-off is that a page can only be as fresh, and as complete, as its last
publish - most visibly on the Search page, whose tweet table is the newest
`DEFAULT_TWEET_LIMIT` (1 000) rows per query + window. Column filters narrow
those rows in the browser; the *option lists* behind the checkboxes come from
`facets.json`, which is aggregated over the whole window at publish time, so
ticking a username still offers every author in the window.

## Navigation

All of it comes from **`config.yaml`** at the app root - see *Configuration*
below. The chrome is shaped like a browser window: the rail on the left holds
**sections**; the header stacks the app and section name, then that section's
pages as **tabs**, then - on Users - the **favorites bar**:

```
┌────────┬──────────────────────────────────────────────┐
│        │ X Proxy - Users                              │  top bar
│        ├──────────────────────────────────────────────┤
│ Posts  │ ⟨Search Users⟩                               │  tabs
│        ├──────────────────────────────────────────────┤
│ Users  │ @grok  ▸ AI labs 3  @xai       ⊞ New folder  │  favorites (Users only)
│        │                                              │
│        │ page                                         │
│        │                                              │
│ Snap…  │                                              │  publish stamp
├────────┤                                              │
│ Params │                                              │
└────────┴──────────────────────────────────────────────┘
```

| Section | Title | Tabs |
|---|---|---|
| Posts | `X Proxy - Posts` | Search Tweets · Search Recent Tweets · Count Recent Tweets |
| Users | `X Proxy - Users` | Search Users |
| Parameters | `X Proxy - Parameters` | Parameters |

Order is config order - the rail, and the tabs inside a section. A section link
goes to the page **last visited** in it, so coming back to Posts lands where it
was left; before any visit it goes to that section's first visible page. Every
section has at least one tab, so the strip never disappears under the title.

The **publish stamp** (`Snapshot · <date> UTC`) sits at the foot of the rail,
above the rule that separates Parameters - it describes the whole app, not one
page, and it is the thing to read when a number looks stale. It is hidden when
the rail is collapsed, and on phones where the rail is a row.

The **favorites bar** shows where `favorites: true` says so - today Users alone,
its chips being jumps into that section. The whole header is sticky: switching
tab or favorite never means scrolling back up first.

Under 760px the rail lies down as a horizontal, scrollable strip above the
header, and the page takes the full width. Only the header stays sticky there -
the rail on top of it would leave nothing to read - and Parameters keeps its
gear without its label, which is what makes the three sections fit a 390px
phone. Collapsing the rail is a desktop affordance and has no effect at that
width. Tabs and the favorites bar already scroll sideways, so they only lose
padding; the *New folder* button keeps its icon and drops its label.

### Configuration

`config.yaml` at the app root is the single source of truth for the navigation:
sections, their pages, the order of both, what is visible, which section shows a
title bar or the favorites bar, plus the favorites caps and the feed's batch
size. All of it used to be hardcoded in `Shell.tsx` and `lib/`.

The web app is a **static export**, so nothing fetches the YAML at runtime:
`app_config.py` compiles it into `web/src/lib/appConfig.generated.ts`, which the
components import through `lib/appConfig.ts` (the lookups - `tabsOf`,
`railSections`, `titleOf`, `PAGE_PATHS`). `pnpm build`, `pnpm dev` and
`pnpm typecheck` all regenerate it first, so editing the YAML and rebuilding is
the whole loop.

```bash
uv run python -m …x.apps.x_proxy.app_config           # print what it says
uv run python -m …x.apps.x_proxy.app_config --write   # regenerate the module
uv run python -m …x.apps.x_proxy.app_config --check   # CI: fail if it is stale
```

`charts:` is the one block the **publisher** reads rather than the browser - the
bar counts of the published charts (*Top authors* carries 20) - so a change there
needs a snapshot rebuild, not just a web publish. It is deliberately left out of
the generated TypeScript.

Per section: `label`, `icon` (`posts` | `users` | `gear`, drawn in `Shell.tsx`),
`visible`, `place` (`main` rail group or `bottom`, under the rule), `top_nav`
(false hides the "X Proxy - <section>" bar, for a section whose page carries its
own heading) and `favorites`. Per page: `label`, `path`, `visible`, `filters`
(whether the Scenario / Query dropdowns show), `search_box` (whether it has a
search box, whose needle lives in `?q=`) and `favorites`, which overrides the
the section's bar for that page alone, and `tab`, which names the tab to light
up while a page that is not itself a tab is open. `favorites` is a **scope**,
not a flag: `users`, `posts` or `none`.

Hiding is **chrome only**: a hidden section keeps its pages, a hidden page keeps
its route, and both stay reachable by URL - the export publishes every
configured route either way.

Keys and paths are the code boundary, not free text: page keys are the union
`PageKey` the components switch on, and paths are real directories under
`web/src/app/`. `app_config.py` rejects a duplicate key, an unknown icon or
place, a relative path, a non-boolean flag, a `default_page` that is unknown or
hidden, and a `title` naming a placeholder other than `{app}` / `{section}`;
`app_config_test.py` also asserts every configured path has a `page.tsx`.

### Deep links

Every page is a **path**, exported as its own HTML file, so a link opens on that
page directly. Only the state a path cannot carry stays in the query string
(`src/lib/routes.ts`):

| Page | Path | Params |
|---|---|---|
| Search Tweets | `/posts/search-tweets/` | `q` |
| Search Recent Tweets | `/posts/search-posts-recent/` | `scenario`, `query` |
| One post | `/posts/post/` | `post` (**required**), `user`, `from`, `expand` |
| Count Recent Tweets | `/posts/get-posts-counts-recent/` | `scenario`, `query` |
| Search Users | `/users/search` | `q`, `user`, `expand` |
| Parameters | `/parameters/` | - |

So `…/x/apps/x_proxy/posts/search-posts-recent/?scenario=last_7d&query=ai` opens the
Search page on that window and query, `…/x/apps/x_proxy/users/search?q=grok` opens
that search, adding `&user=grok` opens that author's page, and `&post=<tweet id>`
scrolls that post to the top of the author page (showing the page of the feed
that holds it). `scenario` is an
id from `globals/scenarios.json`, `query` a slug from `globals/queries.json`,
`user` a handle from the search index, `q` whatever was typed in the Users
search box, `post` the numeric tweet id. The Users path has **no trailing slash**
before the query string (`search?user=` not `search/?user=`).

`?token=` (the `/app-html/` access credential) is kept on every in-app link and
snapshot fetch so switching pages does not drop authorisation.

Rules the app keeps:

- Only the params a page honours are written, and which those are is
  configured: `filters: true` puts `scenario` + `query` in the URL,
  `search_box: true` puts `q` there. The Users and Search Tweets pages hide the
  Scenario / Query filters, so their URLs carry neither, and Users' links to
  Posts leave the author behind. A shared URL never advertises state you cannot see.
- Moving between pages, and opening or closing an author, **push** history; the
  filter dropdowns and the Users search box **replace** it, so Back means
  "previous page", not "undo one dropdown" or "one keystroke". The search box
  only writes once typing pauses.
- A pasted URL is normalised in place on arrival: `?user=@grok` becomes
  `?user=grok`, and a `scenario` or `query` this publish no longer carries falls
  back to the first published one and rewrites itself. A bare page URL stays
  bare.
- `/` holds no view: it forwards to `default_page` - `/posts/search-tweets/`,
  the first tab of the first section - translating
  links minted before the pages had paths (`?page=users&user=grok`) on the way
  through. A path this publish does not carry falls back to the app root rather
  than 404-ing (`routes.py`), so old bookmarks still land somewhere useful.
- Navigation is client-side: the pages share one `AppProvider` mounted by the
  root layout, so snapshots are fetched once per session and the filters,
  timezone and sidebar survive a page change. That works because the export's
  `index.txt` payloads are published - dropping them turns every click into a
  full reload.

## Search Users

The Users page is **not** scoped by the Scenario / Query filters - those are
hidden there. It has two exclusive states, both of them URLs:

**The search** (`/users/search?q=grok`) answers with a list of results rather
than a grid of tiles - one row per author: its address, the display name as the
link with the `@handle` under it, the account bio as the snippet when it has
one, then what the graph knows about it (posts ingested, location, verification,
last post). Names and bios come from the search index itself, which is why
`users.json` carries `display_name` and `description` columns (see below)
rather than the page fetching a shard per result. Results are ranked
by how well the handle or display name answers the needle (`rankUsers`
in `lib/userSearch.ts`): exact handle, then exact name, then prefix / substring
on each, then a location match, with the busiest author first inside each band
- so searching "grok" answers with @grok, not with whichever louder account
happens to contain those letters. The box is submitted with Enter (Google
style); typing does not re-filter. An empty query lists everyone, busiest
first, **100 per page** (`USER_RESULTS_PAGE_SIZE`), with a count of
`N results in the X graph`. A submitted
query updates that line to `N results for “…”`. The × in the box clears the
query and returns to the full-graph listing.

**One author** (`/users/search?q=grok&user=grok`) replaces the results with
that account's page: profile metadata, KPIs of what was ingested, then the posts
as a feed. Closing the author - the ✕ or *Back to search* - drops `user` (and
`post`) and lands back on the results it was opened from, needle intact, which
is why `q` rides along in the URL. A handle absent from the published dataset
renders as "not in the published X graph" rather than as an empty page.

### The feed

Each card is three rows: **the date and the kind** first, so the feed reads as a
timeline; then the post's URL; then its text and media.

A **matched** card also names the followed query that pulled the post in
(`Matched Query · AI`), read from the `queries` slugs the shard now carries and
worded the way the Query filter words them. A post answering two followed
queries names both.

Over the feed sit three tabs, labelled with their counts - the same split the
*Posts retrieved* KPI names. The words are `feed.tabs` in `config.yaml`; the
keys are the split the data carries:

| Tab | Holds |
|---|---|
| All | everything ingested from this author |
| Matched Query | the posts that answered a followed query - the card says which |
| Referenced | reply parents, quoted tweets and retweeted originals, ingested only to explain a match |

*Referenced* replaced *Context* as the tab's name: it is the word the ontology
uses (`x:ReferencedTweet`, `x:isReferencedByTweet`) and it says what happened to
the post rather than what it is for. Rewording it again is a config edit.

The feed opens with `feed.batch` posts (**10**, from `config.yaml`) and grows by
another batch whenever its end comes into view - an `IntersectionObserver` with
300px of lead, so the next batch is there before the reader is - or when *Show
more* is pressed. The whole shard is already in memory, so a batch is a slice,
not a fetch; the count under the button says `N of M shown`, and the end of a
grown feed says so. Switching tab starts again at the first batch.

A post is not a state of this page - it is a **page of its own**, `/posts/post/`
(below). Any card's ⤢, its URL or its text is a link there, so ⌘-click opens a
post in its own tab and the address is shareable as it stands. It is a URL, so it is shareable and Back / Forward walk in and out of
posts; a deep link naming a post further down than the feed has grown makes sure
that much of the feed is rendered before returning to it.

Result rows are real links, so ⌘/ctrl-click opens an author in a new tab while a
plain click opens it in place without a reload, and Back / Forward walk the
authors visited. A paged listing says which page it is on (`· page 2/3`) and
paging returns to the top. Pinning is **not** on a result row - it is on the
author's own page, and on a post's page, where the favorites bar is.

## Search Tweets

`/posts/search-tweets/?q=…` searches **every post the publish carries**. Like
Search Users it is *not* scoped by the Scenario / Query filters - those are
hidden there - so its corpus is the whole of `tables.json`, not one window; it
is what replaced the *Tweets fetched* table on Search Recent Tweets.

A post published under two followed queries, or falling inside two scenario
windows, is a row in each of those tables. `tweetHits` keys hits by tweet id,
unions the query slugs onto one hit, and sorts the merged list **newest first** -
per-table publish order cannot be trusted once several are merged.

It is built like Search Users: a rounded box submitted with Enter, a count line,
then one result per post -

```
x.com › grok › status/9000                     ← address; the handle opens their feed
@grok · Aug 25, 2026, 10:15 AM · AI · 9000     ← title: who, when, which query, which post
Grok says: a truth-seeking post about the …    ← the post's own text, as the snippet
Referenced · Paris · 2 media                   ← what is left over
```

- where the title is the link to the post's page. `results.per_page` (**100**)
sets the page size, the same number Search Users lists, and `rankTweets` in
`lib/tweetSearch.ts` ranks hits by *how* they answered the needle: the author's
handle exactly, then by prefix, then a word of the text starting with it, then
either containing it, then the author's location - newest first inside each
band. An empty needle lists everything, newest first.

Unsearched, the count line quotes the **graph**, not this publish:
`128,340 posts in the X graph`, from `globals/graph.json` (below). A search
replaces it with `N results for “…”`, and either way a paged listing says which
page it is on (`· page 2/3`). Paging returns to the top of the list - the pager
is at the bottom, so page 2 would otherwise open halfway down itself.

### How many posts there are

`globals/graph.json` carries the size of the dataset behind every page -
`posts`, split into `matched` and `referenced` - counted once per publish over
**distinct tweet ids**, so a post carried by two queries or two windows counts
once. It comes from the Parquet projection when there is one (a column scan) and
from two `COUNT(DISTINCT ?tweet)` SPARQL queries otherwise. A publish older than
the file leaves the count line falling back to the rows it can count itself.

## One post

`/posts/post/?post=<tweet id>` is a post's address. **The tweet id is required
and enough**; `?user=<handle>` is optional and only ever a shortcut:

| URL | How the post is found |
|---|---|
| `?post=9000` | among the published rows (`tables.json`, already in memory), which also names the author |
| `?post=9000&user=grok` | straight from that author's shard - one file, and the whole post (full text, every media) |
| `?post=<outside every window>` | needs `&user=`: the tables do not carry it, the author's shard does |

An id that resolves to nothing says so, and points at `&user=` as the way to
open it anyway. The card is the feed's card, expanded: full width, larger text,
media uncropped, its URL a plain link to x.com.

Two more params ride along:

- **`from=`** - which page opened this one, so *back* is exact: `tweets` returns
  to the search that found the post (with `q=`, so the results come back as they
  were), `users` returns to the author's feed. Whichever back does not lead to
  is still on the page as a link of its own.
- **`expand=1`** - the post and nothing else: no rail, no tabs, no title bar.
  The ⤢ in the header toggles it and the URL carries it, so a full view can be
  linked to directly. `AppView` returns the page without mounting `Shell` at
  all rather than hiding it with CSS. An author's page takes the same flag
  (`/users/search?user=grok&expand=1`); a *listing* ignores it, having nothing
  to expand.

The header **pins the post** - to the `posts` bar this page carries, never to
the authors pinned on Users, which is why it sets `favorites: posts` for itself
though the rest of Posts carries no bar. It also keeps the *Search Tweets* tab
lit (`tab: tweets`), the way an author's page keeps *Search Users* lit.
↗ *On X* is the way out.

It is a hidden page (`visible: false`) - a destination reached from a result or
a feed, not a tab - which is why it keeps its route but never joins the strip.
Links minted before it existed (`/users/search?user=&post=`) are forwarded here.

### The favorites bars

There are **two** bars, and they never mix - different chips, different storage
keys, `favorites:` in `config.yaml` saying which one a page shows:

| Bar | Pinned from | A chip reads | It opens |
|---|---|---|---|
| `users` | an author's page (Users) | `@handle` | `/users/search?user=` |
| `posts` | a post's page | the **tweet id** (its text is the tooltip) | `/posts/post/?post=` |

Both are browser bookmarks bars: new pins land at the front, and the chip of
whatever the page is currently showing is marked active. The links carry no
needle - a favorite is a jump to one thing, not a search.

Organising it (`components/FavoritesBar.tsx`, over the pure operations in
`lib/pins.ts`):

- **Drag** a chip along the bar to reorder it, onto the middle of a folder to
  file it there, or out of an open folder to bring it back to the bar. A caret
  shows where it would land; a folder about to swallow it is outlined.
- **New folder** appends one and opens its name for typing straight away -
  Enter or clicking away commits it, Escape leaves the default name.
- Every chip's **⋮ menu** (also its right-click menu) does the same without a
  pointer drag: move a favorite to the bar or to any folder, remove it, rename a
  folder, or delete a folder and its contents. A control that only answers to a
  drag is a control keyboard users do not have.

Folders never nest: a bar is one row and a menu, not a tree. State lives in
`localStorage` under `x.apps.x_proxy.pinnedUsers` and `…pinnedPosts`, and the
caps come from the top-level `favorites:` block in `config.yaml` - at most 60
favorites and 12 folders per bar, with folder names cut at 32 characters. The reader still accepts the plain
`["grok", …]` written before the bar had folders, so an existing browser keeps
its pins; anything unparseable is dropped rather than thrown, and blocked
storage (private mode, embedded frames) degrades to favorites that do not
survive a reload.

The whole page is one published dataset:

| Object | Holds |
|---|---|
| `search_users/users.json` | Every author (~60k) - the search index, as compact arrays: `[username, posts, last_post_at, location, verified_type, shard, description, display_name]` |
| `search_users/posts/<shard>.json` | For each author in the shard: `profile` + every post, newest first. A matched post carries the `queries` slugs it answered; a referenced one carries `referenced: true` and no queries (`DATASET_FORMAT` 3 - every shard rebuilds once) |
| `search_users/shards.json` | Per-shard content hash, author count, post count, byte size |

`description` and `display_name` are trailing columns, and `DATASET_FORMAT` is
deliberately *not* bumped for them: an older app ignores extras, a newer one
reads a missing one as empty, and a bump would force all 256 shards to be
re-queried for a change that touches none of them. Bios are capped at
`MAX_DESCRIPTION_CHARS` (160, which is X's own limit) - that cap is what bounds
their share of a ~60k-row index - and names + bios come from one pass each over
the hydrated accounts (`all_descriptions`, `all_display_names`), not from the
per-shard account query.

`DATASET_FORMAT` **is** bumped to 2 when author posts start including referenced
context (not only search matches): index counts and shard payloads both change,
so the next publish rebuilds every shard once.

Authors are grouped into 256 shards by `sha1(username)` (`user_shard`), so
selecting an author downloads one file of a few hundred KB instead of the whole
~110 MB dataset, and paging by 100 is a slice of an array already in memory. The
index carries each author's `shard` so the browser never has to hash anything -
`crypto.subtle` is undefined on a page served over plain http from a
non-localhost host, which would otherwise break the page in exactly the
deployments that need it.

Counts (`posts`, `last_post_at`, `first_post_at`) are SPARQL aggregates over the
whole graph, so the KPIs describe the author rather than the page on screen.
Posts are sorted newest-first with `url` as the tie-breaker, so authors who post
several times in the same second keep a stable order.

Each author's `profile` is the tweet aggregates merged with their `XUser`
individual - display name, bio, location, URL, join date,
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
concatenates them into one space-separated `media_url` - grouping is also
what keeps one row per tweet despite the join. An asset that fails to load
falls back to a plain link so the media stays reachable.

Attachments render as a **carousel** (`components/MediaCarousel.tsx`), one item
at a time with arrows, a counter and dots - a post with four photos is one
frame tall, not four. The frame keeps a fixed ratio and the item is contained
inside it, so moving between a portrait photo and a landscape video does not
resize the post under the pointer. The same component serves the post feed and
the table's Post / Media cells.

### Incremental republish

The ingestion orchestrations rebuild this dataset after **every** pipeline run,
so writing 256 shards each time would be wasteful. Each shard is serialized
once, hashed, and compared against `shards.json` from the previous publish;
identical shards are not re-uploaded. A typical tick touches a handful of
authors, so it writes a handful of shards. The graph reads still happen in full
(~60 s at 110k posts) - only the uploads are skipped.

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
dropped the partially-overlapped first bucket whole - a publish at 13:02 lost
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
LIMIT, so a capped read is the newest N tweets in the window - never an
arbitrary sample.

## Ingested tweets over time

The Search page line chart matches Count's **Posts over time**: per-hour (24h /
48h) or per-day (7d / 30d) **counts**, current vs previous period - not a
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

`filters` is `{column: {contains, values}}` - substring OR exact set, OR within
a column, AND across columns.

This replaced two live SPARQL routes (`api/tweets`, `api/tweets/values`); see
`docs/adr/20260728_x_app_live_tweet_search.md` for the design that preceded it.

### Serving is middleware, not routes

`XCountAppMiddleware` answers `/app-html/x/apps/x_proxy/…` **before the router**.
Nexus registers a `/app-html/{path:path}` static catch-all ahead of this
module's routes, so anything left to normal routing is answered with
`{"detail": "App HTML not found: …"}` before it reaches us. Middleware is the
only ordering that holds - worth remembering if a newly published path ever
needs serving: add it to `_SNAPSHOT_RE` (which allows one optional nested
directory, for `search_users/posts/<shard>.json`) rather than to a route table.

## Rebuild snapshots

```bash
# Uses config.local.yaml when present in the CWD:
cd /path/to/axi-ai
# Ensure web export exists first (pnpm build in apps/x_proxy/web)
uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.build --config config.local.yaml
```

Against the docker stack, `config.local.yaml` points at `http://minio:9000`, so
the publisher has to run *inside* the API container - which bind-mounts the repo,
and therefore sees a `web/out/` built on the host:

```bash
cd /path/to/axi-ai
(cd .abi/libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/apps/x_proxy/web && pnpm build)
docker compose exec abi uv run --no-dev python -m \
  naas_abi_marketplace.applications.x.apps.x_proxy.build --config config.local.yaml --web-only
```

`--web-only` uploads `web/out/` and nothing else - no SPARQL, no snapshot
rebuild - which is the loop for changing the UI. Drop it to republish the data
too. Changing `routes.py` needs `docker compose restart abi`; changing the web
app does not. The app is then at
`http://localhost:9879/app-html/x/apps/x_proxy/`.

Orchestrations call `publish_x_app()` → `XAppHubBuilder.publish()` which
delegates to `api.publish.publish_app`.

### Rebuilt after a pipeline run - opt-in

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
`x_build_app` schedule already republishes from the same graph state - so the
dashboard is at most an hour behind with this off. Turn it on per entry when the
dashboard must follow ingestion, or per run from the launchpad:

```yaml
ops:
  x_search_recent_tweets_files_op_reprocess_envelopes:
    config:
      app_publish: true
```

The files sweep publishes once rather than per file - it can map hundreds of
envelopes in a run, and the dataset is rebuilt from the final graph state
anyway. The event sensor publishes per envelope, which is why leaving it off is
the sane default there.

The helper never raises: a failed publish is logged and reported in the op's
summary (`{"failed": true, "error": …}`), because ingestion is what the run is
for and must not be undone by a storage hiccup. Shard hashing (above) is what
keeps an enabled republish cheap - a no-change rebuild uploads nothing.

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
2. `web/out/` in the repo - a developer's fresh `pnpm build` wins locally
3. `/opt/x-app-web/out` - the image-baked export used in production

If none exists, the two callers differ:

| Caller | `require_web` | No export anywhere |
|---|---|---|
| `build.py` CLI | `True` | Raises - you were meant to `pnpm build` first |
| `XAppHubBuilder.publish()` (orchestration) | `False` | Logs a warning, publishes the JSON snapshots, leaves the already-uploaded web assets untouched |

So production ships UI by **rebuilding the image**; the scheduled run then
publishes those assets along with the snapshots. Publishing from a dev host
still works too:

```bash
cd applications/x/apps/x_proxy/web && pnpm install && pnpm build
cd /path/to/axi-ai
uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.build --config config.remote.yaml
```

Changes to `routes.py` / `api/` additionally need the ABI service restarted:
route registration happens at startup, so a running process keeps serving the
code it imported.
