"""Render the X Recent Tweets dashboard HTML (loads api JSON snapshots)."""

from __future__ import annotations

import html
from datetime import datetime


def render_index(built_at: datetime) -> str:
    built = html.escape(built_at.strftime("%Y-%m-%d %H:%M UTC"))
    return _INDEX_TEMPLATE.replace("__BUILT_AT__", built)


_INDEX_TEMPLATE = r"""<!doctype html>
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
    .sidebar { position: sticky; top: 0; height: 100vh; flex: 0 0 auto; width: 248px;
      background: var(--panel); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow: hidden; transition: width .18s ease; }
    .sidebar.collapsed { width: 64px; }
    .brand { display: flex; align-items: center; gap: 12px; padding: 18px; border-bottom: 1px solid var(--border);
      white-space: nowrap; overflow: hidden; cursor: pointer; }
    .brand-ico { width: 26px; height: 26px; fill: var(--text); flex: 0 0 auto; }
    .brand-name { font-weight: 800; font-size: 1rem; }
    .brand-toggle { margin-left: auto; color: var(--muted); }
    .sidebar.collapsed .brand-name, .sidebar.collapsed .brand-toggle, .sidebar.collapsed .nav-label { display: none; }
    .nav { display: flex; flex-direction: column; gap: 4px; padding: 14px 10px; }
    .nav-item { display: flex; align-items: center; gap: 12px; padding: 11px 12px;
      color: var(--label); cursor: pointer; border: 1px solid transparent; }
    .nav-item:hover, .nav-item.active { background: var(--panel-2); color: var(--text); }
    .nav-item.active { border-color: var(--border); }
    .nav-ico { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; }
    .main { flex: 1 1 auto; min-width: 0; }
    .main-head { position: sticky; top: 0; z-index: 30; background: var(--bg); }
    .topnav { position: relative; display: flex; align-items: center; justify-content: center;
      padding: 16px 24px; border-bottom: 1px solid var(--border); }
    .topnav h1 { margin: 0; font-size: 1rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }
    .topnav .built { position: absolute; right: 24px; color: var(--muted); font-size: .78rem; }
    .controls { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; padding: 16px 24px;
      border-bottom: 1px solid var(--border); }
    .field { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .field label { font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--label); font-weight: 700; }
    select { appearance: none; background: var(--panel); color: var(--text); border: 1px solid var(--border);
      border-radius: 0; padding: 9px 36px 9px 14px; font-size: .9rem; min-width: 200px; }
    #query-select { min-width: 420px; }
    .page-wrap { max-width: 1360px; margin: 0 auto; padding: 24px 24px 56px; }
    .page { display: none; } .page.active { display: block; }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .kpis.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .kpi { background: var(--panel); border: 1px solid var(--border); padding: 16px 18px; }
    .kpi-label { font-size: .72rem; color: var(--label); font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
    .kpi-value { margin-top: 6px; font-size: 1.7rem; font-weight: 800; }
    .kpi-value.up { color: var(--accent); }
    .kpi-hint { margin-top: 4px; font-size: .74rem; color: var(--muted); }
    .kpi-delta { margin-left: 8px; font-size: .95rem; font-weight: 700; }
    .kpi-delta.pos, .bl-delta.pos { color: #00ba7c; }
    .kpi-delta.neg, .bl-delta.neg { color: #f4212e; }
    .kpi-delta.flat, .bl-delta.flat { color: var(--muted); }
    .section { margin-top: 28px; }
    .section-head h2 { margin: 0; font-size: 1.05rem; font-weight: 700; }
    .section-head .sub { margin: 3px 0 0; font-size: .8rem; color: var(--muted); }
    .card { background: var(--panel); border: 1px solid var(--border); padding: 16px; }
    .kpi-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
    .kpi-chart { background: var(--panel); border: 1px solid var(--border); padding: 16px 18px; }
    .bar-list { display: flex; flex-direction: column; gap: 12px; max-height: 150px; overflow-y: auto; }
    .bar-row { display: grid; grid-template-columns: 1fr auto; gap: 5px 10px; }
    .bl-label { font-size: .82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bl-label a { color: var(--text); text-decoration: none; }
    .bl-value { font-size: .82rem; font-weight: 700; color: var(--muted); }
    .bl-delta { margin-left: 6px; font-size: .72rem; font-weight: 700; }
    .bl-track { grid-column: 1 / -1; height: 6px; background: var(--panel-2); }
    .bl-fill { height: 100%; background: var(--accent); }
    .bar-empty { color: var(--muted); font-size: .82rem; }
    svg.chart { width: 100%; height: 300px; display: block; overflow: visible; }
    text { fill: var(--muted); font-size: 11px; }
    .dt-toolbar { display: flex; flex-wrap: wrap; gap: 10px 16px; justify-content: space-between; margin-bottom: 12px; }
    .dt-search { background: var(--bg); color: var(--text); border: 1px solid var(--border);
      padding: 8px 12px; font-size: .85rem; min-width: 280px; }
    .dt-wrap { width: 100%; overflow: auto; max-height: 720px; }
    table.dt { width: 100%; border-collapse: collapse; font-size: .82rem; }
    table.dt th { position: sticky; top: 0; background: var(--panel-2); color: var(--label);
      text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border); font-size: .7rem;
      text-transform: uppercase; letter-spacing: .04em; }
    table.dt td { padding: 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    table.dt a { color: var(--accent); text-decoration: none; word-break: break-all; }
    table.dt td.empty { text-align: center; color: var(--muted); padding: 40px 10px; }
    .status { color: var(--muted); font-size: .85rem; padding: 24px; text-align: center; }
    @media (max-width: 820px) {
      .kpis, .kpis.three, .kpi-charts { grid-template-columns: 1fr 1fr; }
      #query-select { min-width: 240px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar" id="sidebar">
      <div class="brand">
        <svg class="brand-ico" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
        <span class="brand-name">X / Twitter</span>
        <span class="brand-toggle" id="sidebar-toggle">◂</span>
      </div>
      <nav class="nav">
        <a class="nav-item active" data-page="count">
          <svg class="nav-ico" viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg>
          <span class="nav-label">Count Recent Tweets</span>
        </a>
        <a class="nav-item" data-page="search">
          <svg class="nav-ico" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>
          <span class="nav-label">Search Recent Tweets</span>
        </a>
      </nav>
    </aside>
    <div class="main">
      <div class="main-head">
        <div class="topnav">
          <h1 id="page-title">Count Recent Tweets</h1>
          <span class="built">Snapshot · __BUILT_AT__</span>
        </div>
        <div class="controls">
          <div class="field"><label for="window-select">Scenario</label>
            <select id="window-select"></select></div>
          <div class="field"><label for="query-select">Query</label>
            <select id="query-select"></select></div>
          <div class="field"><label for="tz-select">Timezone</label>
            <select id="tz-select"></select></div>
        </div>
      </div>
      <div class="page-wrap">
        <div class="page active" id="page-count" data-title="Count Recent Tweets">
          <div class="kpis" id="count-kpis"></div>
          <div class="kpi-charts" style="margin-top:12px">
            <div class="kpi-chart"><div class="kpi-label">Top periods</div><div class="bar-list" id="count-bars"></div></div>
          </div>
          <div class="section">
            <div class="section-head"><h2>Posts over time</h2><p class="sub" id="count-chart-sub"></p></div>
            <div class="card"><svg id="count-chart" class="chart" role="img"></svg></div>
          </div>
        </div>
        <div class="page" id="page-search" data-title="Search Recent Tweets">
          <div class="kpis three" id="search-kpis"></div>
          <div class="kpi-charts">
            <div class="kpi-chart"><div class="kpi-label">Top authors</div><div class="bar-list" id="bars-authors"></div></div>
            <div class="kpi-chart"><div class="kpi-label">Top author locations</div><div class="bar-list" id="bars-locations"></div></div>
          </div>
          <div class="section">
            <div class="section-head"><h2>Ingested tweets over time</h2><p class="sub" id="search-chart-sub"></p></div>
            <div class="card"><svg id="search-chart" class="chart" role="img"></svg></div>
          </div>
          <div class="section">
            <div class="section-head"><h2>Tweets in range</h2><p class="sub" id="tweets-sub"></p></div>
            <div class="card"><div id="tweets-table"></div></div>
          </div>
          <div class="section">
            <div class="section-head"><h2>Top authors</h2><p class="sub" id="authors-sub"></p></div>
            <div class="card"><div id="authors-table"></div></div>
          </div>
        </div>
        <div class="status" id="boot-status">Loading snapshots…</div>
      </div>
    </div>
  </div>
  <script>
  (() => {
    const BASE = ".";
    const state = {
      scenarios: [], queries: [], timezones: [],
      count: { kpis: [], barcharts: [], linecharts: [] },
      search: { kpis: [], barcharts: [], linecharts: [], tables: [] },
      tz: "UTC",
    };
    const qs = (id) => document.getElementById(id);
    const fmt = (n) => (n == null || Number.isNaN(n)) ? "—" : Number(n).toLocaleString();
    const NS = "http://www.w3.org/2000/svg";

    async function loadJson(path) {
      const r = await fetch(BASE + "/" + path, { cache: "no-store" });
      if (!r.ok) throw new Error(path + " HTTP " + r.status);
      return r.json();
    }

    function fillSelect(sel, items, valueKey, labelKey, selected) {
      sel.innerHTML = "";
      items.forEach((it) => {
        const o = document.createElement("option");
        o.value = it[valueKey]; o.textContent = it[labelKey];
        if (it[valueKey] === selected) o.selected = true;
        sel.appendChild(o);
      });
    }

    function setDelta(el, delta, suffix) {
      if (!el) return;
      if (delta == null) { el.className = "kpi-delta flat"; el.textContent = ""; return; }
      const r = Math.round(delta * 10) / 10;
      el.className = "kpi-delta " + (r > 0 ? "pos" : r < 0 ? "neg" : "flat");
      el.textContent = (r === 0 ? "±0" : (r > 0 ? "+" : "") + r.toLocaleString()) + (suffix || "");
    }

    function renderKpis(host, items, { accentFirst } = {}) {
      host.innerHTML = "";
      (items || []).forEach((it, i) => {
        const box = document.createElement("div"); box.className = "kpi";
        const lab = document.createElement("div"); lab.className = "kpi-label"; lab.textContent = it.label;
        const val = document.createElement("div"); val.className = "kpi-value" + (accentFirst && i === 0 ? " up" : "");
        const num = document.createElement("span");
        const unit = it.unit === "%" ? "%" : "";
        num.textContent = it.value == null ? "—" : fmt(it.value) + unit;
        const delta = document.createElement("span");
        setDelta(delta, it.delta, it.unit === "%" ? " pts" : "");
        val.appendChild(num); val.appendChild(delta);
        const hint = document.createElement("div"); hint.className = "kpi-hint"; hint.textContent = it.hint || "";
        box.appendChild(lab); box.appendChild(val); box.appendChild(hint);
        host.appendChild(box);
      });
    }

    function renderBars(host, bars) {
      host.innerHTML = "";
      if (!bars || !bars.length) {
        const p = document.createElement("div"); p.className = "bar-empty"; p.textContent = "No data in range.";
        host.appendChild(p); return;
      }
      const max = Math.max(1, ...bars.map((b) => b.value || 0));
      bars.forEach((b) => {
        const row = document.createElement("div"); row.className = "bar-row";
        const lab = document.createElement("div"); lab.className = "bl-label";
        if (b.href) {
          const a = document.createElement("a"); a.href = b.href; a.target = "_blank"; a.rel = "noopener";
          a.textContent = b.label; lab.appendChild(a);
        } else lab.textContent = b.label;
        const val = document.createElement("div"); val.className = "bl-value"; val.textContent = fmt(b.value);
        if (typeof b.delta === "number") {
          const d = document.createElement("span");
          d.className = "bl-delta " + (b.delta > 0 ? "pos" : b.delta < 0 ? "neg" : "flat");
          d.textContent = b.delta === 0 ? "±0" : (b.delta > 0 ? "+" : "") + fmt(b.delta);
          val.appendChild(d);
        }
        const track = document.createElement("div"); track.className = "bl-track";
        const fill = document.createElement("div"); fill.className = "bl-fill";
        fill.style.width = (100 * (b.value || 0) / max) + "%";
        track.appendChild(fill);
        row.appendChild(lab); row.appendChild(val); row.appendChild(track);
        host.appendChild(row);
      });
    }

    function drawChart(svg, cur, prev) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const n = (cur || []).length;
      const W = Math.max(720, n * 12), H = 300, pad = { l: 48, r: 20, t: 16, b: 54 };
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      if (!n) {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", W / 2); t.setAttribute("y", H / 2); t.setAttribute("text-anchor", "middle");
        t.textContent = "No data in this range."; svg.appendChild(t); return;
      }
      const innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
      const maxV = Math.max(1, ...cur.map((p) => p.value), ...(prev || []).map((p) => p.value));
      const xAt = (i) => pad.l + (n > 1 ? (i * innerW) / (n - 1) : innerW / 2);
      const yAt = (v) => pad.t + innerH - (v / maxV) * innerH;
      [0, 0.5, 1].forEach((f) => {
        const v = Math.round(maxV * f), y = yAt(v);
        const line = document.createElementNS(NS, "line");
        line.setAttribute("x1", pad.l); line.setAttribute("x2", W - pad.r);
        line.setAttribute("y1", y); line.setAttribute("y2", y);
        line.setAttribute("stroke", "#2f3336"); svg.appendChild(line);
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", pad.l - 8); t.setAttribute("y", y + 4); t.setAttribute("text-anchor", "end");
        t.textContent = fmt(v); svg.appendChild(t);
      });
      if (prev && prev.length) {
        const cpath = prev.slice(0, n).map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`).join(" ");
        const cline = document.createElementNS(NS, "path");
        cline.setAttribute("d", cpath); cline.setAttribute("fill", "none");
        cline.setAttribute("stroke", "#71767b"); cline.setAttribute("stroke-width", "1.5");
        cline.setAttribute("stroke-dasharray", "4 4"); svg.appendChild(cline);
      }
      const path = cur.map((p, i) => `${i ? "L" : "M"} ${xAt(i)} ${yAt(p.value)}`).join(" ");
      const area = document.createElementNS(NS, "path");
      area.setAttribute("d", `${path} L ${xAt(n - 1)} ${pad.t + innerH} L ${xAt(0)} ${pad.t + innerH} Z`);
      area.setAttribute("fill", "#1d9bf0"); area.setAttribute("fill-opacity", "0.12"); svg.appendChild(area);
      const line = document.createElementNS(NS, "path");
      line.setAttribute("d", path); line.setAttribute("fill", "none");
      line.setAttribute("stroke", "#1d9bf0"); line.setAttribute("stroke-width", "2"); svg.appendChild(line);
      const every = Math.max(1, Math.ceil(n / 12));
      cur.forEach((p, i) => {
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", xAt(i)); dot.setAttribute("cy", yAt(p.value));
        dot.setAttribute("r", "2.2"); dot.setAttribute("fill", "#1d9bf0"); svg.appendChild(dot);
        if (i === n - 1 || i % every === 0) {
          const lx = xAt(i), ly = H - pad.b + 15;
          const t = document.createElementNS(NS, "text");
          t.setAttribute("x", lx); t.setAttribute("y", ly); t.setAttribute("text-anchor", "end");
          t.setAttribute("transform", `rotate(-32 ${lx} ${ly})`); t.textContent = p.label; svg.appendChild(t);
        }
      });
    }

    function renderTable(host, table) {
      host.innerHTML = "";
      const toolbar = document.createElement("div"); toolbar.className = "dt-toolbar";
      const search = document.createElement("input"); search.className = "dt-search";
      search.type = "search"; search.placeholder = "Search…";
      toolbar.appendChild(search); host.appendChild(toolbar);
      const wrap = document.createElement("div"); wrap.className = "dt-wrap"; host.appendChild(wrap);
      const columns = (table && table.columns) || [];
      let rows = (table && table.rows) || [];
      function draw() {
        const q = search.value.trim().toLowerCase();
        const view = !q ? rows : rows.filter((r) =>
          columns.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q)));
        const tableEl = document.createElement("table"); tableEl.className = "dt";
        const thead = document.createElement("thead"); const hr = document.createElement("tr");
        columns.forEach((c) => { const th = document.createElement("th"); th.textContent = c.label; hr.appendChild(th); });
        thead.appendChild(hr); tableEl.appendChild(thead);
        const tb = document.createElement("tbody");
        if (!view.length) {
          const tr = document.createElement("tr"); const td = document.createElement("td");
          td.className = "empty"; td.colSpan = Math.max(1, columns.length); td.textContent = "No rows.";
          tr.appendChild(td); tb.appendChild(tr);
        } else {
          view.slice(0, 200).forEach((r) => {
            const tr = document.createElement("tr");
            columns.forEach((c) => {
              const td = document.createElement("td");
              const v = r[c.key];
              if (c.key === "url" && v) {
                const a = document.createElement("a"); a.href = v; a.target = "_blank"; a.rel = "noopener";
                a.textContent = v; td.appendChild(a);
              } else if (c.key === "username" && v && v !== "—") {
                const a = document.createElement("a"); a.href = "https://x.com/" + v; a.target = "_blank";
                a.rel = "noopener"; a.textContent = "@" + v; td.appendChild(a);
              } else if (c.key === "created_at" && v) {
                td.textContent = new Date(v).toLocaleString(undefined, { timeZone: state.tz });
              } else td.textContent = v == null || v === "" ? "—" : String(v);
              tr.appendChild(td);
            });
            tb.appendChild(tr);
          });
        }
        tableEl.appendChild(tb); wrap.innerHTML = ""; wrap.appendChild(tableEl);
      }
      search.addEventListener("input", draw); draw();
    }

    function pick(list, slug, scenarioId, key) {
      return (list || []).find((x) => x.query_slug === slug && x.scenario_id === scenarioId) || null;
    }

    function update() {
      const slug = qs("query-select").value;
      const scenarioId = qs("window-select").value;
      state.tz = qs("tz-select").value || "UTC";
      if (!slug || !scenarioId) return;

      const ck = pick(state.count.kpis, slug, scenarioId);
      renderKpis(qs("count-kpis"), ck ? ck.items : [], { accentFirst: true });
      const cb = pick(state.count.barcharts, slug, scenarioId);
      const topBars = (cb && cb.items && cb.items[0] && cb.items[0].bars) || [];
      renderBars(qs("count-bars"), topBars);
      const cl = pick(state.count.linecharts, slug, scenarioId);
      const cCur = (cl && cl.series && cl.series.find((s) => s.id === "current") || {}).points || [];
      const cPrev = (cl && cl.series && cl.series.find((s) => s.id === "previous") || {}).points || [];
      qs("count-chart-sub").textContent = (cl && cl.granularity === "day" ? "Per day" : "Per hour")
        + " · current vs previous period";
      drawChart(qs("count-chart"), cCur, cPrev);

      const sk = pick(state.search.kpis, slug, scenarioId);
      renderKpis(qs("search-kpis"), sk ? sk.items : [], { accentFirst: true });
      const sb = pick(state.search.barcharts, slug, scenarioId);
      const authors = ((sb && sb.items) || []).find((i) => i.id === "top_authors");
      const locs = ((sb && sb.items) || []).find((i) => i.id === "top_locations");
      renderBars(qs("bars-authors"), authors ? authors.bars : []);
      renderBars(qs("bars-locations"), locs ? locs.bars : []);
      const sl = pick(state.search.linecharts, slug, scenarioId);
      const sCur = (sl && sl.series && sl.series.find((s) => s.id === "current") || {}).points || [];
      const sPrev = (sl && sl.series && sl.series.find((s) => s.id === "previous") || {}).points || [];
      qs("search-chart-sub").textContent = (sl && sl.granularity === "day" ? "Per day" : "Per hour")
        + " · ingested tweets (capped)";
      drawChart(qs("search-chart"), sCur, sPrev);

      const tweets = (state.search.tables || []).find(
        (t) => t.id === "tweets" && t.query_slug === slug && t.scenario_id === scenarioId);
      const authorsT = (state.search.tables || []).find(
        (t) => t.id === "authors" && t.query_slug === slug && t.scenario_id === scenarioId);
      qs("tweets-sub").textContent = tweets ? (tweets.rows || []).length + " tweet(s) in range" : "";
      qs("authors-sub").textContent = authorsT ? (authorsT.rows || []).length + " author(s) in range" : "";
      renderTable(qs("tweets-table"), tweets);
      renderTable(qs("authors-table"), authorsT);
    }

    function showPage(key) {
      document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === key));
      ["count", "search"].forEach((k) => {
        const el = qs("page-" + k);
        const on = k === key;
        el.classList.toggle("active", on);
        if (on) qs("page-title").textContent = el.dataset.title;
      });
    }

    async function boot() {
      try {
        const [scenarios, queries, timezone, cKpis, cBars, cLines, sKpis, sBars, sLines, sTables] =
          await Promise.all([
            loadJson("globals/scenarios.json"),
            loadJson("globals/queries.json"),
            loadJson("globals/timezone.json"),
            loadJson("count_recent_tweets/kpis.json"),
            loadJson("count_recent_tweets/barcharts.json"),
            loadJson("count_recent_tweets/linecharts.json"),
            loadJson("search_recents_tweets/kpis.json"),
            loadJson("search_recents_tweets/barcharts.json"),
            loadJson("search_recents_tweets/linecharts.json"),
            loadJson("search_recents_tweets/tables.json"),
          ]);
        state.scenarios = scenarios.scenarios || [];
        state.queries = queries.queries || [];
        state.timezones = timezone.timezones || [];
        state.count = { kpis: cKpis.kpis || [], barcharts: cBars.barcharts || [], linecharts: cLines.linecharts || [] };
        state.search = {
          kpis: sKpis.kpis || [], barcharts: sBars.barcharts || [],
          linecharts: sLines.linecharts || [], tables: sTables.tables || [],
        };
        fillSelect(qs("window-select"), state.scenarios, "id", "label", state.scenarios[0] && state.scenarios[0].id);
        fillSelect(qs("query-select"), state.queries, "slug", "query", state.queries[0] && state.queries[0].slug);
        fillSelect(qs("tz-select"), state.timezones, "id", "label", timezone.default || "UTC");
        qs("boot-status").style.display = "none";
        update();
      } catch (e) {
        qs("boot-status").textContent = "Failed to load snapshots: " + e.message
          + ". Run the X app build to publish JSON under x/apps/x/.";
      }
    }

    document.querySelectorAll(".nav-item").forEach((n) => n.addEventListener("click", () => showPage(n.dataset.page)));
    qs("sidebar").addEventListener("click", (ev) => {
      if (ev.target.closest(".nav-item")) return;
      qs("sidebar").classList.toggle("collapsed");
    });
    ["window-select", "query-select", "tz-select"].forEach((id) => qs(id).addEventListener("change", update));
    showPage("count");
    boot();
  })();
  </script>
</body>
</html>
"""
