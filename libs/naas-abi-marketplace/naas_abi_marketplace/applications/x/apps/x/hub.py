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
    .app { display: flex; align-items: flex-start; min-height: 100vh; }

    /* ----- Sidebar (sticky, collapsible) ----- */
    .sidebar { position: sticky; top: 0; height: 100vh; flex: 0 0 auto; width: 248px;
      background: var(--panel); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden; transition: width .18s ease; }
    .sidebar.collapsed { width: 64px; }
    .brand { display: flex; align-items: center; gap: 12px; padding: 18px; border-bottom: 1px solid var(--border);
      white-space: nowrap; overflow: hidden; cursor: pointer; }
    .brand-ico { width: 26px; height: 26px; fill: var(--text); flex: 0 0 auto; }
    .brand-name { font-weight: 800; font-size: 1rem; letter-spacing: -.01em; }
    .brand-toggle { margin-left: auto; flex: 0 0 auto; display: inline-flex; align-items: center;
      justify-content: center; color: var(--muted); cursor: pointer; padding: 2px; }
    .brand-toggle:hover { color: var(--text); }
    .brand-toggle .tg-ico { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2;
      stroke-linecap: round; stroke-linejoin: round; }
    .sidebar.collapsed .brand { justify-content: center; padding: 18px 0; }
    .sidebar.collapsed .brand-name, .sidebar.collapsed .brand-toggle { display: none; }
    .nav { display: flex; flex-direction: column; gap: 4px; padding: 14px 10px; }
    .nav-item { position: relative; display: flex; align-items: center; gap: 12px; padding: 11px 12px;
      color: var(--label); text-decoration: none; cursor: pointer; border: 1px solid transparent;
      white-space: nowrap; overflow: hidden; }
    .nav-item:hover { background: var(--panel-2); color: var(--text); }
    .nav-item.active { background: var(--panel-2); color: var(--text); border-color: var(--border); }
    .nav-item.active .nav-ico { stroke: var(--accent); }
    .nav-ico { width: 20px; height: 20px; flex: 0 0 auto; fill: none; stroke: currentColor; stroke-width: 2;
      stroke-linecap: round; stroke-linejoin: round; }
    .nav-label { font-size: .9rem; font-weight: 600; }
    .sidebar.collapsed .nav-item { justify-content: center; padding: 11px 0; }
    .sidebar.collapsed .nav-label { display: none; }
    /* Hover tooltip (title + description) shown only when collapsed. */
    .nav-tip { display: none; position: absolute; left: calc(100% + 12px); top: 50%; transform: translateY(-50%);
      width: 224px; background: var(--panel-2); border: 1px solid var(--border); padding: 9px 11px; z-index: 80;
      box-shadow: 0 8px 24px rgba(0, 0, 0, .55); }
    .nav-tip strong { display: block; font-size: .82rem; color: var(--text); margin-bottom: 3px; }
    .nav-tip em { display: block; font-style: normal; font-size: .74rem; color: var(--muted); line-height: 1.4;
      white-space: normal; }
    .sidebar.collapsed .nav-item:hover .nav-tip { display: block; }

    /* ----- Main column ----- */
    .main { flex: 1 1 auto; min-width: 0; }
    .main-head { position: sticky; top: 0; z-index: 30; background: var(--bg); }
    .topnav { position: relative; display: flex; align-items: center; justify-content: center; gap: 12px;
      padding: 16px 24px; border-bottom: 1px solid var(--border); }
    .topnav h1 { margin: 0; font-size: 1rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em;
      text-align: center; }
    .topnav .built { position: absolute; right: 24px; top: 50%; transform: translateY(-50%);
      color: var(--muted); font-size: .78rem; }
    .filters-bar { border-bottom: 1px solid var(--border); background: var(--bg); }
    .controls { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-end; gap: 12px;
      padding: 16px 24px; }
    .page-wrap { max-width: 1360px; margin: 0 auto; padding: 24px 24px 56px; }
    .page { display: none; }
    .page.active { display: block; }
    .field { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .field label { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--label); font-weight: 700; }
    select { appearance: none; background: var(--panel); color: var(--text);
      border: 1px solid var(--border); border-radius: 0; padding: 9px 36px 9px 14px; font-size: .9rem;
      font-family: inherit; cursor: pointer;
      background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2371767b' stroke-width='2'><path d='M6 9l6 6 6-6'/></svg>");
      background-repeat: no-repeat; background-position: right 12px center; }
    #query-select { min-width: 460px; max-width: 100%; }
    #window-select { min-width: 190px; }
    #tz-select { min-width: 240px; }
    select:focus { outline: none; border-color: var(--accent); }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 6px; }
    .kpis.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
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
    /* Top-3 visible, scrollable to 10 — with a discreet thin scrollbar. */
    .bar-list { display: flex; flex-direction: column; gap: 12px; max-height: 150px; overflow-y: auto;
      padding-right: 6px; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
    .bar-list::-webkit-scrollbar { width: 5px; }
    .bar-list::-webkit-scrollbar-thumb { background: var(--border); }
    .bar-list::-webkit-scrollbar-thumb:hover { background: var(--muted); }
    .bar-list::-webkit-scrollbar-track { background: transparent; }
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
    .section:first-child { margin-top: 0; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 0; padding: 16px; }
    .chart-legend { display: flex; flex-wrap: wrap; gap: 18px; margin-bottom: 14px; font-size: .76rem;
      color: var(--label); }
    .chart-legend .lg-item { display: inline-flex; align-items: center; gap: 8px; }
    .lg-swatch { width: 22px; height: 0; border-top: 2px solid var(--accent); display: inline-block; }
    .lg-prev .lg-swatch { border-top-style: dashed; border-top-color: var(--muted); }
    .chart-wrap { width: 100%; }
    svg.chart { width: 100%; height: 300px; display: block; overflow: visible; }
    text { fill: var(--muted); font-size: 11px; }
    .dt-toolbar { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center;
      justify-content: space-between; margin-bottom: 12px; }
    .dt-search { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 0;
      padding: 8px 12px; font-size: .85rem; min-width: 280px; }
    .dt-search:focus { outline: none; border-color: var(--accent); }
    .col-toggles { display: flex; flex-wrap: wrap; gap: 6px 14px; }
    .col-toggles label { display: inline-flex; align-items: center; gap: 6px; font-size: .74rem;
      color: var(--muted); cursor: pointer; }
    .dt-wrap { width: 100%; overflow-x: auto; max-height: 720px; overflow-y: auto;
      scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
    .dt-wrap::-webkit-scrollbar { width: 5px; height: 5px; }
    .dt-wrap::-webkit-scrollbar-thumb { background: var(--border); }
    .dt-wrap::-webkit-scrollbar-thumb:hover { background: var(--muted); }
    .dt-wrap::-webkit-scrollbar-track { background: transparent; }
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
    @media (max-width: 820px) {
      .kpis, .kpis.three { grid-template-columns: repeat(2, 1fr); }
      #query-select { min-width: 240px; } table.dt td.col-text { max-width: 280px; }
      .page-wrap, .topnav, .controls { padding-left: 16px; padding-right: 16px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar" id="sidebar">
      <div class="brand">
        <svg class="brand-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
        <span class="brand-name">X / Twitter</span>
        <span class="brand-toggle" id="sidebar-toggle" role="button" tabindex="0" aria-label="Toggle sidebar">
          <svg class="tg-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
        </span>
      </div>
      <nav class="nav">
        <a class="nav-item active" data-page="count" role="button" tabindex="0">
          <svg class="nav-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg>
          <span class="nav-label">Count Recent Tweets</span>
          <span class="nav-tip"><strong>Count Recent Tweets</strong><em>Post volume for the query — from the X recent-counts endpoint.</em></span>
        </a>
        <a class="nav-item" data-page="search" role="button" tabindex="0">
          <svg class="nav-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>
          <span class="nav-label">Search Recent Tweets</span>
          <span class="nav-tip"><strong>Search Recent Tweets</strong><em>Tweets ingested for the query — counts, coverage, authors and content.</em></span>
        </a>
      </nav>
    </aside>

    <div class="main">
      <div class="main-head">
        <div class="topnav">
          <h1 id="page-title">Count Recent Tweets</h1>
          <span class="built">Snapshot · __BUILT_AT__</span>
        </div>
        <div class="filters-bar">
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
      <div class="field">
        <label for="tz-select">Timezone</label>
        <select id="tz-select" aria-label="Timezone">
          <option value="UTC" selected>UTC — Coordinated Universal Time</option>
          <option value="Europe/Paris">CET — Central European Time</option>
          <option value="America/New_York">EST — Eastern Time (US)</option>
          <option value="America/Los_Angeles">PST — Pacific Time (US)</option>
        </select>
      </div>
          </div>
        </div>
      </div>

      <div class="page-wrap">
        <div class="page active" id="page-count" data-title="Count Recent Tweets">

    <div class="kpis">
      <div class="kpi"><div class="kpi-label">Total Tweets</div>
        <div class="kpi-value up"><span id="kpi-total">—</span><span id="kpi-total-delta" class="kpi-delta"></span></div>
        <div id="kpi-total-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label" id="kpi-mean-label">Mean / hour</div>
        <div class="kpi-value"><span id="kpi-mean">—</span><span id="kpi-mean-delta" class="kpi-delta"></span></div>
        <div id="kpi-mean-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">High</div><div id="kpi-top" class="kpi-value">—</div><div id="kpi-top-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">Low</div><div id="kpi-down" class="kpi-value">—</div><div id="kpi-down-hint" class="kpi-hint"></div></div>
    </div>

    <div class="section">
      <div class="section-head">
        <h2>Posts over time</h2>
        <p class="sub" id="chart-sub">Select a query to see its trend.</p>
      </div>
      <div class="card">
        <div class="chart-legend">
          <span class="lg-item"><span class="lg-swatch"></span>Current</span>
          <span class="lg-item lg-prev" id="legend-prev"><span class="lg-swatch"></span>Previous period</span>
        </div>
        <div class="chart-wrap"><svg id="chart" class="chart" role="img" aria-label="Posts over time"></svg></div>
      </div>
    </div>
        </div>

        <div class="page" id="page-search" data-title="Search Recent Tweets">

    <div class="kpis three">
      <div class="kpi"><div class="kpi-label">Total Tweets Ingested</div>
        <div class="kpi-value up"><span id="kpi-ingested">—</span><span id="kpi-ingested-delta" class="kpi-delta"></span></div>
        <div id="kpi-ingested-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">Coverage</div>
        <div class="kpi-value"><span id="kpi-coverage">—</span><span id="kpi-coverage-delta" class="kpi-delta"></span></div>
        <div id="kpi-coverage-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">Total Tweets</div>
        <div class="kpi-value up"><span id="kpi-stotal">—</span><span id="kpi-stotal-delta" class="kpi-delta"></span></div>
        <div id="kpi-stotal-hint" class="kpi-hint"></div></div>
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
      </div>
    </div>
  </div>

  <script id="series-data" type="application/json">__DATA_JSON__</script>
  <script>
  (() => {
    const SERIES = JSON.parse(document.getElementById("series-data").textContent);
    const bySlug = Object.fromEntries(SERIES.map((s) => [s.slug, s]));
    const querySel = document.getElementById("query-select");
    const windowSel = document.getElementById("window-select");
    const tzSel = document.getElementById("tz-select");
    const svg = document.getElementById("chart");
    const NS = "http://www.w3.org/2000/svg";
    // Display timezone (chart labels, table dates, daily bucketing). Absolute
    // filtering by the rolling window is unaffected — timezone is display-only.
    let currentTz = "UTC";

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
    function aggregateRange(buckets, fromMs, toMs, daily, tz) {
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
            { month: "short", day: "numeric", hour: "2-digit", timeZone: tz });
          const endLabel = end.toLocaleString(undefined, { hour: "2-digit", timeZone: tz });
          return { t: start, value: b.count, label, rangeLabel: label + " – " + endLabel };
        });
      }
      // Group by the calendar day *in the selected timezone*.
      const dayKey = (d) => new Intl.DateTimeFormat("en-CA",
        { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
      const byDay = new Map();
      for (const b of inRange) {
        const key = dayKey(parse(b.start));
        byDay.set(key, (byDay.get(key) || 0) + b.count);
      }
      return [...byDay.entries()].sort().map(([key, value]) => {
        // Format the key date itself at noon UTC (avoids any rollover), so the
        // label is exactly the tz-local day whatever the viewer's own timezone.
        const kd = new Date(key + "T12:00:00Z");
        const nd = new Date(kd.getTime() + 86400000);
        const label = kd.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
        const endLabel = nd.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
        return { t: kd, value, label, rangeLabel: label + " – " + endLabel };
      });
    }

    function setDelta(id, delta, decimals, suffix) {
      const e = document.getElementById(id);
      const r = decimals ? Math.round(delta * 10) / 10 : Math.round(delta);
      e.className = "kpi-delta " + (r > 0 ? "pos" : r < 0 ? "neg" : "flat");
      const num = r === 0 ? "±0"
        : (r > 0 ? "+" : "") + r.toLocaleString(undefined, { maximumFractionDigits: decimals ? 1 : 0 });
      e.textContent = num + (suffix || "");
    }
    function clearDelta(id) {
      const e = document.getElementById(id);
      e.className = "kpi-delta flat"; e.textContent = "";
    }
    // Search Recent Tweets KPIs: ingested tweets (comp vs scenario) and coverage
    // = ingested / total posts (count endpoint) as a %, with the comparison delta
    // expressed in percentage points.
    function setSearchKpis(curTweets, compTweets, curCount, compCount) {
      const curIng = curTweets.length, compIng = compTweets.length;
      // Total Tweets = the count-endpoint total for the window (same value as the
      // Count page KPI), replicated here as the coverage denominator.
      document.getElementById("kpi-stotal").textContent = fmt(curCount);
      setDelta("kpi-stotal-delta", curCount - compCount, false);
      document.getElementById("kpi-stotal-hint").textContent =
        compCount ? fmt(compCount) + " prev. period" : "no prior period";

      document.getElementById("kpi-ingested").textContent = fmt(curIng);
      setDelta("kpi-ingested-delta", curIng - compIng, false);
      document.getElementById("kpi-ingested-hint").textContent =
        (compIng || compCount) ? fmt(compIng) + " prev. period" : "no prior period";

      const curCov = curCount > 0 ? (100 * curIng) / curCount : null;
      const compCov = compCount > 0 ? (100 * compIng) / compCount : null;
      document.getElementById("kpi-coverage").textContent =
        curCov == null ? "—" : curCov.toFixed(1) + "%";
      if (curCov != null && compCov != null) {
        setDelta("kpi-coverage-delta", curCov - compCov, true, " pts");
      } else {
        clearDelta("kpi-coverage-delta");
      }
      document.getElementById("kpi-coverage-hint").textContent =
        curCov == null ? "no count data"
          : compCov != null ? compCov.toFixed(1) + "% prev. period" : "no prior period";
    }
    function resetSearchKpis() {
      document.getElementById("kpi-stotal").textContent = "—";
      document.getElementById("kpi-stotal-hint").textContent = "";
      clearDelta("kpi-stotal-delta");
      document.getElementById("kpi-ingested").textContent = "—";
      document.getElementById("kpi-ingested-hint").textContent = "";
      clearDelta("kpi-ingested-delta");
      document.getElementById("kpi-coverage").textContent = "—";
      document.getElementById("kpi-coverage-hint").textContent = "";
      clearDelta("kpi-coverage-delta");
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
      const H = 300, pad = { l: 48, r: 20, t: 16, b: 54 };
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

      // Cap how many x-labels we draw so wide labels never collide, and rotate
      // them so even the widest ("Jul 24, 02 PM") stay clear of each other.
      const labelEvery = Math.max(1, Math.ceil(n / (daily ? 14 : 12)));
      cur.forEach((p, i) => {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", xAt(i)); dot.setAttribute("cy", yAt(p.value));
        dot.setAttribute("r", daily ? 3 : 2.2); dot.setAttribute("fill", "#1d9bf0");
        const title = document.createElementNS(NS, "title");
        const cv = comp[i] ? comp[i].value : null;
        title.textContent = `${p.label}: ${fmt(p.value)} posts`
          + (cv != null ? ` (prev. ${fmt(cv)})` : "");
        dot.appendChild(title); svg.appendChild(dot);
        // Always label the last point; otherwise skip the penultimate slot so it
        // can't sit right on top of the (always-drawn) final label.
        const labelled = i === n - 1
          || (i % labelEvery === 0 && i < n - 1 - labelEvery / 2);
        if (labelled) {
          const lx = xAt(i), ly = H - pad.b + 15;
          const t = document.createElementNS(NS, "text");
          t.setAttribute("x", lx); t.setAttribute("y", ly);
          t.setAttribute("text-anchor", "end");
          t.setAttribute("transform", `rotate(-32 ${lx} ${ly})`);
          t.textContent = p.label;
          svg.appendChild(t);
        }
      });
    }

    // ----- Generic Excel-like data table -----------------------------------
    const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };
    const fmtDate = (iso) => new Date(iso).toLocaleString(undefined,
      { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: currentTz });
    const chartSub = document.getElementById("chart-sub");
    const legendPrev = document.getElementById("legend-prev");
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
      const tz = tzSel.value || "UTC";
      currentTz = tz;
      const now = Date.now();
      const win = hours * 3600 * 1000;
      // Comparison = the equal-length window immediately preceding the current one.
      const curFrom = now - win, curTo = now;
      const compFrom = now - 2 * win, compTo = now - win;
      if (!s) {
        setKpis([], [], false); draw([], [], false);
        resetSearchKpis();
        legendPrev.style.display = "none";
        chartSub.textContent = "";
        tweetsSub.textContent = "No followed queries yet";
        authorsSub.textContent = "";
        tweetsTable.setRows([]); authorsTable.setRows([]);
        renderBarList(barsAuthors, []); renderBarList(barsLocations, []);
        return;
      }
      const curPts = aggregateRange(s.buckets || [], curFrom, curTo, daily, tz);
      const compPts = aggregateRange(s.buckets || [], compFrom, compTo, daily, tz);
      const curCountTotal = curPts.reduce((a, p) => a + p.value, 0);
      const compCountTotal = compPts.reduce((a, p) => a + p.value, 0);
      chartSub.textContent = (daily ? "Per day" : "Per hour") + " · current vs previous period";
      legendPrev.style.display = compPts.length ? "inline-flex" : "none";
      setKpis(curPts, compPts, daily);
      draw(curPts, compPts, daily);

      const tweets = await ensureTweets(s.slug);
      if (tweets === null) {
        resetSearchKpis();
        tweetsSub.textContent = "Tweets unavailable";
        authorsSub.textContent = "";
        tweetsTable.setRows([]); authorsTable.setRows([]);
        renderBarList(barsAuthors, []); renderBarList(barsLocations, []);
        return;
      }
      const curTweets = tweetsBetween(tweets, curFrom, curTo);
      const compTweets = tweetsBetween(tweets, compFrom, compTo);
      setSearchKpis(curTweets, compTweets, curCountTotal, compCountTotal);

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

    // ----- Sidebar navigation + collapse -----------------------------------
    // Filters live in the sticky top bar and stay shared across pages; nav only
    // toggles which page is visible and updates the uppercase topnav title.
    const sidebar = document.getElementById("sidebar");
    const navItems = Array.from(document.querySelectorAll(".nav-item"));
    const pages = {
      count: document.getElementById("page-count"),
      search: document.getElementById("page-search"),
    };
    const pageTitle = document.getElementById("page-title");
    function showPage(key) {
      if (!pages[key]) return;
      navItems.forEach((n) => n.classList.toggle("active", n.dataset.page === key));
      let title = "";
      Object.entries(pages).forEach(([k, elx]) => {
        const on = k === key;
        elx.classList.toggle("active", on);
        if (on) title = elx.dataset.title || "";
      });
      pageTitle.textContent = title;
    }
    navItems.forEach((n) => {
      n.addEventListener("click", () => showPage(n.dataset.page));
      n.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); showPage(n.dataset.page); }
      });
    });

    // Collapse/expand by clicking the toggle icon, the brand, or empty sidebar
    // space — but never a nav item (those navigate, not toggle).
    sidebar.addEventListener("click", (ev) => {
      if (ev.target.closest(".nav-item")) return;
      sidebar.classList.toggle("collapsed");
    });
    document.getElementById("sidebar-toggle").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        sidebar.classList.toggle("collapsed");
      }
    });
    // Auto-collapse to the icon rail on narrow viewports.
    let autoCollapsed = false;
    function syncCollapse() {
      const narrow = window.innerWidth < 900;
      if (narrow && !autoCollapsed) { sidebar.classList.add("collapsed"); autoCollapsed = true; }
      else if (!narrow && autoCollapsed) { sidebar.classList.remove("collapsed"); autoCollapsed = false; }
    }
    syncCollapse();
    window.addEventListener("resize", syncCollapse);
    showPage("count");

    querySel.addEventListener("change", update);
    windowSel.addEventListener("change", update);
    tzSel.addEventListener("change", update);
    update();
  })();
  </script>
</body>
</html>"""
