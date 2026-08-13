import { mountProcessesPage } from "./processes.js";
import { mountGraphPage } from "./graph.js";

const API = "/api/personnel-cockpit";
const ENTITY = "_demo";
const ORG_KEY = "cockpit-org-filter";
const RAIL_KEY = "cockpit-rail-collapsed";
const PAGE_KEY = "cockpit-page";

let currentEntity = localStorage.getItem(ORG_KEY) || ENTITY;
let currentPageId = "workforce";

const APP_NAME = "Personnel Cockpit";
const BANNER_DISMISS_KEY = "cockpit-banner-dismissed";

const BANNER_ICONS = {
  info: 'M11.25 11.25h.75v4.5h.75M12 8.25h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  warning:
    'M12 9v3.75m0 3.75h.008M10.363 3.591 2.257 17.727A1.5 1.5 0 0 0 3.557 20h16.886a1.5 1.5 0 0 0 1.3-2.273L13.637 3.591a1.5 1.5 0 0 0-2.274 0Z',
  error:
    'M12 9v3.75m0 3.75h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
};

const PAGES = {
  workforce: {
    title: "Workforce",
    banner: {
      type: "info",
      enabled: true,
      text: "Demo roster from the personnel graph — headcount, status mix, and age pyramid.",
    },
  },
  graph: {
    title: "Graph",
    banner: {
      type: "info",
      enabled: true,
      text: "Search a person, then set distance 1–3: birth and working hubs at d=1, declarant at d=2, linked people at d=3.",
    },
  },
  logs: {
    title: "Logs",
    banner: {
      type: "info",
      enabled: true,
      text: "Each card is one ledger entry. Rows are facts in subject → property → object form, with URI-only types and properties. The header summarizes who registered what, in plain language.",
    },
  },
  processes: {
    title: "Processes",
    banner: {
      type: "info",
      enabled: true,
      text: "Birth and Working processes mapped to the BFO 7 buckets. Employment continuants remain in PersonnelOntology for HR records.",
    },
  },
};

function setRailCollapsed(collapsed) {
  const shell = document.querySelector(".shell");
  const toggle = document.getElementById("rail-toggle");
  shell.classList.toggle("rail-collapsed", collapsed);
  toggle.hidden = collapsed;
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.setAttribute("aria-label", "Collapse sidebar");
  toggle.title = "Collapse sidebar";
  localStorage.setItem(RAIL_KEY, collapsed ? "1" : "0");
}

function dismissedBanners() {
  try {
    return JSON.parse(sessionStorage.getItem(BANNER_DISMISS_KEY) || "{}");
  } catch {
    return {};
  }
}

function dismissBanner(pageId) {
  const map = dismissedBanners();
  map[pageId] = true;
  sessionStorage.setItem(BANNER_DISMISS_KEY, JSON.stringify(map));
  const el = document.getElementById("page-banner");
  el.hidden = true;
  el.dataset.page = "";
}

function showPageBanner(pageId) {
  const el = document.getElementById("page-banner");
  const cfg = PAGES[pageId]?.banner;
  if (!cfg?.enabled || !cfg.text?.trim() || dismissedBanners()[pageId]) {
    el.hidden = true;
    el.dataset.page = "";
    return;
  }
  const type = ["info", "warning", "error"].includes(cfg.type) ? cfg.type : "info";
  el.hidden = false;
  el.dataset.page = pageId;
  el.dataset.type = type;
  el.className = `page-banner type-${type}`;
  el.title = "Click to dismiss";
  document.getElementById("page-banner-text").textContent = cfg.text;
  document.getElementById("page-banner-icon").innerHTML =
    `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="${BANNER_ICONS[type]}" /></svg>`;
}

async function loadJson(rel) {
  const res = await fetch(`${API}/entities/${currentEntity}/${rel}`);
  if (!res.ok) throw new Error(`${rel} → ${res.status}`);
  return res.json();
}

async function loadGlobal(name) {
  const res = await fetch(`${API}/globals/${name}`);
  if (!res.ok) throw new Error(`globals/${name} → ${res.status}`);
  return res.json();
}

function formatPublishedAt(value) {
  const dateTime = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(value);
  if (dateTime) {
    const [, y, mo, d, h, mi] = dateTime;
    const dt = new Date(Date.UTC(+y, +mo - 1, +d, +h, +mi));
    return `${dt.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })}, ${dt.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    })} UTC`;
  }
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, y, mo, d] = dateOnly;
    const dt = new Date(Date.UTC(+y, +mo - 1, +d));
    return dt.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  return value;
}

async function loadLatestPublishedAt() {
  const manifest = await loadJson("manifest.json");
  let latest = manifest.data_version || null;
  const pages = manifest.datasets?.pages || {};
  for (const rels of Object.values(pages)) {
    for (const rel of rels) {
      try {
        const data = await loadJson(rel);
        const version = data.data_version;
        if (version && (!latest || version > latest)) latest = version;
      } catch {
        // ignore missing datasets
      }
    }
  }
  return latest;
}

async function mountOrgFilter() {
  const select = document.getElementById("org-filter");
  if (!select) return;
  try {
    const data = await loadGlobal("organizations.json");
    const orgs = data.organizations || [];
    select.innerHTML = orgs
      .map(
        (org) =>
          `<option value="${org.entity_id}">${org.label || org.organizationLabel || org.entity_id}</option>`
      )
      .join("");
    const stored = localStorage.getItem(ORG_KEY);
    if (stored && orgs.some((org) => org.entity_id === stored)) {
      select.value = stored;
      currentEntity = stored;
    } else {
      select.value = ENTITY;
      currentEntity = ENTITY;
    }
    select.addEventListener("change", () => {
      currentEntity = select.value || ENTITY;
      localStorage.setItem(ORG_KEY, currentEntity);
      showPage(currentPageId);
    });
  } catch {
    select.innerHTML = `<option value="${ENTITY}">Naas.ai</option>`;
    select.value = ENTITY;
  }
}

async function mountRailPublished() {
  const el = document.getElementById("rail-published");
  if (!el) return;
  try {
    const publishedAt = await loadLatestPublishedAt();
    el.textContent = publishedAt
      ? `Published ${formatPublishedAt(publishedAt)}`
      : "Publication time unavailable";
  } catch {
    el.textContent = "Publication time unavailable";
  }
}

function chip(status) {
  const cls =
    status === "active" ? "" : status === "on-leave" || status === "notice-period" ? "warn" : "muted";
  return `<span class="chip ${cls}">${status}</span>`;
}

function renderBars(rows, labelKey, valueKey) {
  const max = Math.max(...rows.map((r) => r[valueKey]), 1);
  return `<div class="bars">${rows
    .map(
      (r) => `
      <div class="bar-row">
        <span>${r[labelKey]}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${(100 * r[valueKey]) / max}%"></div></div>
        <strong>${r[valueKey]}</strong>
      </div>`
    )
    .join("")}</div>`;
}

function renderPyramid(rows) {
  const max = Math.max(...rows.flatMap((r) => [r.Male || 0, r.Female || 0]), 1);
  return `<div class="pyramid">${rows
    .map((r) => {
      const m = r.Male || 0;
      const f = r.Female || 0;
      return `<div class="pyramid-row">
        <span>${r.band}</span>
        <div class="pyramid-pair">
          <div class="pyramid-male" style="width:${(100 * m) / max}%" title="Male ${m}"></div>
          <div class="pyramid-female" style="width:${(100 * f) / max}%" title="Female ${f}"></div>
        </div>
        <span>${m} · ${f}</span>
      </div>`;
    })
    .join("")}</div>
    <p style="margin:0.7rem 0 0;font-size:0.75rem;color:var(--muted)">Left = Male · Right = Female</p>`;
}

async function renderWorkforce(el) {
  const [kpis, roster, families, status, pyramid] = await Promise.all([
    loadJson("workforce/kpis.json"),
    loadJson("workforce/roster.json"),
    loadJson("workforce/by_job_family.json"),
    loadJson("workforce/status_mix.json"),
    loadJson("workforce/age_pyramid.json"),
  ]);
  const k = kpis.kpis;
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi"><span>Active headcount</span><strong>${k.active_headcount.value}</strong></div>
      <div class="kpi"><span>On leave</span><strong>${k.on_leave.value}</strong></div>
      <div class="kpi"><span>Notice period</span><strong>${k.notice_period.value}</strong></div>
      <div class="kpi"><span>Open roles</span><strong>${k.open_roles.value}</strong></div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <h2>Headcount by job family</h2>
        ${renderBars(families.records, "jobFamily", "headcount")}
      </div>
      <div class="panel">
        <h2>Age pyramid</h2>
        ${renderPyramid(pyramid.records)}
      </div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <h2>Status mix</h2>
        ${renderBars(status.records, "status_value", "count")}
      </div>
      <div class="panel">
        <h2>Roster</h2>
        <table>
          <thead><tr><th>Name</th><th>Title</th><th>Family</th><th>Status</th></tr></thead>
          <tbody>
            ${roster.records
              .map(
                (r) => `<tr>
                <td>${r.personLabel}<br><small style="color:var(--muted)">${r.employee_id}</small></td>
                <td>${r.job_title}</td>
                <td>${r.job_family}</td>
                <td>${chip(r.status_value)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
    <div class="agent-q"><strong>Ask PersonnelAgent:</strong> “Who is on leave?” · “How is headcount split by job family?” · “Tell me about employee E-10428.”</div>
  `;
}

async function renderLogs(el) {
  const ledger = await loadJson("logs/ledger.json");
  const entries = ledger.records || [];

  const uriCell = (value) => {
    const text = value || "—";
    return `<td class="ledger-uri" title="${text}">${text}</td>`;
  };

  const cards = entries
    .map((entry) => {
      const triples = (entry.triples || entry.assertions || [])
        .map((t) => {
          const object = t.object ?? t.value_uri ?? t.value ?? "—";
          const predicate = t.predicate_uri ?? t.prop_uri ?? t.relation_uri ?? "—";
          const predicateType = t.predicate_type_uri ?? t.prop_type ?? "—";
          const objectType = t.object_type_uri ?? "—";
          const source = t.source_uri || entry.source_uri || "—";
          const timestamp = t.source_at || t.ledger_at || entry.source_at || entry.ledger_at || "—";
          return `<tr>
            ${uriCell(t.subject_uri)}
            ${uriCell(t.subject_type_uri)}
            ${uriCell(predicate)}
            ${uriCell(predicateType)}
            ${uriCell(object)}
            ${uriCell(objectType)}
            ${uriCell(source)}
            <td class="ledger-when" title="${timestamp}">${timestamp}</td>
          </tr>`;
        })
        .join("");

      return `<article class="ledger-entry">
        <header class="ledger-entry-head">
          <div class="ledger-entry-title">
            <span class="ledger-process">${entry.person_label || "Registration"}</span>
            <span class="ledger-class">${entry.process_uri || entry.process_id || "—"}</span>
          </div>
          <dl class="ledger-meta">
            <div><dt>Source at</dt><dd class="ledger-when">${entry.source_at || entry.ledger_at || "—"}</dd></div>
            <div><dt>Declarant</dt><dd>${entry.declarant_label || "—"}</dd></div>
            <div><dt>Birth</dt><dd class="ledger-uri">${entry.birth_uri || entry.registers_birth || "—"}</dd></div>
            <div><dt>Source</dt><dd class="ledger-uri">${entry.source_uri || entry.source_id || "—"}</dd></div>
          </dl>
          ${entry.declared_content ? `<p class="ledger-quote">${entry.declared_content}</p>` : ""}
        </header>
        <div class="ledger-scroll">
          <table class="ledger-table ledger-assertions">
            <thead><tr>
              <th>Subject</th>
              <th>Subject type</th>
              <th>Predicate</th>
              <th>Predicate type</th>
              <th>Object</th>
              <th>Object type</th>
              <th>Source</th>
              <th>Timestamp</th>
            </tr></thead>
            <tbody>${triples || `<tr><td colspan="8" class="muted">No facts recorded</td></tr>`}</tbody>
          </table>
        </div>
      </article>`;
    })
    .join("");

  el.innerHTML = `
    <div class="ledger-stack">${cards}</div>
    <div class="agent-q"><strong>Ask PersonnelAgent:</strong> “List birth registrations.” · “Reconstruct Emma Petit’s registration lineage.”</div>
  `;
}

let disposeGraph = null;
let disposeProcesses = null;

async function renderGraph(el) {
  if (disposeGraph) {
    disposeGraph();
    disposeGraph = null;
  }
  const data = await loadJson("graph/index.json");
  disposeGraph = mountGraphPage(el, data);
}


async function renderProcesses(el) {
  if (disposeProcesses) {
    disposeProcesses();
    disposeProcesses = null;
  }
  const data = await loadJson("processes/processes.json");
  disposeProcesses = mountProcessesPage(el, data);
}

const RENDERERS = {
  workforce: renderWorkforce,
  graph: renderGraph,
  logs: renderLogs,
  processes: renderProcesses,
};

function resolveStoredPageId() {
  const stored = localStorage.getItem(PAGE_KEY);
  if (stored && PAGES[stored]) return stored;
  return "workforce";
}

async function showPage(pageId) {
  if (!PAGES[pageId]) pageId = "workforce";
  currentPageId = pageId;
  localStorage.setItem(PAGE_KEY, pageId);
  if (pageId !== "graph" && disposeGraph) {
    disposeGraph();
    disposeGraph = null;
  }
  if (pageId !== "processes" && disposeProcesses) {
    disposeProcesses();
    disposeProcesses = null;
  }
  document.querySelectorAll("#nav button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === pageId);
  });
  document.querySelectorAll(".page").forEach((p) => {
    p.classList.toggle("active", p.id === `page-${pageId}`);
  });
  const title = PAGES[pageId].title;
  document.getElementById("topbar-title").textContent = title;
  document.title = `${title} | ${APP_NAME}`;
  showPageBanner(pageId);
  const el = document.getElementById(`page-${pageId}`);
  el.innerHTML = `<p style="color:var(--muted)">Loading…</p>`;
  try {
    await RENDERERS[pageId](el);
  } catch (err) {
    el.innerHTML = `<p class="load-error">Failed to load data: ${err.message}. Run <code>make demo</code> in <code>domains/personnel</code> first.</p>`;
  }
}

document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-page]");
  if (!btn) return;
  e.stopPropagation();
  showPage(btn.dataset.page);
});

document.getElementById("rail-toggle").addEventListener("click", (e) => {
  e.stopPropagation();
  setRailCollapsed(true);
});

document.getElementById("rail").addEventListener("click", () => {
  if (document.querySelector(".shell").classList.contains("rail-collapsed")) {
    setRailCollapsed(false);
  }
});

document.getElementById("page-banner").addEventListener("click", () => {
  const pageId = document.getElementById("page-banner").dataset.page;
  if (pageId) dismissBanner(pageId);
});

setRailCollapsed(localStorage.getItem(RAIL_KEY) === "1");
mountOrgFilter();
mountRailPublished();
showPage(resolveStoredPageId());
