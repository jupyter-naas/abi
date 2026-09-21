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

const MAX_CLASS_RESULTS = 8;

function fold(text) {
  return String(text ?? "")
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** ``personnel:hasEmployeeRole`` → ``has employee role``; the prefix is dropped. */
function localWords(qname) {
  const local = String(qname ?? "").split(":").pop();
  return fold(local.replace(/_/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2"));
}

/** One searchable entry per class node: what it is called, and what it carries. */
function classSearchEntry(node, detail) {
  const properties = [
    ...(detail?.datatype_properties || []),
    ...(detail?.object_properties_domain || []),
    ...(detail?.object_properties_range || []),
  ].map((item) => ({
    label: item.label || localWords(item.property),
    folded: `${fold(item.label)} ${localWords(item.property)}`,
  }));
  return {
    node,
    label: fold(node.label),
    // The prefix says which vocabulary a class is from. It is matched only when
    // typed in full, or "pers" would return every personnel: class.
    prefix: node.id.includes(":") ? fold(node.id.split(":")[0]) : "",
    local: localWords(node.id),
    definition: fold(detail?.definition || ""),
    properties,
  };
}

/**
 * Rank classes against a query. Every word must match somewhere; the name counts
 * most, then the local id, then a property, then the definition. A word that
 * is exactly a namespace prefix (``personnel``, ``abi``) keeps that namespace.
 */
function searchClasses(entries, query) {
  const words = fold(query).split(/[^a-z0-9]+/).filter(Boolean);
  if (!words.length) return [];
  const results = [];
  for (const entry of entries) {
    let score = 0;
    let via = "";
    let matchedAll = true;
    for (const word of words) {
      let best = 0;
      if (entry.label.startsWith(word)) best = 8;
      else if (entry.prefix && entry.prefix === word) best = 7;
      else if (entry.label.split(/\s+/).some((part) => part.startsWith(word))) best = 6;
      else if (entry.label.includes(word)) best = 5;
      else if (entry.local.includes(word)) best = 4;
      else {
        const property = entry.properties.find((item) => item.folded.includes(word));
        if (property) {
          best = 2;
          via = via || property.label;
        } else if (entry.definition.includes(word)) best = 1;
      }
      if (!best) {
        matchedAll = false;
        break;
      }
      score += best;
    }
    if (matchedAll) results.push({ node: entry.node, score, via });
  }
  return results
    .sort(
      (a, b) =>
        b.score - a.score ||
        a.node.label.localeCompare(b.node.label, undefined, { sensitivity: "base" }),
    )
    .slice(0, MAX_CLASS_RESULTS);
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
          <p class="ontology-lead">Shared S1 vocabulary: the module, then one file per process slice.</p>
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
            <div class="ontology-class-search">
              ${ICONS.search}
              <input
                class="ontology-class-input"
                type="search"
                placeholder="Search the graph…"
                aria-label="Search classes and properties in the graph"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded="false"
                aria-controls="ontology-class-results"
                autocomplete="off"
                spellcheck="false"
              />
              <ul class="ontology-class-results" id="ontology-class-results" role="listbox" hidden></ul>
            </div>
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
  const classSearchEl = view.querySelector(".ontology-class-search");
  const classInputEl = view.querySelector(".ontology-class-input");
  const classResultsEl = view.querySelector(".ontology-class-results");
  const expandBtn = view.querySelector(".ontology-expand-btn");
  const drawer = view.querySelector("#ontology-drawer");
  const drawerBody = view.querySelector(".ontology-drawer-body");
  const graphHost = view.querySelector(".ontology-graph-host");
  const classesByIri = payload.classes;
  let selectedIri = "";
  let graphController = null;
  let activeGraph = payload.graph;
  let teardownSplitResizer = null;
  let searchEntries = [];
  let searchResults = [];
  let activeResult = -1;

  function indexGraph(graph) {
    searchEntries = graph.nodes.map((node) => classSearchEntry(node, classesByIri[node.iri]));
  }

  function closeResults() {
    classResultsEl.hidden = true;
    classResultsEl.innerHTML = "";
    classInputEl.setAttribute("aria-expanded", "false");
    classInputEl.removeAttribute("aria-activedescendant");
    searchResults = [];
    activeResult = -1;
  }

  function renderResults() {
    if (!classInputEl.value.trim()) return closeResults();
    classResultsEl.innerHTML = searchResults.length
      ? searchResults
          .map(
            ({ node, via }, index) => `
          <li class="ontology-class-result" role="option" id="ontology-class-result-${index}"
              data-iri="${escapeHtml(node.iri)}" aria-selected="${index === activeResult}">
            <span class="ontology-class-result-label">${escapeHtml(node.label)}</span>
            <span class="ontology-class-result-id">${escapeHtml(node.id)}${
              via ? ` · property: ${escapeHtml(via)}` : ""
            }</span>
          </li>`,
          )
          .join("")
      : `<li class="ontology-class-noresult" role="presentation">No class in this graph matches.</li>`;
    classResultsEl.hidden = false;
    classInputEl.setAttribute("aria-expanded", "true");
    if (activeResult >= 0) {
      classInputEl.setAttribute("aria-activedescendant", `ontology-class-result-${activeResult}`);
    } else {
      classInputEl.removeAttribute("aria-activedescendant");
    }
  }

  function clearSelection() {
    selectedIri = "";
    graphController?.setSelected("");
    closeDrawer();
  }

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
    const node = activeGraph.nodes.find((item) => item.iri === selectedIri);
    classInputEl.value = node ? node.label : "";
    closeResults();
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
    indexGraph(graph);
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
      classInputEl.value = "";
      closeResults();
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
  classInputEl.addEventListener("input", () => {
    const query = classInputEl.value.trim();
    if (!query) {
      closeResults();
      // Emptying the field (typing it away or the native clear button) lets go
      // of the selection, the way choosing the empty option used to.
      if (selectedIri) clearSelection();
      return;
    }
    searchResults = searchClasses(searchEntries, query);
    activeResult = searchResults.length ? 0 : -1;
    renderResults();
  });

  classInputEl.addEventListener("focus", () => {
    if (classInputEl.value.trim() && !selectedIri) {
      searchResults = searchClasses(searchEntries, classInputEl.value);
      activeResult = searchResults.length ? 0 : -1;
      renderResults();
    }
  });

  classInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (!classResultsEl.hidden) closeResults();
      else if (classInputEl.value) {
        classInputEl.value = "";
        clearSelection();
      }
      event.preventDefault();
      return;
    }
    if (!searchResults.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      activeResult = (activeResult + step + searchResults.length) % searchResults.length;
      renderResults();
    } else if (event.key === "Enter" && activeResult >= 0) {
      event.preventDefault();
      selectClass(searchResults[activeResult].node.iri);
    }
  });

  classResultsEl.addEventListener("mousedown", (event) => {
    const option = event.target.closest(".ontology-class-result");
    if (!option) return;
    // mousedown, not click: the input would blur and close the list first.
    event.preventDefault();
    selectClass(option.dataset.iri);
  });

  // focusout, not a document-wide click listener: it goes away with the page.
  classSearchEl.addEventListener("focusout", () => {
    window.setTimeout(() => {
      if (!classSearchEl.contains(document.activeElement)) closeResults();
    }, 0);
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
