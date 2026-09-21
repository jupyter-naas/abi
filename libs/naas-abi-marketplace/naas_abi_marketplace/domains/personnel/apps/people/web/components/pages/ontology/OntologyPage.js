/**
 * The ontology page, laid out like the Nexus ontology network: a toolbar with
 * the relations to show and the layout, the network with its BFO bucket panel,
 * an inspector for the selected class, and a status bar. The Turtle a class was
 * written in stays one click away.
 */

import { fetchOntology } from "../../../lib/api.js";
import { BFO_BUCKETS, bfoColor, configureBfoBuckets } from "../../../lib/bfo-buckets.js";
import { escapeHtml, ICONS } from "../../../lib/dom.js";
import { mountNetwork } from "../../../lib/network-canvas.js";
import { buildOntologyGraph, connectedNodes, connectionsOf, filterGraph, nodesPerBucket, termsInSource } from "../../../lib/ontology-graph.js";
import { classSearchEntry, searchClasses } from "../../../lib/ontology-search.js";
import { searchHref } from "../../../lib/routes.js";
import { highlightTurtle } from "./ttl-highlight.js";

const BUCKET_DESCRIPTIONS = {
  "Material Entity": "Objects, people, organizations",
  Process: "Events, activities, changes",
  "Temporal Region": "Time periods, instants",
  Site: "Locations, places",
  Quality: "Properties, attributes",
  Realizable: "Roles & dispositions",
  GDC: "Documents, data, plans",
  Entity: "Entity",
  Unknown: "Unclassified or unresolved bucket",
};

const ALL_FILES = "all";

function listHtml(items, render) {
  return items?.length ? `<ul class="inspector-list">${items.map(render).join("")}</ul>` : "";
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

  configureBfoBuckets(config.theme?.bfo_buckets);
  const title = payload.title || "Personnel Ontology";
  const graph = buildOntologyGraph(payload);
  const classes = payload.classes;
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const sourceTerms = payload.sources.map((source) => termsInSource(source.text || "", graph.nodes));
  const bucketDefs = BFO_BUCKETS.filter(
    (bucket) => !["Entity", "Unknown"].includes(bucket.type) || graph.nodes.some((node) => node.bucket === bucket.type),
  );

  const state = {
    // Restrictions say what each class is made of; the other two relations are one click away.
    hierarchy: false,
    restrictions: true,
    properties: false,
    layout: "network",
    zones: { topLevel: true, buckets: true }, // drawn in the BFO zones layout: Occurrents/Continuants, and the 7 buckets
    file: ALL_FILES,
    buckets: new Set(),
    hidden: new Set(),
    expanded: new Set(),
    selectedNode: null,
    selectedEdge: null,
    turtle: false,
  };

  const fileOptions = [
    // The ontology is the module and every process slice, merged and deduplicated.
    `<option value="${ALL_FILES}">${escapeHtml(title)}</option>`,
    ...payload.sources.map((source, index) => `<option value="${index}">${escapeHtml(source.name)}</option>`),
  ].join("");

  view.innerHTML = `
    <div class="ontology-page">
      <section class="ontology-network" aria-label="Ontology network">
        <div class="ontology-toolbar">
          <h1 class="ontology-title">${escapeHtml(title)}</h1>
          <div class="ontology-controls" role="group" aria-label="Show relationships">
            <label title="Show the class hierarchy"><input type="checkbox" data-relation="hierarchy" />Hierarchy</label>
            <label title="Show restrictions declared on the classes"><input type="checkbox" data-relation="restrictions" checked />Restrictions</label>
            <label title="Show object property relationships"><input type="checkbox" data-relation="properties" />Properties</label>
            <label class="ontology-zones-toggle ontology-zones-first" title="Show the top-level zones and their titles: Occurrents and Continuants"><input type="checkbox" data-zone="topLevel" checked />Zone Top Level</label>
            <label class="ontology-zones-toggle" title="Show a zone and its title for each BFO bucket: Who, What, When, Where, Why, How it is, How we know"><input type="checkbox" data-zone="buckets" checked />Zone BFO 7 Buckets</label>
          </div>
          <label class="ontology-select">Layout
            <select class="ontology-layout-select">
              <option value="network">BFO zones</option>
              <option value="TD">Top to bottom</option>
              <option value="LR">Left to right</option>
            </select>
          </label>
          <label class="ontology-select">File
            <select class="ontology-file-select">${fileOptions}</select>
          </label>
          <div class="ontology-class-search">
            ${ICONS.search}
            <input class="ontology-class-input" type="search" placeholder="Search the graph…"
              aria-label="Search classes and properties in the graph" role="combobox" aria-autocomplete="list"
              aria-expanded="false" aria-controls="ontology-class-results" autocomplete="off" spellcheck="false" />
            <ul class="ontology-class-results" id="ontology-class-results" role="listbox" hidden></ul>
          </div>
          <button type="button" class="ontology-turtle-btn" aria-pressed="false" title="Show the Turtle source">Turtle</button>
          <a class="home-ontology-link" href="${searchHref(config, {})}">Back to search</a>
        </div>
        <div class="ontology-body">
          <aside class="ontology-source" aria-label="Ontology source" hidden>
            <pre class="ontology-code" tabindex="0"><code></code></pre>
            <div class="ontology-resizer" role="separator" aria-orientation="vertical" tabindex="0"
              aria-label="Resize the Turtle source" title="Drag to resize · double-click to reset"></div>
          </aside>
          <div class="ontology-canvas">
            <div class="ontology-viewport"></div>
            <div class="ontology-buckets" aria-label="BFO buckets"></div>
          </div>
          <aside class="ontology-inspector" aria-label="Class inspector" hidden></aside>
        </div>
        <div class="ontology-status" aria-live="polite"></div>
      </section>
    </div>`;

  const $ = (selector) => view.querySelector(selector);
  const searchEl = $(".ontology-class-search");
  const inputEl = $(".ontology-class-input");
  const resultsEl = $(".ontology-class-results");
  const codeEl = $(".ontology-code code");
  const sourceEl = $(".ontology-source");
  const zoneToggleEls = [...view.querySelectorAll(".ontology-zones-toggle")];
  const inspectorEl = $(".ontology-inspector");
  const bucketsEl = $(".ontology-buckets");
  const statusEl = $(".ontology-status");
  const turtleBtn = $(".ontology-turtle-btn");

  let visible = { nodes: [], edges: [] };
  let searchEntries = [];
  let searchResults = [];
  let activeResult = -1;

  const network = mountNetwork($(".ontology-viewport"), {
    onSelectNode: (id) => selectNode(id),
    onSelectEdge: (id) => selectEdge(id),
    onOpenNode: (id) => selectNode(id),
  });

  const keepForFile = () => (state.file === ALL_FILES ? null : sourceTerms[Number(state.file)]);

  /**
   * The terms the relations that are on connect, in the chosen file and before the
   * bucket filters: what the bucket panel lists. The count it shows is what is drawn.
   */
  const filedNodes = () => connectedNodes(graph, state, keepForFile());

  function nodeStyle(node) {
    const palette = bfoColor(node.bucket);
    return { ...node, color: palette.color, border: palette.border, bucketLabel: palette.label };
  }

  function closeResults() {
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
    inputEl.setAttribute("aria-expanded", "false");
    inputEl.removeAttribute("aria-activedescendant");
    searchResults = [];
    activeResult = -1;
  }

  function renderResults() {
    if (!inputEl.value.trim()) return closeResults();
    resultsEl.innerHTML = searchResults.length
      ? searchResults
          .map(
            ({ node, via }, index) => `
          <li class="ontology-class-result" role="option" id="ontology-class-result-${index}"
              data-id="${escapeHtml(node.id)}" aria-selected="${index === activeResult}">
            <span class="ontology-class-result-label">${escapeHtml(node.label)}</span>
            <span class="ontology-class-result-id">${escapeHtml(node.id)}${via ? ` · property: ${escapeHtml(via)}` : ""}</span>
          </li>`,
          )
          .join("")
      : `<li class="ontology-class-noresult" role="presentation">No class in this graph matches.</li>`;
    resultsEl.hidden = false;
    inputEl.setAttribute("aria-expanded", "true");
    if (activeResult >= 0) inputEl.setAttribute("aria-activedescendant", `ontology-class-result-${activeResult}`);
    else inputEl.removeAttribute("aria-activedescendant");
  }

  function renderBuckets() {
    const perBucket = nodesPerBucket(filedNodes());
    const drawn = new Set(visible.nodes.map((node) => node.id));
    const drawnIn = (entries) => entries.filter((entry) => drawn.has(entry.id)).length;
    const anyActive = state.buckets.size > 0;
    bucketsEl.innerHTML = `
      <h2>BFO 7 Buckets</h2>
      ${bucketDefs
        .map((bucket) => {
          const entries = perBucket.get(bucket.type) || [];
          const active = state.buckets.has(bucket.type);
          const expanded = state.expanded.has(bucket.type);
          return `
        <div class="bucket${anyActive && !active ? " is-dimmed" : ""}">
          <div class="bucket-row">
            <button type="button" class="bucket-toggle" data-bucket="${escapeHtml(bucket.type)}" aria-pressed="${active}"
              title="${escapeHtml(bucket.label)} (${escapeHtml(bucket.type)}) — ${escapeHtml(BUCKET_DESCRIPTIONS[bucket.type] || "")}">
              <i style="background:${bucket.color}"></i><strong>${escapeHtml(bucket.label)}</strong>
              ${entries.length ? `<span title="${drawnIn(entries)} on the canvas">${drawnIn(entries)}</span>` : ""}
            </button>
            ${
              entries.length
                ? `<button type="button" class="bucket-expand${expanded ? " is-open" : ""}" data-expand="${escapeHtml(bucket.type)}"
                    aria-expanded="${expanded}" aria-label="Classes in ${escapeHtml(bucket.label)}">›</button>`
                : ""
            }
          </div>
          ${
            expanded && entries.length
              ? `<div class="bucket-nodes">${entries
                  .map(
                    (entry) => `<label${anyActive && !active ? ` title="Not in the chosen buckets"` : ""}><input type="checkbox" data-node="${escapeHtml(entry.id)}"
                      ${drawn.has(entry.id) ? "checked" : ""} ${anyActive && !active ? "disabled" : ""} /><span>${escapeHtml(entry.label)}</span></label>`,
                  )
                  .join("")}</div>`
              : ""
          }
        </div>`;
        })
        .join("")}`;
  }

  function renderStatus() {
    const stats = payload.stats || {};
    const edge = state.selectedEdge ? visible.edges.find((item) => item.id === state.selectedEdge) : null;
    let text;
    if (edge) {
      text = `<span>${escapeHtml(nodeById.get(edge.source)?.label)} ${edge.both ? "↔" : "→"} ${escapeHtml(edge.label || "subclass of")} ${edge.both ? "↔" : "→"} ${escapeHtml(nodeById.get(edge.target)?.label)}</span>
        <button type="button" data-action="clear" aria-label="Clear selection">×</button>`;
    } else {
      text = `<span>${visible.nodes.length} classes · ${visible.edges.length} connections</span>
        <span class="ontology-status-stats">${stats.restrictions ?? 0} restrictions · ${stats.object_properties ?? 0} object properties · ${stats.datatype_properties ?? 0} datatype properties</span>`;
    }
    const filtered = state.buckets.size > 0 || state.hidden.size > 0;
    statusEl.innerHTML = `${text}
      ${!state.selectedNode && !edge ? `<span class="ontology-status-hint">Select a class to inspect</span>` : ""}
      ${filtered ? `<button type="button" data-action="reset">Reset filters</button>` : ""}`;
  }

  function inspectorHtml(node) {
    const detail = classes[node.iri] || {};
    const palette = bfoColor(node.bucket);
    const connections = connectionsOf(node.id, visible.nodes, visible.edges);
    const declaredIn = payload.sources.filter((_, index) => sourceTerms[index].has(node.id));
    const definition = [detail.definition, detail.comment].filter(Boolean).join("\n\n");
    return `
      <header class="inspector-head">
        <div>
          <p class="inspector-kind"><span style="background:${palette.color}"></span>${escapeHtml(palette.label || node.bucket)} · Class</p>
          <h2 tabindex="-1">${escapeHtml(node.label)}</h2>
          <p class="inspector-uri">${escapeHtml(node.iri)}</p>
        </div>
        <button type="button" class="inspector-close" data-action="close" aria-label="Close inspector">×</button>
      </header>
      <div class="inspector-content">
        ${definition ? `<section><h3>Definition</h3><p>${escapeHtml(definition)}</p></section>` : ""}
        ${
          connections.length
            ? `<section><h3>Connections in this view <span>${connections.length}</span></h3>
              <ul class="inspector-connections">${connections
                .map(
                  ({ edge, other, incoming }) => `<li><button type="button" data-select="${escapeHtml(other.id)}" title="Inspect ${escapeHtml(other.label)}">
                    <span>${escapeHtml(
                      edge.both
                        ? `${node.label} ↔ ${edge.label} ↔ ${other.label}`
                        : incoming
                          ? `${other.label} → ${edge.label || "subclass of"} → ${node.label}`
                          : `${node.label} → ${edge.label || "subclass of"} → ${other.label}`,
                    )}</span>›</button></li>`,
                )
                .join("")}</ul></section>`
            : ""
        }
        ${
          detail.datatype_properties?.length
            ? `<section><h3>Data properties <span>${detail.datatype_properties.length}</span></h3>${listHtml(
                detail.datatype_properties,
                (row) => `<li><code>${escapeHtml(row.property)}</code>${row.range ? ` → ${escapeHtml(String(row.range).split("#").pop())}` : ""}</li>`,
              )}</section>`
            : ""
        }
        ${
          declaredIn.length
            ? `<section><h3>${declaredIn.length === 1 ? "Source" : "Sources"}</h3><ul class="inspector-sources">${declaredIn
                .map((source) => `<li>${escapeHtml(source.name)}</li>`)
                .join("")}</ul></section>`
            : ""
        }
      </div>
      <footer class="inspector-actions">
        <button type="button" data-action="focus">Focus node</button>
        ${declaredIn.length ? `<button type="button" data-action="turtle">View in Turtle</button>` : ""}
      </footer>`;
  }

  function renderInspector() {
    const node = state.selectedNode ? nodeById.get(state.selectedNode) : null;
    if (!node || !visible.nodes.some((item) => item.id === node.id)) {
      inspectorEl.hidden = true;
      inspectorEl.innerHTML = "";
      return;
    }
    const wasOpen = !inspectorEl.hidden;
    inspectorEl.innerHTML = inspectorHtml(node);
    inspectorEl.hidden = false;
    inspectorEl.querySelector(".inspector-content").scrollTop = 0;
    if (!wasOpen) inspectorEl.querySelector("h2").focus({ preventScroll: true });
  }

  function showTurtle() {
    const source = state.file === ALL_FILES ? null : payload.sources[Number(state.file)];
    codeEl.innerHTML = highlightTurtle(source?.text || payload.display_ttl);
    sourceEl.hidden = !state.turtle;
    turtleBtn.setAttribute("aria-pressed", String(state.turtle));
  }

  /** Scroll the Turtle to where the class is declared. */
  function scrollTurtleTo(node) {
    const text = state.file === ALL_FILES ? payload.display_ttl : payload.sources[Number(state.file)]?.text || "";
    const local = node.id.includes(":") ? node.id.split(":").pop() : node.id;
    const at = [`${node.id} a `, `${local} a `].map((needle) => text.indexOf(needle)).find((index) => index >= 0);
    if (at === undefined) return;
    const line = text.slice(0, at).split("\n").length - 1;
    const pre = $(".ontology-code");
    pre.scrollTop = Math.max(0, line * (parseFloat(getComputedStyle(pre).lineHeight) || 16) - 24);
  }

  /** Rebuild what is drawn. ``refit`` when the network itself changed, not just a selection. */
  function render({ refit = true } = {}) {
    const keep = keepForFile();
    visible = filterGraph(graph, state, state.buckets, state.hidden, keep);
    searchEntries = visible.nodes.map((node) => classSearchEntry({ ...node, iri: node.iri }, classes[node.iri]));
    if (state.selectedNode && !visible.nodes.some((node) => node.id === state.selectedNode)) state.selectedNode = null;
    if (state.selectedEdge && !visible.edges.some((edge) => edge.id === state.selectedEdge)) state.selectedEdge = null;
    // The bucket panel (176px + margins) and the hint sit over the canvas.
    network.setData(
      { layout: state.layout, nodes: visible.nodes.map(nodeStyle), edges: visible.edges, insets: { right: 208, bottom: 28 } },
      { refit },
    );
    network.setSelection({ nodeId: state.selectedNode, edgeId: state.selectedEdge });
    renderBuckets();
    renderInspector();
    renderStatus();
  }

  function selectNode(id, { focus = true } = {}) {
    state.selectedNode = id || null;
    state.selectedEdge = null;
    network.setSelection({ nodeId: state.selectedNode });
    renderInspector();
    renderStatus();
    if (id && focus) network.focus(id);
    // The canvas narrows when the inspector opens or closes.
    network.resize();
    const node = id ? nodeById.get(id) : null;
    inputEl.value = node ? node.label : "";
    closeResults();
  }

  function selectEdge(id) {
    state.selectedEdge = id || null;
    if (id) state.selectedNode = null;
    network.setSelection({ nodeId: state.selectedNode, edgeId: state.selectedEdge });
    renderInspector();
    renderStatus();
    network.resize();
  }

  // ── Turtle panel width: drag the handle on its right edge (or use the arrow keys) ──
  const SOURCE_WIDTH_KEY = "people.ontology.sourceWidth";
  const SOURCE_MIN = 240;
  const SOURCE_CANVAS_MIN = 320; // what the network keeps
  const resizerEl = $(".ontology-resizer");

  function setSourceWidth(px, { save = true } = {}) {
    if (px === null) {
      sourceEl.style.removeProperty("flex-basis");
      resizerEl.removeAttribute("aria-valuenow");
    } else {
      const most = Math.max(SOURCE_MIN, $(".ontology-body").clientWidth - SOURCE_CANVAS_MIN);
      const width = Math.round(Math.min(most, Math.max(SOURCE_MIN, px)));
      sourceEl.style.flexBasis = `${width}px`;
      resizerEl.setAttribute("aria-valuenow", String(width));
      px = width;
    }
    if (!save) return;
    try {
      if (px === null) localStorage.removeItem(SOURCE_WIDTH_KEY);
      else localStorage.setItem(SOURCE_WIDTH_KEY, String(px));
    } catch {
      /* private window or blocked storage: the width just is not remembered */
    }
  }

  try {
    const saved = Number(localStorage.getItem(SOURCE_WIDTH_KEY));
    if (saved > 0) setSourceWidth(saved, { save: false });
  } catch {
    /* no stored width */
  }

  resizerEl.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    resizerEl.setPointerCapture(event.pointerId);
    resizerEl.classList.add("is-dragging");
  });
  resizerEl.addEventListener("pointermove", (event) => {
    if (!resizerEl.hasPointerCapture(event.pointerId)) return;
    setSourceWidth(event.clientX - sourceEl.getBoundingClientRect().left, { save: false });
  });
  const endDrag = (event) => {
    if (!resizerEl.hasPointerCapture(event.pointerId)) return;
    resizerEl.releasePointerCapture(event.pointerId);
    resizerEl.classList.remove("is-dragging");
    setSourceWidth(sourceEl.getBoundingClientRect().width);
  };
  resizerEl.addEventListener("pointerup", endDrag);
  resizerEl.addEventListener("pointercancel", endDrag);
  resizerEl.addEventListener("dblclick", () => setSourceWidth(null));
  resizerEl.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 96 : 24;
    const width = sourceEl.getBoundingClientRect().width;
    if (event.key === "ArrowLeft") setSourceWidth(width - step);
    else if (event.key === "ArrowRight") setSourceWidth(width + step);
    else if (event.key === "Home") setSourceWidth(null);
    else return;
    event.preventDefault();
  });

  // ── controls ──
  view.querySelector(".ontology-controls").addEventListener("change", (event) => {
    const zone = event.target.dataset.zone;
    if (zone) {
      state.zones[zone] = event.target.checked;
      network.setZonesVisible(state.zones);
      return;
    }
    const relation = event.target.dataset.relation;
    if (!relation) return;
    state[relation] = event.target.checked;
    render();
  });
  $(".ontology-layout-select").addEventListener("change", (event) => {
    state.layout = event.target.value;
    for (const el of zoneToggleEls) el.hidden = state.layout !== "network";
    render();
  });
  $(".ontology-file-select").addEventListener("change", (event) => {
    state.file = event.target.value;
    state.hidden.clear();
    showTurtle();
    render();
  });
  turtleBtn.addEventListener("click", () => {
    state.turtle = !state.turtle;
    showTurtle();
    network.resize();
  });

  bucketsEl.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-bucket]");
    const expand = event.target.closest("[data-expand]");
    if (toggle) {
      const type = toggle.dataset.bucket;
      if (!state.buckets.delete(type)) state.buckets.add(type);
      render({ refit: false });
    } else if (expand) {
      const type = expand.dataset.expand;
      if (!state.expanded.delete(type)) state.expanded.add(type);
      renderBuckets();
    }
  });
  bucketsEl.addEventListener("change", (event) => {
    const id = event.target.dataset.node;
    if (!id) return;
    if (event.target.checked) state.hidden.delete(id);
    else state.hidden.add(id);
    render({ refit: false });
  });

  statusEl.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "reset") {
      state.buckets.clear();
      state.hidden.clear();
      render();
    } else if (action === "clear") {
      state.selectedEdge = null;
      state.selectedNode = null;
      network.setSelection({});
      renderInspector();
      renderStatus();
    }
  });

  inspectorEl.addEventListener("click", (event) => {
    const select = event.target.closest("[data-select]")?.dataset.select;
    if (select) return selectNode(select);
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "close") selectNode(null);
    else if (action === "focus" && state.selectedNode) network.focus(state.selectedNode);
    else if (action === "turtle" && state.selectedNode) {
      const node = nodeById.get(state.selectedNode);
      if (state.file !== ALL_FILES && !sourceTerms[Number(state.file)].has(node.id)) {
        state.file = ALL_FILES;
        $(".ontology-file-select").value = ALL_FILES;
        render();
      }
      state.turtle = true;
      showTurtle();
      network.resize();
      requestAnimationFrame(() => scrollTurtleTo(node));
    }
  });
  inspectorEl.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      selectNode(null);
    }
  });

  // ── class search ──
  inputEl.addEventListener("input", () => {
    const query = inputEl.value.trim();
    if (!query) {
      closeResults();
      // Emptying the field lets go of the selection.
      if (state.selectedNode) selectNode(null);
      return;
    }
    searchResults = searchClasses(searchEntries, query);
    activeResult = searchResults.length ? 0 : -1;
    renderResults();
  });
  inputEl.addEventListener("focus", () => {
    if (inputEl.value.trim() && !state.selectedNode) {
      searchResults = searchClasses(searchEntries, inputEl.value);
      activeResult = searchResults.length ? 0 : -1;
      renderResults();
    }
  });
  inputEl.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (!resultsEl.hidden) closeResults();
      else if (inputEl.value) {
        inputEl.value = "";
        selectNode(null);
      }
      event.preventDefault();
      return;
    }
    if (!searchResults.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      activeResult = (activeResult + (event.key === "ArrowDown" ? 1 : -1) + searchResults.length) % searchResults.length;
      renderResults();
    } else if (event.key === "Enter" && activeResult >= 0) {
      event.preventDefault();
      selectNode(searchResults[activeResult].node.id);
    }
  });
  resultsEl.addEventListener("mousedown", (event) => {
    const option = event.target.closest(".ontology-class-result");
    if (!option) return;
    // mousedown, not click: the input would blur and close the list first.
    event.preventDefault();
    selectNode(option.dataset.id);
  });
  // focusout, not a document-wide click listener: it goes away with the page.
  searchEl.addEventListener("focusout", () => {
    window.setTimeout(() => {
      if (!searchEl.contains(document.activeElement)) closeResults();
    }, 0);
  });

  const onKeydown = (event) => {
    if (event.key === "Escape" && state.selectedNode && !event.defaultPrevented && document.activeElement === document.body) {
      selectNode(null);
    }
  };
  document.addEventListener("keydown", onKeydown);

  document.body.classList.add("is-ontology-view");
  window.scrollTo(0, 0);
  showTurtle();
  render();

  return {
    showTopbarSearch: false,
    lockViewport: true,
    title: `${title} · People`,
    teardown: () => {
      document.removeEventListener("keydown", onKeydown);
      document.body.classList.remove("is-ontology-view");
      network.destroy();
    },
  };
}
