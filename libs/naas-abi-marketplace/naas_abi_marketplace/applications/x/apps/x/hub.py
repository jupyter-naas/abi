"""Build the X "Post Count Following" app from the recent-posts count graph.

Runs the count SPARQL queries against
``GRAPH <http://ontology.naas.ai/graph/x_recent_posts_count>`` and publishes,
under ``x/apps/x/`` in object storage:

* ``data/catalog.json``      — the list of followed queries (dropdown 1)
* ``data/<slug>.json``       — the hourly time series for one followed query
* ``index.html``             — the self-contained dashboard (X/Twitter theme)

The dashboard embeds a compact copy of every series so it renders with no
network round-trip, and also fetches the JSON snapshots so they are reusable by
other consumers (and the X agent). Mirrors the counter_uas report-hub pattern:
the build only writes object storage; catalog serving reads it back.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.StorageUtils import StorageUtils

DEFAULT_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
DEFAULT_NAMESPACE = "http://ontology.naas.ai/x/"
DEFAULT_APP_PREFIX = "x/apps/x"
APP_HTML_DATA_BASE = "/app-html/x/apps/x/data"


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
        namespace: str = DEFAULT_NAMESPACE,
        app_prefix: str = DEFAULT_APP_PREFIX,
    ) -> None:
        self._object_storage = object_storage_service
        self._triple_store = triple_store
        self._storage = StorageUtils(object_storage_service)
        self.graph_name = graph_name
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

    # ----- Publish ----------------------------------------------------------

    def publish(self, queries: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Publish the dashboard + snapshots for the given followed *queries*.

        Each entry is ``{"name"?, "query", "label"?}``. Returns a summary dict.
        """
        built_at = datetime.now(timezone.utc)
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
            catalog.append(
                {
                    "slug": slug,
                    "query": query_string,
                    "label": label,
                    "total": total,
                    "buckets": len(buckets),
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
  <title>X · Post Count Following</title>
  <style>
    :root {
      --bg: #000000; --panel: #16181c; --panel-2: #1d1f23; --border: #2f3336;
      --text: #e7e9ea; --muted: #71767b; --accent: #1d9bf0; --accent-dim: #113a56;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .shell { max-width: 1120px; margin: 0 auto; padding: 24px 20px 48px; }
    header { display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border);
      padding-bottom: 16px; margin-bottom: 20px; }
    .logo { width: 30px; height: 30px; fill: var(--text); flex: 0 0 auto; }
    h1 { margin: 0; font-size: 1.25rem; font-weight: 800; letter-spacing: -.01em; }
    .built { margin-left: auto; color: var(--muted); font-size: .78rem; }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 22px; }
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field label { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
    select { appearance: none; background: var(--panel); color: var(--text);
      border: 1px solid var(--border); border-radius: 9999px; padding: 9px 36px 9px 16px; font-size: .9rem;
      font-family: inherit; cursor: pointer; min-width: 220px;
      background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2371767b' stroke-width='2'><path d='M6 9l6 6 6-6'/></svg>");
      background-repeat: no-repeat; background-position: right 12px center; }
    select:focus { outline: none; border-color: var(--accent); }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 24px; }
    .kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px; }
    .kpi-label { font-size: .72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .kpi-value { margin-top: 6px; font-size: 1.7rem; font-weight: 800; line-height: 1.1; letter-spacing: -.02em; }
    .kpi-hint { margin-top: 4px; font-size: .74rem; color: var(--muted); }
    .kpi-value.up { color: var(--accent); }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 18px 18px 8px; }
    .card h2 { margin: 0 0 2px; font-size: 1rem; font-weight: 700; }
    .card .sub { margin: 0 0 8px; font-size: .78rem; color: var(--muted); }
    .chart-wrap { width: 100%; overflow-x: auto; }
    svg.chart { width: 100%; height: 300px; display: block; }
    .empty { padding: 60px 12px; text-align: center; color: var(--muted); font-size: .9rem; }
    .tip { fill: var(--panel-2); stroke: var(--border); }
    text { fill: var(--muted); font-size: 11px; }
    text.tipval { fill: var(--text); font-weight: 700; }
    @media (max-width: 720px) { .kpis { grid-template-columns: repeat(2, 1fr); } select { min-width: 160px; } }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <svg class="logo" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
      <h1>Post Count Following</h1>
      <span class="built">Snapshot · __BUILT_AT__</span>
    </header>

    <div class="controls">
      <div class="field">
        <label for="query-select">Query</label>
        <select id="query-select" aria-label="Followed query"></select>
      </div>
      <div class="field">
        <label for="window-select">Time range</label>
        <select id="window-select" aria-label="Time range">
          <option value="24">Last 24 hours</option>
          <option value="48">Last 48 hours</option>
          <option value="168" selected>Last 7 days</option>
          <option value="720">Last 30 days</option>
        </select>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="kpi-label">Total posts</div><div id="kpi-total" class="kpi-value up">—</div><div id="kpi-total-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label" id="kpi-mean-label">Mean / hour</div><div id="kpi-mean" class="kpi-value">—</div><div class="kpi-hint">average per period</div></div>
      <div class="kpi"><div class="kpi-label">Peak</div><div id="kpi-top" class="kpi-value">—</div><div id="kpi-top-hint" class="kpi-hint"></div></div>
      <div class="kpi"><div class="kpi-label">Lowest</div><div id="kpi-down" class="kpi-value">—</div><div id="kpi-down-hint" class="kpi-hint"></div></div>
    </div>

    <div class="card">
      <h2 id="chart-title">Posts over time</h2>
      <p class="sub" id="chart-sub">Select a query to see its trend.</p>
      <div class="chart-wrap"><svg id="chart" class="chart" role="img" aria-label="Posts over time"></svg></div>
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
      opt.textContent = s.label;
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

    function aggregate(buckets, hours) {
      const cutoff = Date.now() - hours * 3600 * 1000;
      const inWindow = buckets.filter((b) => parse(b.start).getTime() >= cutoff);
      const daily = hours > 48;
      if (!daily) {
        return {
          daily,
          points: inWindow.map((b) => ({
            t: parse(b.start),
            value: b.count,
            label: parse(b.start).toLocaleString(undefined,
              { month: "short", day: "numeric", hour: "2-digit" }),
          })),
        };
      }
      const byDay = new Map();
      for (const b of inWindow) {
        const d = parse(b.start);
        const key = d.toISOString().slice(0, 10);
        byDay.set(key, (byDay.get(key) || 0) + b.count);
      }
      const points = [...byDay.entries()].sort().map(([key, value]) => ({
        t: new Date(key + "T00:00:00Z"),
        value,
        label: new Date(key + "T00:00:00Z").toLocaleDateString(undefined,
          { month: "short", day: "numeric" }),
      }));
      return { daily, points };
    }

    function setKpis(points, daily) {
      const values = points.map((p) => p.value);
      const total = values.reduce((a, b) => a + b, 0);
      const mean = values.length ? total / values.length : 0;
      document.getElementById("kpi-total").textContent = fmt(total);
      document.getElementById("kpi-total-hint").textContent =
        points.length + (daily ? " day(s)" : " hour(s)");
      document.getElementById("kpi-mean-label").textContent = daily ? "Mean / day" : "Mean / hour";
      document.getElementById("kpi-mean").textContent =
        mean.toLocaleString(undefined, { maximumFractionDigits: 1 });
      const top = points.reduce((a, b) => (b.value > (a?.value ?? -1) ? b : a), null);
      const down = points.reduce((a, b) => (b.value < (a?.value ?? Infinity) ? b : a), null);
      document.getElementById("kpi-top").textContent = top ? fmt(top.value) : "—";
      document.getElementById("kpi-top-hint").textContent = top ? top.label : "";
      document.getElementById("kpi-down").textContent = down ? fmt(down.value) : "—";
      document.getElementById("kpi-down-hint").textContent = down ? down.label : "";
    }

    function draw(points, daily) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const W = Math.max(720, points.length * (daily ? 34 : 12));
      const H = 300, pad = { l: 44, r: 16, t: 16, b: 40 };
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      if (!points.length) {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", W / 2); t.setAttribute("y", H / 2);
        t.setAttribute("text-anchor", "middle");
        t.textContent = "No data in this range.";
        svg.appendChild(t); return;
      }
      const innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
      const maxV = Math.max(1, ...points.map((p) => p.value));
      const xAt = (i) => pad.l + (points.length > 1 ? (i * innerW) / (points.length - 1) : innerW / 2);
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

      const path = points.map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`).join(" ");
      const area = document.createElementNS(NS, "path");
      area.setAttribute("d", `${path} L ${xAt(points.length - 1)} ${pad.t + innerH} L ${xAt(0)} ${pad.t + innerH} Z`);
      area.setAttribute("fill", "#1d9bf0"); area.setAttribute("fill-opacity", "0.12");
      svg.appendChild(area);
      const line = document.createElementNS(NS, "path");
      line.setAttribute("d", path); line.setAttribute("fill", "none");
      line.setAttribute("stroke", "#1d9bf0"); line.setAttribute("stroke-width", "2");
      line.setAttribute("stroke-linejoin", "round"); line.setAttribute("stroke-linecap", "round");
      svg.appendChild(line);

      const labelEvery = Math.ceil(points.length / (daily ? 12 : 8));
      points.forEach((p, i) => {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", xAt(i)); dot.setAttribute("cy", yAt(p.value));
        dot.setAttribute("r", daily ? 3 : 2.2); dot.setAttribute("fill", "#1d9bf0");
        const title = document.createElementNS(NS, "title");
        title.textContent = `${p.label}: ${fmt(p.value)} posts`;
        dot.appendChild(title); svg.appendChild(dot);
        if (i % labelEvery === 0 || i === points.length - 1) {
          const t = document.createElementNS(NS, "text");
          t.setAttribute("x", xAt(i)); t.setAttribute("y", H - pad.b + 20);
          t.setAttribute("text-anchor", "middle"); t.textContent = p.label;
          svg.appendChild(t);
        }
      });
    }

    function update() {
      const s = bySlug[querySel.value];
      const hours = Number(windowSel.value);
      if (!s) { setKpis([], false); draw([], false); return; }
      const { points, daily } = aggregate(s.buckets || [], hours);
      document.getElementById("chart-title").textContent = "Posts over time";
      document.getElementById("chart-sub").textContent =
        s.query + " · " + (daily ? "per day" : "per hour");
      setKpis(points, daily);
      draw(points, daily);
    }

    querySel.addEventListener("change", update);
    windowSel.addEventListener("change", update);
    update();
  })();
  </script>
</body>
</html>"""
