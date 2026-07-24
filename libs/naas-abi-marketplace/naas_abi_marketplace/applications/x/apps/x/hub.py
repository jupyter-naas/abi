"""Build the X "Recent Tweets" app from the recent-posts count + tweet graphs.

Runs the count SPARQL queries against
``GRAPH <http://ontology.naas.ai/graph/x_recent_posts_count>`` and publishes,
under ``x/apps/x/`` in object storage:

* ``data/catalog.json``      — the list of followed queries (dropdown 1)
* ``data/<slug>.json``       — the hourly time series for one followed query
* ``data/<slug>_tweets.json``— the tweets ingested for that query (for the table)
* ``index.html``             — the self-contained dashboard (X/Twitter theme)

The dashboard embeds a compact copy of every count series so the chart + KPIs
render with no network round-trip, and fetches the (potentially large) per-query
tweet snapshot on demand to fill the table below the chart. The tweet snapshots
come from the tweet-content graph populated by the search pipeline. Mirrors the
counter_uas report-hub pattern: the build only writes object storage; catalog
serving reads it back.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils

DEFAULT_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
# Tweet content (full_text, author, url) is written by XSearchRecentTweetsPipeline
# into the main X graph — the table below the chart reads it from there.
DEFAULT_TWEET_GRAPH = "http://ontology.naas.ai/graph/x"
DEFAULT_NAMESPACE = "http://ontology.naas.ai/x/"
DEFAULT_APP_PREFIX = "x/apps/x"
APP_HTML_DATA_BASE = "/app-html/x/apps/x/data"
# Cap the per-query tweet snapshot so the JSON stays reasonable; the table shows
# the most recent tweets within the selected window.
DEFAULT_TWEET_LIMIT = 2000


def slugify(value: str) -> str:
    """Filesystem-safe slug for a query string (kept short and stable)."""
    keep = []
    for ch in value.lower():
        keep.append(ch if ch.isalnum() else "_")
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:80] or "query"


class XCountAppHubBuilder:
    """Publish the X post-count dashboard + its JSON snapshots to object storage."""

    def __init__(
        self,
        object_storage_service: ObjectStorageService,
        triple_store: TripleStoreService,
        *,
        graph_name: str = DEFAULT_COUNT_GRAPH,
        tweet_graph_name: str = DEFAULT_TWEET_GRAPH,
        namespace: str = DEFAULT_NAMESPACE,
        app_prefix: str = DEFAULT_APP_PREFIX,
    ) -> None:
        self._object_storage = object_storage_service
        self._triple_store = triple_store
        self._storage = StorageUtils(object_storage_service)
        self.graph_name = graph_name
        self.tweet_graph_name = tweet_graph_name
        self.namespace = namespace
        self.app_prefix = app_prefix.rstrip("/")

    # ----- SPARQL -----------------------------------------------------------

    def _timeseries(self, query_string: str) -> list[dict[str, Any]]:
        """Hourly ``{start, end, count}`` buckets for *query_string*, oldest first."""
        escaped = query_string.replace("\\", "\\\\").replace('"', '\\"')
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT ?start ?end (MAX(?count) AS ?tweetCount)
        WHERE {{
          GRAPH <{self.graph_name}> {{
            ?resultSet rdf:type x:TweetCountResultSet ;
                       x:query_string "{escaped}" ;
                       x:containsCountBucket ?bucket .
            ?bucket x:bucket_tweet_count ?count ;
                    x:hasCountInterval ?interval .
            ?interval x:bucket_start ?start .
            OPTIONAL {{ ?interval x:bucket_end ?end . }}
          }}
        }}
        GROUP BY ?start ?end
        ORDER BY ?start
        """
        buckets: list[dict[str, Any]] = []
        try:
            rows = self._triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XCountAppHubBuilder: timeseries query failed for "
                f"{query_string!r} ({exc})"
            )
            return buckets
        for row in rows:
            start = getattr(row, "start", None)
            if start is None:
                continue
            end = getattr(row, "end", None)
            count = getattr(row, "tweetCount", None)
            buckets.append(
                {
                    "start": str(start),
                    "end": str(end) if end is not None else None,
                    "count": int(str(count)) if count is not None else 0,
                }
            )
        return buckets

    def _tweets(
        self, query_string: str, limit: int = DEFAULT_TWEET_LIMIT
    ) -> list[dict[str, Any]]:
        """Tweets ingested for *query_string*, newest first.

        Reads the tweet-content graph and returns, per tweet, the fields the
        dashboard table needs: created_at, full text, permalink, author handle,
        author location and verified type. Tweets are joined to the followed
        query through the SearchQuery / SearchRecentTweets / SearchResultSet the
        search pipeline records, matching lenient-both-ways on the query string
        so a count-follow query and its paired search filter line up even with
        minor differences.
        """
        escaped = query_string.replace("\\", "\\\\").replace('"', '\\"')
        sparql = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX x:   <{self.namespace}>
        SELECT DISTINCT ?created ?fullText ?text ?url ?username ?location ?verifiedType
        WHERE {{
          GRAPH <{self.tweet_graph_name}> {{
            ?sq rdf:type x:SearchQuery ; x:query_string ?qs .
            FILTER( CONTAINS(LCASE(STR(?qs)), LCASE("{escaped}"))
                 || CONTAINS(LCASE("{escaped}"), LCASE(STR(?qs))) )
            ?proc rdf:type x:SearchRecentTweets ;
                  x:usesSearchQuery ?sq ;
                  x:producesSearchResult ?rs .
            ?tweet rdf:type x:Tweet ;
                   x:isContainedInSearchResultSet ?rs ;
                   x:tweet_created_at ?created .
            OPTIONAL {{ ?tweet x:full_text ?fullText . }}
            OPTIONAL {{ ?tweet x:tweet_text ?text . }}
            OPTIONAL {{ ?tweet x:url ?url . }}
            OPTIONAL {{
              ?tweet x:isAuthoredBy ?author .
              OPTIONAL {{ ?author x:username ?username . }}
              OPTIONAL {{ ?author x:user_location ?location . }}
              OPTIONAL {{ ?author x:verified_type ?verifiedType . }}
            }}
          }}
        }}
        ORDER BY DESC(?created)
        LIMIT {int(limit)}
        """
        tweets: list[dict[str, Any]] = []
        try:
            rows = self._triple_store.query(sparql)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"XCountAppHubBuilder: tweets query failed for {query_string!r} ({exc})"
            )
            return tweets

        def _s(row: Any, key: str) -> str:
            value = getattr(row, key, None)
            return "" if value is None else str(value)

        for row in rows:
            created = getattr(row, "created", None)
            if created is None:
                continue
            full = _s(row, "fullText")
            tweets.append(
                {
                    "created_at": str(created),
                    "text": full or _s(row, "text"),
                    "url": _s(row, "url"),
                    "username": _s(row, "username"),
                    "location": _s(row, "location"),
                    "verified_type": _s(row, "verifiedType"),
                }
            )
        return tweets

    # ----- Publish ----------------------------------------------------------

    def publish(self, queries: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Publish the dashboard + snapshots for the given followed *queries*.

        Each entry is ``{"name"?, "query", "label"?}``. Returns a summary dict.
        """
        built_at = datetime.now(UTC)
        series: list[dict[str, Any]] = []
        catalog: list[dict[str, Any]] = []

        for entry in queries:
            query_string = str(entry.get("query") or "").strip()
            if not query_string:
                continue
            slug = slugify(entry.get("name") or query_string)
            label = str(entry.get("label") or entry.get("name") or query_string)
            buckets = self._timeseries(query_string)
            total = sum(b["count"] for b in buckets)
            last_start = buckets[-1]["start"] if buckets else None

            item = {
                "slug": slug,
                "query": query_string,
                "label": label,
                "granularity": "hour",
                "updated_at": built_at.isoformat(),
                "buckets": buckets,
            }
            series.append(item)
            self._storage.save_json(
                item, f"{self.app_prefix}/data", f"{slug}.json", copy=False
            )

            # Per-query tweet snapshot (fetched on demand by the table).
            tweets = self._tweets(query_string)
            self._storage.save_json(
                {
                    "slug": slug,
                    "query": query_string,
                    "label": label,
                    "updated_at": built_at.isoformat(),
                    "tweets": tweets,
                },
                f"{self.app_prefix}/data",
                f"{slug}_tweets.json",
                copy=False,
            )

            catalog.append(
                {
                    "slug": slug,
                    "query": query_string,
                    "label": label,
                    "total": total,
                    "buckets": len(buckets),
                    "tweets": len(tweets),
                    "last_bucket_start": last_start,
                }
            )

        catalog_doc = {"updated_at": built_at.isoformat(), "queries": catalog}
        self._storage.save_json(
            catalog_doc, f"{self.app_prefix}/data", "catalog.json", copy=False
        )
        self._storage.save_html(
            render_index(series, built_at),
            self.app_prefix,
            "index.html",
            copy=False,
        )
        summary = {
            "app_prefix": self.app_prefix,
            "queries_published": [item["slug"] for item in series],
            "index_file": f"{self.app_prefix}/index.html",
            "built_at": built_at.isoformat(),
        }
        logger.info(f"XCountAppHubBuilder: published dashboard — {summary}")
        return summary


def render_index(series: list[dict[str, Any]], built_at: datetime) -> str:
    """Render the self-contained X post-count dashboard (X/Twitter dark theme)."""
    data_json = html.escape(json.dumps(series, ensure_ascii=False), quote=False)
    built = html.escape(built_at.strftime("%Y-%m-%d %H:%M UTC"))
    return _INDEX_TEMPLATE.replace("__DATA_JSON__", data_json).replace(
        "__BUILT_AT__", built
    )


# The dashboard is fully client-side: it reads the embedded SERIES, filters by
# the selected window, aggregates hourly (<=48h) or daily (7d/30d), and derives
# the KPIs (total / mean / peak / lowest) + line chart from the filtered series.
_INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>X · Recent Tweets</title>
  <style>
    :root {
      --bg: #000000; --panel: #16181c; --panel-2: #1d1f23; --border: #2f3336;
      --text: #e7e9ea; --muted: #71767b; --accent: #1d9bf0; --label: #c7ccd0;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .shell { max-width: 1360px; margin: 0 auto; padding: 24px 24px 56px; }
    header { display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border);
      padding-bottom: 16px; margin-bottom: 20px; }
    .logo { width: 30px; height: 30px; fill: var(--text); flex: 0 0 auto; }
    h1 { margin: 0; font-size: 1.25rem; font-weight: 800; letter-spacing: -.01em; }
    .built { margin-left: auto; color: var(--muted); font-size: .78rem; }
    .controls { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-end; gap: 12px; margin-bottom: 26px; }
    .field { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .field label { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--label); font-weight: 700; }
    select { appearance: none; background: var(--panel); color: var(--text);
      border: 1px solid var(--border); border-radius: 0; padding: 9px 36px 9px 14px; font-size: .9rem;
      font-family: inherit; cursor: pointer;
      background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2371767b' stroke-width='2'><path d='M6 9l6 6 6-6'/></svg>");
      background-repeat: no-repeat; background-position: right 12px center; }
    #query-select { min-width: 460px; max-width: 100%; }
    #window-select { min-width: 190px; }
    select:focus { outline: none; border-color: var(--accent); }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 6px; }
    .kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 0; padding: 16px 18px; }
    .kpi-label { font-size: .72rem; color: var(--label); font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
    .kpi-value { margin-top: 6px; font-size: 1.7rem; font-weight: 800; line-height: 1.1; letter-spacing: -.02em; }
    .kpi-hint { margin-top: 4px; font-size: .74rem; color: var(--muted); }
    .kpi-value.up { color: var(--accent); }
    .kpi-delta { margin-left: 8px; font-size: .95rem; font-weight: 700; }
    .kpi-delta.pos, .bl-delta.pos { color: #00ba7c; }
    .kpi-delta.neg, .bl-delta.neg { color: #f4212e; }
    .kpi-delta.flat, .bl-delta.flat { color: var(--muted); }
    .bl-delta { margin-left: 6px; font-size: .72rem; font-weight: 700; }
    .kpi-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
    .kpi-chart { background: var(--panel); border: 1px solid var(--border); border-radius: 0; padding: 16px 18px; }
    .kpi-chart .kpi-label { margin-bottom: 12px; }
    /* Top-3 visible, scrollable to 10. */
    .bar-list { display: flex; flex-direction: column; gap: 12px; max-height: 150px; overflow-y: auto;
      padding-right: 6px; }
    .bar-row { display: grid; grid-template-columns: 1fr auto; column-gap: 10px; row-gap: 5px; align-items: baseline; }
    .bar-row .bl-label { font-size: .82rem; color: var(--text); overflow: hidden; text-overflow: ellipsis;
      white-space: nowrap; }
    .bar-row .bl-label a { color: var(--text); text-decoration: none; }
    .bar-row .bl-label a:hover { color: var(--accent); text-decoration: underline; }
    .bar-row .bl-value { font-size: .82rem; font-weight: 700; color: var(--muted); font-variant-numeric: tabular-nums; }
    .bar-row .bl-track { grid-column: 1 / -1; height: 6px; background: var(--panel-2); }
    .bar-row .bl-fill { height: 100%; background: var(--accent); }
    .bar-empty { color: var(--muted); font-size: .82rem; padding: 8px 0; }
    .section { margin-top: 28px; }
    .section-head { margin-bottom: 10px; }
    .section-head h2 { margin: 0; font-size: 1.05rem; font-weight: 700; }
    .section-head .sub { margin: 3px 0 0; font-size: .8rem; color: var(--muted); word-break: break-word; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 0; padding: 16px; }
    .chart-wrap { width: 100%; overflow-x: auto; }
    svg.chart { width: 100%; height: 300px; display: block; }
    text { fill: var(--muted); font-size: 11px; }
    .dt-toolbar { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center;
      justify-content: space-between; margin-bottom: 12px; }
    .dt-search { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 0;
      padding: 8px 12px; font-size: .85rem; min-width: 280px; }
    .dt-search:focus { outline: none; border-color: var(--accent); }
    .col-toggles { display: flex; flex-wrap: wrap; gap: 6px 14px; }
    .col-toggles label { display: inline-flex; align-items: center; gap: 6px; font-size: .74rem;
      color: var(--muted); cursor: pointer; }
    .dt-wrap { width: 100%; overflow-x: auto; max-height: 720px; overflow-y: auto; }
    table.dt { width: 100%; border-collapse: collapse; font-size: .82rem; }
    table.dt thead th { position: sticky; top: 0; z-index: 2; text-align: left; background: var(--panel-2);
      color: var(--label); font-weight: 700; font-size: .7rem; text-transform: uppercase; letter-spacing: .04em;
      padding: 9px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
    table.dt thead th.sortable { cursor: pointer; user-select: none; }
    table.dt thead th.sortable:hover { color: var(--text); }
    table.dt thead th .arrow { color: var(--accent); margin-left: 4px; }
    table.dt tr.filters th { top: 33px; background: var(--panel); z-index: 1; padding: 6px 8px; }
    table.dt tr.filters input { width: 100%; min-width: 70px; background: var(--bg); color: var(--text);
      border: 1px solid var(--border); border-radius: 0; padding: 5px 7px; font-size: .74rem; }
    table.dt tr.filters input:focus { outline: none; border-color: var(--accent); }
    table.dt td { padding: 10px; border-bottom: 1px solid var(--border); vertical-align: top; color: var(--text); }
    table.dt td.col-rank { white-space: nowrap; color: var(--muted); }
    table.dt td.col-date { white-space: nowrap; color: var(--label); font-weight: 600; }
    table.dt td.col-count { white-space: nowrap; color: var(--text); font-weight: 700; }
    table.dt td.col-text { max-width: 560px; white-space: pre-wrap; word-break: break-word; }
    table.dt a { color: var(--accent); text-decoration: none; word-break: break-all; }
    table.dt a:hover { text-decoration: underline; }
    table.dt tr:hover td { background: var(--panel-2); }
    table.dt td.empty { text-align: center; color: var(--muted); padding: 40px 10px; }
    .pager { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-top: 12px;
      font-size: .78rem; color: var(--muted); }
    .pager button { background: var(--panel); color: var(--text); border: 1px solid var(--border);
      border-radius: 0; padding: 6px 12px; font-size: .78rem; cursor: pointer; font-family: inherit; }
    .pager button:disabled { opacity: .4; cursor: default; }
    @media (max-width: 820px) { .kpis { grid-template-columns: repeat(2, 1fr); }
      #query-select { min-width: 240px; } table.dt td.col-text { max-width: 280px; } }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
      <h1>Recent Tweets</h1>
      <span class="built">Snapshot · __BUILT_AT__</span>
    </header>

    <div class="controls">
      <div class="field">
        <label for="window-select">Scenario</label>
        <select id="window-select" aria-label="Scenario">
          <option value="24">Last 24 hours</option>
          <option value="48">Last 48 hours</option>
          <option value="168" selected>Last 7 days</option>
          <option value="720">Last 30 days</option>
        </select>
      </div>
      <div class="field">
        <label for="query-select">Query</label>
        <select id="query-select" aria-label="Followed query"></select>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="kpi-label">Total posts</div>
        <div class="kpi-value up"><span id="kpi-total">—</span><span id="kpi-total-delta" class="kpi-delta"></span></div>
        <div id="kpi-total-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label" id="kpi-mean-label">Mean / hour</div>
        <div class="kpi-value"><span id="kpi-mean">—</span><span id="kpi-mean-delta" class="kpi-delta"></span></div>
        <div id="kpi-mean-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">High</div><div id="kpi-top" class="kpi-value">—</div><div id="kpi-top-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">Low</div><div id="kpi-down" class="kpi-value">—</div><div id="kpi-down-hint" class="kpi-hint"></div></div>
    </div>

    <div class="kpi-charts">
      <div class="kpi-chart">
        <div class="kpi-label">Top authors</div>
        <div class="bar-list" id="bars-authors"></div>
      </div>
      <div class="kpi-chart">
        <div class="kpi-label">Top author locations</div>
        <div class="bar-list" id="bars-locations"></div>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <h2>Posts over time</h2>
        <p class="sub" id="chart-sub">Select a query to see its trend.</p>
      </div>
      <div class="card"><div class="chart-wrap"><svg id="chart" class="chart" role="img" aria-label="Posts over time"></svg></div></div>
    </div>

    <div class="section">
      <div class="section-head">
        <h2>Tweets in range</h2>
        <p class="sub" id="tweets-sub">Select a query to load its tweets.</p>
      </div>
      <div class="card"><div id="tweets-table"></div></div>
    </div>

    <div class="section">
      <div class="section-head">
        <h2>Top authors</h2>
        <p class="sub" id="authors-sub">Ranked by tweet count in range.</p>
      </div>
      <div class="card"><div id="authors-table"></div></div>
    </div>
  </div>

  <script id="series-data" type="application/json">__DATA_JSON__</script>
  <script>
  (() => {
    const SERIES = JSON.parse(document.getElementById("series-data").textContent);
    const bySlug = Object.fromEntries(SERIES.map((s) => [s.slug, s]));
    const querySel = document.getElementById("query-select");
    const windowSel = document.getElementById("window-select");
    const svg = document.getElementById("chart");
    const NS = "http://www.w3.org/2000/svg";

    SERIES.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.slug;
      opt.textContent = s.query;
      querySel.appendChild(opt);
    });
    if (!SERIES.length) {
      const opt = document.createElement("option");
      opt.textContent = "No followed queries yet";
      querySel.appendChild(opt);
      querySel.disabled = true;
    }

    const fmt = (n) => Number(n).toLocaleString();
    const parse = (iso) => new Date(iso);

    // Aggregate count buckets whose start falls in [fromMs, toMs) into chart
    // points — hourly for <=48h scenarios, daily otherwise. Used for both the
    // current scenario and its comparison (previous) period.
    function aggregateRange(buckets, fromMs, toMs, daily) {
      const inRange = buckets.filter((b) => {
        const t = parse(b.start).getTime();
        return t >= fromMs && t < toMs;
      });
      if (!daily) {
        return inRange.map((b) => {
          const start = parse(b.start);
          // Trust the stored end only when it is strictly after the start; some
          // buckets store end == start, which would render "12 h – 12 h".
          let end = b.end ? parse(b.end) : null;
          if (!end || end.getTime() <= start.getTime()) {
            end = new Date(start.getTime() + 3600000);
          }
          const label = start.toLocaleString(undefined,
            { month: "short", day: "numeric", hour: "2-digit" });
          const endLabel = end.toLocaleString(undefined, { hour: "2-digit" });
          return { t: start, value: b.count, label, rangeLabel: label + " – " + endLabel };
        });
      }
      const byDay = new Map();
      for (const b of inRange) {
        const key = parse(b.start).toISOString().slice(0, 10);
        byDay.set(key, (byDay.get(key) || 0) + b.count);
      }
      return [...byDay.entries()].sort().map(([key, value]) => {
        const start = new Date(key + "T00:00:00Z");
        const end = new Date(start.getTime() + 86400000);
        const label = start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        const endLabel = end.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        return { t: start, value, label, rangeLabel: label + " – " + endLabel };
      });
    }

    function setDelta(id, delta, decimals) {
      const e = document.getElementById(id);
      const r = decimals ? Math.round(delta * 10) / 10 : Math.round(delta);
      e.className = "kpi-delta " + (r > 0 ? "pos" : r < 0 ? "neg" : "flat");
      e.textContent = r === 0 ? "±0"
        : (r > 0 ? "+" : "") + r.toLocaleString(undefined, { maximumFractionDigits: decimals ? 1 : 0 });
    }
    function setKpis(cur, comp, daily) {
      const curTotal = cur.reduce((a, p) => a + p.value, 0);
      const compTotal = comp.reduce((a, p) => a + p.value, 0);
      const curMean = cur.length ? curTotal / cur.length : 0;
      const compMean = comp.length ? compTotal / comp.length : 0;
      const unit = daily ? "day" : "hour";

      document.getElementById("kpi-total").textContent = fmt(curTotal);
      setDelta("kpi-total-delta", curTotal - compTotal, false);
      document.getElementById("kpi-total-hint").textContent =
        comp.length ? fmt(compTotal) + " prev. period" : "no prior period";

      document.getElementById("kpi-mean-label").textContent = "Mean / " + unit;
      document.getElementById("kpi-mean").textContent =
        curMean.toLocaleString(undefined, { maximumFractionDigits: 1 });
      setDelta("kpi-mean-delta", curMean - compMean, true);
      document.getElementById("kpi-mean-hint").textContent = comp.length
        ? compMean.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " prev. period"
        : "no prior period";

      // High / Low: no comparison (rename of Peak / Lowest).
      const top = cur.reduce((a, b) => (b.value > (a?.value ?? -1) ? b : a), null);
      const down = cur.reduce((a, b) => (b.value < (a?.value ?? Infinity) ? b : a), null);
      document.getElementById("kpi-top").textContent = top ? fmt(top.value) : "—";
      document.getElementById("kpi-top-hint").textContent = top ? top.rangeLabel : "";
      document.getElementById("kpi-down").textContent = down ? fmt(down.value) : "—";
      document.getElementById("kpi-down-hint").textContent = down ? down.rangeLabel : "";
    }

    function draw(cur, comp, daily) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const n = cur.length;
      const W = Math.max(720, n * (daily ? 34 : 12));
      const H = 300, pad = { l: 44, r: 16, t: 16, b: 40 };
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      if (!n) {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", W / 2); t.setAttribute("y", H / 2);
        t.setAttribute("text-anchor", "middle");
        t.textContent = "No data in this range.";
        svg.appendChild(t); return;
      }
      const innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
      const maxV = Math.max(1, ...cur.map((p) => p.value), ...comp.map((p) => p.value));
      const xAt = (i) => pad.l + (n > 1 ? (i * innerW) / (n - 1) : innerW / 2);
      const yAt = (v) => pad.t + innerH - (v / maxV) * innerH;

      [0, 0.5, 1].forEach((f) => {
        const v = Math.round(maxV * f), y = yAt(v);
        const line = document.createElementNS(NS, "line");
        line.setAttribute("x1", pad.l); line.setAttribute("x2", W - pad.r);
        line.setAttribute("y1", y); line.setAttribute("y2", y);
        line.setAttribute("stroke", "#2f3336"); line.setAttribute("stroke-width", "1");
        svg.appendChild(line);
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", pad.l - 8); t.setAttribute("y", y + 4);
        t.setAttribute("text-anchor", "end"); t.textContent = fmt(v);
        svg.appendChild(t);
      });

      // Comparison (previous period) line — aligned by index, dashed + muted.
      if (comp.length) {
        const cpath = comp.slice(0, n).map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`).join(" ");
        const cline = document.createElementNS(NS, "path");
        cline.setAttribute("d", cpath); cline.setAttribute("fill", "none");
        cline.setAttribute("stroke", "#71767b"); cline.setAttribute("stroke-width", "1.5");
        cline.setAttribute("stroke-dasharray", "4 4");
        cline.setAttribute("stroke-linejoin", "round"); cline.setAttribute("stroke-linecap", "round");
        svg.appendChild(cline);
      }

      const path = cur.map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`).join(" ");
      const area = document.createElementNS(NS, "path");
      area.setAttribute("d", `${path} L ${xAt(n - 1)} ${pad.t + innerH} L ${xAt(0)} ${pad.t + innerH} Z`);
      area.setAttribute("fill", "#1d9bf0"); area.setAttribute("fill-opacity", "0.12");
      svg.appendChild(area);
      const line = document.createElementNS(NS, "path");
      line.setAttribute("d", path); line.setAttribute("fill", "none");
      line.setAttribute("stroke", "#1d9bf0"); line.setAttribute("stroke-width", "2");
      line.setAttribute("stroke-linejoin", "round"); line.setAttribute("stroke-linecap", "round");
      svg.appendChild(line);

      const labelEvery = Math.ceil(n / (daily ? 12 : 8));
      cur.forEach((p, i) => {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", xAt(i)); dot.setAttribute("cy", yAt(p.value));
        dot.setAttribute("r", daily ? 3 : 2.2); dot.setAttribute("fill", "#1d9bf0");
        const title = document.createElementNS(NS, "title");
        const cv = comp[i] ? comp[i].value : null;
        title.textContent = `${p.label}: ${fmt(p.value)} posts`
          + (cv != null ? ` (prev. ${fmt(cv)})` : "");
        dot.appendChild(title); svg.appendChild(dot);
        if (i % labelEvery === 0 || i === n - 1) {
          const t = document.createElementNS(NS, "text");
          t.setAttribute("x", xAt(i)); t.setAttribute("y", H - pad.b + 20);
          t.setAttribute("text-anchor", "middle"); t.textContent = p.label;
          svg.appendChild(t);
        }
      });
    }

    // ----- Generic Excel-like data table -----------------------------------
    const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };
    const fmtDate = (iso) => new Date(iso).toLocaleString(undefined,
      { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    const chartSub = document.getElementById("chart-sub");
    const tweetsSub = document.getElementById("tweets-sub");
    const authorsSub = document.getElementById("authors-sub");
    const barsAuthors = document.getElementById("bars-authors");
    const barsLocations = document.getElementById("bars-locations");
    const PAGE_SIZE = 50;

    function createDataTable(host, opts) {
      const columns = opts.columns;
      const pageSize = opts.pageSize || PAGE_SIZE;
      const visible = new Set(columns.filter((c) => c.visible !== false).map((c) => c.key));
      const filters = {};
      let rows = [];
      let globalQ = "";
      let sortKey = opts.sortKey || null;
      let sortDir = opts.sortDir || "asc";
      let page = 1;
      let focusKey = null;

      host.innerHTML = "";
      const toolbar = el("div", "dt-toolbar");
      const search = el("input", "dt-search");
      search.type = "search";
      search.placeholder = opts.searchPlaceholder || "Search all columns…";
      search.addEventListener("input", () => { globalQ = search.value; page = 1; draw(); });
      const toggles = el("div", "col-toggles");
      columns.forEach((c) => {
        if (c.toggle === false) return;
        const lab = document.createElement("label");
        const cb = document.createElement("input");
        cb.type = "checkbox"; cb.checked = visible.has(c.key);
        cb.addEventListener("change", () => {
          if (cb.checked) visible.add(c.key); else { visible.delete(c.key); delete filters[c.key]; }
          page = 1; draw();
        });
        lab.appendChild(cb); lab.appendChild(document.createTextNode(c.label));
        toggles.appendChild(lab);
      });
      toolbar.appendChild(search); toolbar.appendChild(toggles);
      const wrap = el("div", "dt-wrap");
      const pager = el("div", "pager");
      host.appendChild(toolbar); host.appendChild(wrap); host.appendChild(pager);

      const activeCols = () => columns.filter((c) => visible.has(c.key));
      const cellText = (c, row) => { const v = c.text ? c.text(row) : row[c.key]; return v == null ? "" : v; };
      const sortVal = (c, row) => (c.sortVal ? c.sortVal(row) : cellText(c, row));

      function filtered() {
        const gq = globalQ.trim().toLowerCase();
        return rows.filter((row) => {
          if (gq && !columns.some((c) => String(cellText(c, row)).toLowerCase().includes(gq))) return false;
          return activeCols().every((c) => {
            const f = (filters[c.key] || "").trim().toLowerCase();
            return !f || String(cellText(c, row)).toLowerCase().includes(f);
          });
        });
      }
      function cmp(a, b) {
        const an = Number(a), bn = Number(b);
        if (a !== "" && b !== "" && !Number.isNaN(an) && !Number.isNaN(bn)) return an - bn;
        return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
      }
      function sorted(list) {
        if (!sortKey) return list;
        const c = columns.find((x) => x.key === sortKey);
        if (!c) return list;
        const cp = list.slice();
        cp.sort((a, b) => { const r = cmp(sortVal(c, a), sortVal(c, b)); return sortDir === "asc" ? r : -r; });
        return cp;
      }

      function draw() {
        const cols = activeCols();
        const view = sorted(filtered());
        const pages = Math.max(1, Math.ceil(view.length / pageSize));
        if (page > pages) page = pages;
        const slice = view.slice((page - 1) * pageSize, page * pageSize);

        const table = el("table", "dt");
        const thead = document.createElement("thead");
        const hr = document.createElement("tr");
        cols.forEach((c) => {
          const th = document.createElement("th");
          if (c.cls) th.className = c.cls;
          th.textContent = c.label;
          if (c.sortable !== false) {
            th.classList.add("sortable");
            if (c.key === sortKey) {
              const s = el("span", "arrow"); s.textContent = sortDir === "asc" ? "▲" : "▼";
              th.appendChild(s);
            }
            th.addEventListener("click", () => {
              if (sortKey === c.key) sortDir = sortDir === "asc" ? "desc" : "asc";
              else { sortKey = c.key; sortDir = c.defaultDir || "asc"; }
              draw();
            });
          }
          hr.appendChild(th);
        });
        thead.appendChild(hr);

        if (opts.columnSearch !== false) {
          const fr = el("tr", "filters");
          cols.forEach((c) => {
            const th = document.createElement("th");
            if (c.searchable !== false) {
              const inp = document.createElement("input");
              inp.type = "search"; inp.placeholder = "Filter…";
              inp.value = filters[c.key] || "";
              inp.dataset.fk = c.key;
              inp.addEventListener("input", () => {
                filters[c.key] = inp.value; page = 1; focusKey = c.key; draw();
              });
              th.appendChild(inp);
            }
            fr.appendChild(th);
          });
          thead.appendChild(fr);
        }
        table.appendChild(thead);

        const tb = document.createElement("tbody");
        if (!slice.length) {
          const tr = document.createElement("tr");
          const td = document.createElement("td");
          td.className = "empty"; td.colSpan = cols.length;
          td.textContent = opts.emptyText || "No rows.";
          tr.appendChild(td); tb.appendChild(tr);
        } else {
          const frag = document.createDocumentFragment();
          slice.forEach((row) => {
            const tr = document.createElement("tr");
            cols.forEach((c) => {
              const td = document.createElement("td");
              if (c.cls) td.className = c.cls;
              const content = c.render ? c.render(row) : String(cellText(c, row));
              if (content == null || content === "") td.textContent = "—";
              else if (typeof content === "string") td.textContent = content;
              else td.appendChild(content);
              tr.appendChild(td);
            });
            frag.appendChild(tr);
          });
          tb.appendChild(frag);
        }
        table.appendChild(tb);
        wrap.innerHTML = ""; wrap.appendChild(table);

        pager.innerHTML = "";
        const info = document.createElement("span");
        info.textContent = view.length + " row(s) · page " + page + " / " + pages;
        const prev = document.createElement("button");
        prev.textContent = "Prev"; prev.disabled = page <= 1;
        prev.addEventListener("click", () => { page -= 1; draw(); });
        const next = document.createElement("button");
        next.textContent = "Next"; next.disabled = page >= pages;
        next.addEventListener("click", () => { page += 1; draw(); });
        pager.appendChild(info); pager.appendChild(prev); pager.appendChild(next);

        if (focusKey) {
          const a = wrap.querySelector('input[data-fk="' + focusKey + '"]');
          if (a) { a.focus(); const n = a.value.length; a.setSelectionRange(n, n); }
          focusKey = null;
        }
      }

      return { setRows(newRows) { rows = newRows || []; page = 1; draw(); } };
    }

    // ----- data shaping -----------------------------------------------------
    function tweetsBetween(tweets, fromMs, toMs) {
      return tweets.filter((t) => {
        const ts = new Date(t.created_at).getTime();
        return ts >= fromMs && ts < toMs;
      });
    }
    function countBy(tweets, keyFn) {
      const m = new Map();
      tweets.forEach((t) => {
        const k = keyFn(t);
        if (k == null) return;
        m.set(k, (m.get(k) || 0) + 1);
      });
      return m;
    }
    function authorRanking(tweets) {
      const map = new Map();
      tweets.forEach((t) => {
        const u = t.username || "—";
        const e = map.get(u) ||
          { username: u, location: t.location || "", verified: t.verified_type || "", tweet_count: 0 };
        e.tweet_count += 1;
        if (!e.location && t.location) e.location = t.location;
        if (!e.verified && t.verified_type) e.verified = t.verified_type;
        map.set(u, e);
      });
      const arr = [...map.values()].sort((a, b) => b.tweet_count - a.tweet_count);
      arr.forEach((e, i) => { e.rank = i + 1; });
      return arr;
    }
    function authorLink(username) {
      if (!username || username === "—") return "—";
      const a = document.createElement("a");
      a.href = "https://x.com/" + username; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.textContent = "@" + username;
      return a;
    }
    function tweetTextCell(t) {
      const frag = document.createDocumentFragment();
      const span = document.createElement("span"); span.textContent = t.text || "";
      frag.appendChild(span);
      if (t.url) {
        frag.appendChild(document.createElement("br"));
        const a = document.createElement("a");
        a.href = t.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = t.url;
        frag.appendChild(a);
      }
      return frag;
    }
    function authorLocationRanking(tweets) {
      const map = new Map();
      tweets.forEach((t) => {
        const loc = (t.location || "").trim();
        if (!loc) return;
        map.set(loc, (map.get(loc) || 0) + 1);
      });
      return [...map.entries()]
        .map(([location, count]) => ({ location, count }))
        .sort((a, b) => b.count - a.count);
    }
    // Horizontal bar list — shows the top items (top 3 visible, scroll to 10).
    function renderBarList(host, items) {
      host.innerHTML = "";
      if (!items.length) {
        const p = el("div", "bar-empty"); p.textContent = "No data in range.";
        host.appendChild(p); return;
      }
      const max = Math.max(1, ...items.map((i) => i.value));
      const frag = document.createDocumentFragment();
      items.forEach((it) => {
        const row = el("div", "bar-row");
        const label = el("div", "bl-label"); label.title = it.label;
        if (it.href) {
          const a = document.createElement("a");
          a.href = it.href; a.target = "_blank"; a.rel = "noopener noreferrer";
          a.textContent = it.label;
          label.appendChild(a);
        } else { label.textContent = it.label; }
        const val = el("div", "bl-value"); val.textContent = fmt(it.value);
        if (typeof it.delta === "number") {
          const d = document.createElement("span");
          d.className = "bl-delta " + (it.delta > 0 ? "pos" : it.delta < 0 ? "neg" : "flat");
          d.textContent = it.delta === 0 ? "±0" : (it.delta > 0 ? "+" : "") + fmt(it.delta);
          d.title = "vs previous period";
          val.appendChild(d);
        }
        const track = el("div", "bl-track");
        const fill = el("div", "bl-fill"); fill.style.width = (100 * it.value / max) + "%";
        track.appendChild(fill);
        row.appendChild(label); row.appendChild(val); row.appendChild(track);
        frag.appendChild(row);
      });
      host.appendChild(frag);
    }

    const tweetsTable = createDataTable(document.getElementById("tweets-table"), {
      searchPlaceholder: "Search tweets…",
      emptyText: "No tweets in this range.",
      sortKey: "date", sortDir: "desc",
      columns: [
        { key: "date", label: "Date", cls: "col-date", defaultDir: "desc",
          text: (r) => r.created_at, sortVal: (r) => r.created_at, render: (r) => fmtDate(r.created_at) },
        { key: "text", label: "Text", cls: "col-text", text: (r) => r.text, render: (r) => tweetTextCell(r) },
        { key: "author", label: "Author", text: (r) => r.username, render: (r) => authorLink(r.username) },
        { key: "location", label: "Location", text: (r) => r.location },
        { key: "verified", label: "Verified", text: (r) => r.verified_type },
      ],
    });
    const authorsTable = createDataTable(document.getElementById("authors-table"), {
      searchPlaceholder: "Search authors…",
      emptyText: "No authors in this range.",
      sortKey: "tweet_count", sortDir: "desc",
      columns: [
        { key: "rank", label: "#", cls: "col-rank", searchable: false, defaultDir: "asc",
          text: (r) => r.rank, sortVal: (r) => r.rank },
        { key: "author", label: "Author", text: (r) => r.username, render: (r) => authorLink(r.username) },
        { key: "location", label: "Location", text: (r) => r.location },
        { key: "verified", label: "Verified", text: (r) => r.verified },
        { key: "tweet_count", label: "Tweets", cls: "col-count", defaultDir: "desc",
          text: (r) => String(r.tweet_count), sortVal: (r) => r.tweet_count },
      ],
    });

    // ----- tweets fetch + wiring -------------------------------------------
    const tweetCache = {};   // slug -> array | null (null = load failed)
    async function ensureTweets(slug) {
      if (slug in tweetCache) return tweetCache[slug];
      try {
        const r = await fetch("data/" + slug + "_tweets.json", { cache: "no-store" });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const d = await r.json();
        tweetCache[slug] = Array.isArray(d.tweets) ? d.tweets : [];
      } catch (e) { tweetCache[slug] = null; }
      return tweetCache[slug];
    }

    async function update() {
      const s = bySlug[querySel.value];
      const hours = Number(windowSel.value);
      const daily = hours > 48;
      const now = Date.now();
      const win = hours * 3600 * 1000;
      // Comparison = the equal-length window immediately preceding the current one.
      const curFrom = now - win, curTo = now;
      const compFrom = now - 2 * win, compTo = now - win;
      if (!s) {
        setKpis([], [], false); draw([], [], false);
        chartSub.textContent = "";
        tweetsSub.textContent = "No followed queries yet";
        authorsSub.textContent = "";
        tweetsTable.setRows([]); authorsTable.setRows([]);
        renderBarList(barsAuthors, []); renderBarList(barsLocations, []);
        return;
      }
      const curPts = aggregateRange(s.buckets || [], curFrom, curTo, daily);
      const compPts = aggregateRange(s.buckets || [], compFrom, compTo, daily);
      chartSub.textContent = (daily ? "Per day" : "Per hour") + " · current vs previous period";
      setKpis(curPts, compPts, daily);
      draw(curPts, compPts, daily);

      const tweets = await ensureTweets(s.slug);
      if (tweets === null) {
        tweetsSub.textContent = "Tweets unavailable";
        authorsSub.textContent = "";
        tweetsTable.setRows([]); authorsTable.setRows([]);
        renderBarList(barsAuthors, []); renderBarList(barsLocations, []);
        return;
      }
      const curTweets = tweetsBetween(tweets, curFrom, curTo);
      const compTweets = tweetsBetween(tweets, compFrom, compTo);

      tweetsSub.textContent = curTweets.length + " tweet(s) in range";
      tweetsTable.setRows(curTweets);
      const ranking = authorRanking(curTweets);
      authorsSub.textContent = ranking.length + " author(s) in range";
      authorsTable.setRows(ranking);

      // Bar-chart KPIs (top 3 shown, scroll to 10) with previous-period deltas.
      const compAuthors = countBy(compTweets, (t) => t.username || "—");
      renderBarList(barsAuthors, ranking.slice(0, 10).map((a) => ({
        label: "@" + a.username,
        value: a.tweet_count,
        href: (a.username && a.username !== "—") ? "https://x.com/" + a.username : null,
        delta: a.tweet_count - (compAuthors.get(a.username) || 0),
      })));
      const compLoc = countBy(compTweets, (t) => (t.location || "").trim() || null);
      renderBarList(barsLocations, authorLocationRanking(curTweets).slice(0, 10).map((l) => ({
        label: l.location,
        value: l.count,
        delta: l.count - (compLoc.get(l.location) || 0),
      })));
    }

    querySel.addEventListener("change", update);
    windowSel.addEventListener("change", update);
    update();
  })();
  </script>
</body>
</html>"""
