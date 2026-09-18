import { fetchOntology } from "../../../lib/api.js";
import { escapeHtml, ICONS } from "../../../lib/dom.js";
import { searchHref } from "../../../lib/routes.js";
import { highlightTurtle } from "./ttl-highlight.js";
import { mountCockpitStyleGraph } from "../../../lib/graph-canvas.js";

function listHtml(items, render) {
  if (!items?.length) return `<p class="ontology-empty">None</p>`;
  return `<ul class="ontology-list">${items.map(render).join("")}</ul>`;
}

const ONTOLOGY_SPLIT_RATIO_KEY = "people-ontology-split-ratio";

function mountSplitResizer(splitEl, resizerEl, onResize) {
  let ratio = 0.5;
  try {
    const stored = Number(sessionStorage.getItem(ONTOLOGY_SPLIT_RATIO_KEY));
    if (Number.isFinite(stored)) ratio = stored;
  } catch {
    /* ignore */
  }
  ratio = Math.min(0.78, Math.max(0.22, ratio));
  splitEl.style.setProperty("--ontology-split-ratio", String(ratio));

  let dragging = false;

  const onPointerMove = (ev) => {
    if (!dragging) return;
    const rect = splitEl.getBoundingClientRect();
    const stacked = getComputedStyle(splitEl).flexDirection === "column";
    const next = stacked
      ? (ev.clientY - rect.top) / rect.height
      : (ev.clientX - rect.left) / rect.width;
    ratio = Math.min(0.78, Math.max(0.22, next));
    splitEl.style.setProperty("--ontology-split-ratio", String(ratio));
    onResize?.();
  };

  const onPointerUp = () => {
    if (!dragging) return;
    dragging = false;
    try {
      sessionStorage.setItem(ONTOLOGY_SPLIT_RATIO_KEY, String(ratio));
    } catch {
      /* ignore */
    }
    document.body.classList.remove("is-ontology-split-drag");
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    onResize?.();
  };

  resizerEl.addEventListener("pointerdown", (ev) => {
    ev.preventDefault();
    dragging = true;
    document.body.classList.add("is-ontology-split-drag");
    resizerEl.setPointerCapture(ev.pointerId);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  });

  return () => {
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
  };
}

function statsHtml(stats) {
  const rows = [
    ["Classes", stats?.classes],
    ["Restrictions", stats?.restrictions],
    ["Object properties", stats?.object_properties],
    ["Datatype properties", stats?.datatype_properties],
    ["Annotation properties", stats?.annotation_properties],
  ];
  return `<dl class="ontology-stats">${rows
    .map(
      ([label, value]) =>
        `<div class="ontology-stat"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value ?? "—"))}</dd></div>`,
    )
    .join("")}</dl>`;
}

function drawerHtml(detail) {
  if (!detail) {
    return `<p class="ontology-empty">Select a class in the graph to inspect its axioms.</p>`;
  }
  const restrictions = listHtml(
    detail.restrictions,
    (row) =>
      `<li><code>${escapeHtml(row.property)}</code> · ${escapeHtml(row.quantifier)}${
        row.filler ? ` → <code>${escapeHtml(row.filler)}</code>` : ""
      }</li>`,
  );
  const domainProps = listHtml(
    detail.object_properties_domain,
    (row) => `<li><code>${escapeHtml(row.property)}</code> — ${escapeHtml(row.label)}</li>`,
  );
  const rangeProps = listHtml(
    detail.object_properties_range,
    (row) => `<li><code>${escapeHtml(row.property)}</code> — ${escapeHtml(row.label)}</li>`,
  );
  const dataProps = listHtml(
    detail.datatype_properties,
    (row) =>
      `<li><code>${escapeHtml(row.property)}</code>${
        row.range ? ` → ${escapeHtml(row.range)}` : ""
      }</li>`,
  );
  const supers = detail.superclasses?.length
    ? detail.superclasses.map((item) => `<code>${escapeHtml(item)}</code>`).join(", ")
    : "—";
  const subs = detail.subclasses?.length
    ? detail.subclasses.map((item) => `<code>${escapeHtml(item)}</code>`).join(", ")
    : "—";

  return `
    <header class="ontology-drawer-head">
      <h2>${escapeHtml(detail.label)}</h2>
      <p class="ontology-drawer-id"><code>${escapeHtml(detail.id)}</code></p>
      ${detail.bfo_bucket ? `<p class="ontology-drawer-bucket">BFO bucket: <strong>${escapeHtml(detail.bfo_bucket)}</strong></p>` : ""}
    </header>
    ${detail.definition ? `<p class="ontology-drawer-def">${escapeHtml(detail.definition)}</p>` : ""}
    ${detail.comment ? `<p class="ontology-drawer-comment">${escapeHtml(detail.comment)}</p>` : ""}
    <section class="ontology-drawer-section">
      <h3>Superclasses</h3><p>${supers}</p>
    </section>
    <section class="ontology-drawer-section">
      <h3>Subclasses</h3><p>${subs}</p>
    </section>
    <section class="ontology-drawer-section">
      <h3>Restrictions</h3>${restrictions}
    </section>
    <section class="ontology-drawer-section">
      <h3>Object properties (domain)</h3>${domainProps}
    </section>
    <section class="ontology-drawer-section">
      <h3>Object properties (range)</h3>${rangeProps}
    </section>
    <section class="ontology-drawer-section">
      <h3>Datatype properties</h3>${dataProps}
    </section>`;
}

export async function mountOntology(view, { config }) {
  view.innerHTML = `<div class="ontology-page"><p class="stats">Loading ontology…</p></div>`;

  let payload;
  try {
    payload = await fetchOntology();
  } catch (error) {
    view.innerHTML = `<div class="ontology-page"><div class="empty-state error-block">
      <h2>Could not load ontology</h2><p>${escapeHtml(error.message)}</p>
      <p><a class="home-ontology-link" href="${searchHref(config, {})}">Back to search</a></p></div></div>`;
    return { showTopbarSearch: false, title: "Personnel Ontology" };
  }

  const classNodes = [...payload.graph.nodes].sort((a, b) =>
    a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
  );
  const classOptions = `<option value="">Select a class…</option>${classNodes
    .map((node) => `<option value="${escapeHtml(node.iri)}">${escapeHtml(node.label)} (${escapeHtml(node.id)})</option>`)
    .join("")}`;

  const sourceOptions = payload.sources
    .map(
      (source, index) =>
        `<option value="${index}"${index === 0 ? " selected" : ""}>${escapeHtml(source.name)}</option>`,
    )
    .join("");

  view.innerHTML = `
    <div class="ontology-page">
      <header class="ontology-head">
        <div>
          <h1 class="ontology-title">${escapeHtml(payload.title || "Personnel Ontology")}</h1>
          <p class="ontology-lead">Shared S1 vocabulary: module plus working and studying process slices.</p>
          ${statsHtml(payload.stats)}
        </div>
        <a class="home-ontology-link" href="${searchHref(config, {})}">Back to search</a>
      </header>
      <div class="ontology-split">
        <section class="ontology-pane ontology-pane--ttl" aria-label="Ontology source">
          <div class="ontology-pane-toolbar">
            <label class="ontology-file-label">File
              <select class="ontology-file-select">${sourceOptions}</select>
            </label>
            <span class="ontology-pane-hint">Turtle</span>
          </div>
          <pre class="ontology-code" tabindex="0"><code></code></pre>
        </section>
        <div
          class="ontology-split-resizer"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize Turtle and graph panels"
          tabindex="0"
        ></div>
        <section class="ontology-pane ontology-pane--graph" aria-label="Class graph">
          <div class="ontology-pane-toolbar ontology-graph-toolbar">
            <label class="ontology-class-label">Class
              <select class="ontology-class-select">${classOptions}</select>
            </label>
            <div class="ontology-graph-actions">
              <button type="button" class="ontology-expand-btn" aria-label="Expand graph to full page" aria-pressed="false">${ICONS.expand}</button>
            </div>
          </div>
          <div class="ontology-graph-host"></div>
        </section>
      </div>
      <aside class="ontology-drawer" id="ontology-drawer" aria-label="Class details" hidden>
        <button type="button" class="ontology-drawer-close" aria-label="Close details">×</button>
        <div class="ontology-drawer-body"></div>
      </aside>
    </div>`;

  const pageEl = view.querySelector(".ontology-page");
  const splitEl = view.querySelector(".ontology-split");
  const splitResizerEl = view.querySelector(".ontology-split-resizer");
  const codeEl = view.querySelector(".ontology-code code");
  const fileSelectEl = view.querySelector(".ontology-file-select");
  const classSelectEl = view.querySelector(".ontology-class-select");
  const expandBtn = view.querySelector(".ontology-expand-btn");
  const drawer = view.querySelector("#ontology-drawer");
  const drawerBody = view.querySelector(".ontology-drawer-body");
  const graphHost = view.querySelector(".ontology-graph-host");
  const classesByIri = payload.classes;
  let selectedIri = "";
  let graphController = null;
  let activeGraph = payload.graph;
  let teardownSplitResizer = null;

  function refitGraph() {
    requestAnimationFrame(() => graphController?.resize({ refit: true }));
  }

  function graphForSource(index) {
    const source = payload.sources[Number(index)] || payload.sources[0];
    const text = source?.text || "";
    const nodes = payload.graph.nodes.filter((node) => {
      const local = node.id.includes(":") ? node.id.split(":").pop() : node.id;
      return (
        text.includes(node.id) ||
        text.includes(`${local} a `) ||
        text.includes(`${local};`) ||
        text.includes(`${local} `)
      );
    });
    if (!nodes.length) return payload.graph;
    const ids = new Set(nodes.map((node) => node.id));
    const edges = payload.graph.edges.filter((edge) => ids.has(edge.from) && ids.has(edge.to));
    return { nodes, edges };
  }

  function showTtl(index) {
    const source = payload.sources[Number(index)] || payload.sources[0];
    codeEl.innerHTML = highlightTurtle(source?.text || payload.display_ttl);
  }

  function selectClass(iri, { openPanel = true } = {}) {
    selectedIri = iri || "";
    classSelectEl.value = selectedIri;
    graphController?.setSelected(selectedIri);
    if (selectedIri) graphController?.centreOn(selectedIri);
    if (openPanel && selectedIri) openDrawer(selectedIri);
  }

  function openDrawer(iri) {
    const detail = classesByIri[iri];
    drawerBody.innerHTML = drawerHtml(detail);
    drawer.hidden = false;
    pageEl.classList.add("is-drawer-open");
    refitGraph();
  }

  function closeDrawer() {
    drawer.hidden = true;
    pageEl.classList.remove("is-drawer-open");
    refitGraph();
  }

  function mountGraph(graph = activeGraph) {
    activeGraph = graph;
    graphController?.destroy();
    graphController = mountCockpitStyleGraph(graphHost, graph, {
      selectedIri,
      onSelect: (node) => selectClass(node.iri),
      theme: config.theme,
      appConfig: config,
    });
  }

  function refreshGraphForFile(index) {
    showTtl(index);
    const nextGraph = graphForSource(index);
    mountGraph(nextGraph);
    const stillVisible = nextGraph.nodes.some((node) => node.iri === selectedIri);
    if (!stillVisible) {
      selectedIri = "";
      classSelectEl.value = "";
      closeDrawer();
    } else if (selectedIri) {
      graphController?.setSelected(selectedIri);
      graphController?.centreOn(selectedIri);
    }
  }

  document.body.classList.add("is-ontology-view");
  window.scrollTo(0, 0);
  if (splitEl && splitResizerEl) {
    teardownSplitResizer = mountSplitResizer(splitEl, splitResizerEl, refitGraph);
  }
  refreshGraphForFile(0);
  classSelectEl.addEventListener("change", () => {
    if (classSelectEl.value) selectClass(classSelectEl.value);
    else {
      selectedIri = "";
      graphController?.setSelected("");
    }
  });
  view.querySelector(".ontology-drawer-close").addEventListener("click", closeDrawer);

  fileSelectEl.addEventListener("change", () => refreshGraphForFile(fileSelectEl.value));

  expandBtn.addEventListener("click", () => {
    const expanded = pageEl.classList.toggle("is-graph-expanded");
    expandBtn.innerHTML = expanded ? ICONS.collapse : ICONS.expand;
    expandBtn.setAttribute("aria-label", expanded ? "Exit full page graph" : "Expand graph to full page");
    expandBtn.setAttribute("aria-pressed", expanded ? "true" : "false");
    document.body.classList.toggle("ontology-graph-fullscreen", expanded);
    refitGraph();
  });

  let resizeTimer = 0;
  const onResize = () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => refitGraph(), 120);
  };
  window.addEventListener("resize", onResize);

  return {
    showTopbarSearch: false,
    lockViewport: true,
    title: `${payload.title || "Personnel Ontology"} · People`,
    teardown: () => {
      window.removeEventListener("resize", onResize);
      window.clearTimeout(resizeTimer);
      document.body.classList.remove("ontology-graph-fullscreen", "is-ontology-view");
      teardownSplitResizer?.();
      graphController?.destroy();
    },
  };
}
