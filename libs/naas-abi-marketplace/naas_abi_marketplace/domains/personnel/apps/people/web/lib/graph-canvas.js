/**
 * 2D ontology graph canvas — pan, zoom, BFO colours, Cockpit graph parameters.
 */

import { bfoColor, configureBfoBuckets, renderBfoLegendHtml } from "./bfo-buckets.js";
import {
  configureOntologyGraph,
  getScaleLimits,
  graphParams,
  persistParams,
  renderParamsPanel,
  resetParamsToDefaults,
  syncParamValueLabels,
} from "./graph-params.js";
import {
  ONTOLOGY_GRAPH_FOCUS_ID,
  ONTOLOGY_GRAPH_FOCUS_IRI,
  anchorOntologyFocusNode,
  layoutOntologyGraph,
  runLayoutSimulation,
} from "./graph-physics.js";

let NODE_RADIUS = 30;

const EDGE_STROKE = {
  subClassOf: "#5a6478",
  restriction: "#00b0c8",
  objectProperty: "#0072ce",
};

function readColors() {
  const style = getComputedStyle(document.documentElement);
  return {
    ink: style.getPropertyValue("--ink").trim() || "#10121b",
    muted: style.getPropertyValue("--muted").trim() || "#5a6478",
    panel: style.getPropertyValue("--panel").trim() || "#ffffff",
    nodeFill: style.getPropertyValue("--graph-node-fill").trim() || "#ffffff",
    accent: style.getPropertyValue("--accent").trim() || "#171c8e",
  };
}

function nodePalette(node) {
  return bfoColor(node.bfo_bucket || node.bfoBucket || "Unknown");
}

function mountCanvas(host, stage, canvas, graph, ui, { selectedIri, onSelect, appConfig }) {
  const ctx = canvas.getContext("2d");
  let colors = readColors();
  let { min: MIN_SCALE, max: MAX_SCALE } = getScaleLimits();

  function buildLayout() {
    const laid = layoutOntologyGraph(graph, graphParams, { nodeRadius: NODE_RADIUS });
    for (const node of laid.nodes) {
      node.palette = nodePalette(node);
    }
    return laid;
  }

  function personAnchorNode() {
    return (
      nodes.find((node) => node.id === ONTOLOGY_GRAPH_FOCUS_ID) ||
      nodes.find((node) => node.iri === ONTOLOGY_GRAPH_FOCUS_IRI) ||
      null
    );
  }

  let laidOut = buildLayout();
  let { nodes, edges } = laidOut;
  let graphFocus = laidOut.focus || personAnchorNode();
  let selected =
    nodes.find((node) => node.iri === selectedIri) ||
    nodes.find((node) => node.id === selectedIri) ||
    null;

  let paramsOpen = false;
  let defaultZoom = graphParams.zoom;
  let pan = { x: 0, y: 0 };
  let scale = defaultZoom;
  let dragging = null;
  let panning = null;
  let offset = { x: 0, y: 0 };
  let pointerStart = null;
  let stopSimulation = null;

  const legendEl = ui.legend;
  const controlsHost = ui.controlsHost;

  function syncLegend() {
    if (!legendEl) return;
    legendEl.hidden = !graphParams.legend;
    legendEl.innerHTML = renderBfoLegendHtml();
  }

  function renderControls() {
    if (!controlsHost) return;
    controlsHost.innerHTML = `
      <div class="graph-zoom">
        <button type="button" class="ontology-graph-zoom-in" title="Zoom in">+</button>
        <button type="button" class="ontology-graph-zoom-out" title="Zoom out">−</button>
        <button type="button" class="ontology-graph-zoom-reset" title="Reset view">⟲</button>
      </div>
      ${renderParamsPanel(graphParams, paramsOpen)}`;
    controlsHost.querySelector(".ontology-graph-zoom-in")?.addEventListener("click", () => {
      zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 1.15);
    });
    controlsHost.querySelector(".ontology-graph-zoom-out")?.addEventListener("click", () => {
      zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 0.87);
    });
    controlsHost.querySelector(".ontology-graph-zoom-reset")?.addEventListener("click", () => {
      resetView(graphFocus || personAnchorNode(), { fitNetwork: true });
    });
    const toggle = controlsHost.querySelector(".ontology-graph-params-toggle");
    const menu = controlsHost.querySelector(".ontology-graph-params-menu");
    toggle?.addEventListener("click", () => {
      paramsOpen = !paramsOpen;
      if (menu) menu.hidden = !paramsOpen;
      toggle.setAttribute("aria-expanded", paramsOpen ? "true" : "false");
    });
    menu?.addEventListener("change", onParamChange);
    menu?.addEventListener("input", onParamInput);
    controlsHost.querySelector("#graph-params-reset")?.addEventListener("click", () => {
      resetParamsToDefaults();
      defaultZoom = graphParams.zoom;
      paramsOpen = false;
      relayout();
      renderControls();
      syncLegend();
    });
    syncParamValueLabels(controlsHost, graphParams);
  }

  function relayout() {
    stopSimulation?.();
    const focus = selected;
    const laid = buildLayout();
    ({ nodes, edges } = laid);
    graphFocus = laid.focus || personAnchorNode();
    edges.degreesCounted = false;
    selected =
      nodes.find((node) => node.iri === focus?.iri) ||
      nodes.find((node) => node.id === focus?.id) ||
      null;
    stopSimulation = startSimulation();
  }

  function startSimulation() {
    return runLayoutSimulation(nodes, edges, graphParams, {
      nodeRadius: NODE_RADIUS,
      onFrame: draw,
      onEnd: () => {
        anchorOntologyFocusNode(nodes);
        graphFocus = personAnchorNode();
        resetView(selected || graphFocus, { fitNetwork: !selected });
      },
    });
  }

  function applyParam(key, value) {
    graphParams[key] = value;
    if (key === "zoom") defaultZoom = value;
    persistParams({ ...graphParams });
    if (key === "legend") {
      syncLegend();
      return;
    }
    if (
      key === "physics" ||
      key === "clusterBy" ||
      key === "clusterPull" ||
      key === "linkDistance" ||
      key === "repulsion" ||
      key === "nodeMinGap" ||
      key === "settleMs"
    ) {
      relayout();
    }
  }

  function onParamChange(ev) {
    const target = ev.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
    const key = target.dataset.param;
    if (!key) return;
    if (target instanceof HTMLInputElement && target.type === "checkbox") {
      applyParam(key, target.checked);
    } else if (target instanceof HTMLSelectElement) {
      applyParam(key, target.value);
    }
    syncParamValueLabels(controlsHost, graphParams);
  }

  function onParamInput(ev) {
    const target = ev.target;
    if (!(target instanceof HTMLInputElement) || target.type !== "range") return;
    const key = target.dataset.param;
    if (!key) return;
    const value = Number(target.value);
    applyParam(key, value);
    syncParamValueLabels(controlsHost, graphParams);
  }

  function viewCenter() {
    return { cx: canvas.clientWidth / 2, cy: canvas.clientHeight / 2 };
  }

  function screenToWorld(sx, sy) {
    const { cx, cy } = viewCenter();
    return {
      x: (sx - cx - pan.x) / scale,
      y: (sy - cy - pan.y) / scale,
    };
  }

  function zoomAt(sx, sy, factor) {
    const { cx, cy } = viewCenter();
    const wx = (sx - cx - pan.x) / scale;
    const wy = (sy - cy - pan.y) / scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
    pan.x = sx - cx - wx * scale;
    pan.y = sy - cy - wy * scale;
    draw();
  }

  function networkBounds() {
    if (!nodes.length) return null;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const node of nodes) {
      minX = Math.min(minX, node.x);
      minY = Math.min(minY, node.y);
      maxX = Math.max(maxX, node.x);
      maxY = Math.max(maxY, node.y);
    }
    const pad = NODE_RADIUS + 20;
    return {
      minX: minX - pad,
      minY: minY - pad,
      maxX: maxX + pad,
      maxY: maxY + pad,
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2,
    };
  }

  /** Pan/zoom so the anchor class (Person by default) sits on the canvas center. */
  function resetView(node, { fitNetwork = false } = {}) {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w < 2 || h < 2) return;

    const anchor = node || graphFocus || personAnchorNode() || selected || nodes[0];
    if (!anchor) return;

    scale = defaultZoom;

    if (fitNetwork) {
      const bounds = networkBounds();
      if (bounds) {
        const extentX = Math.max(
          Math.abs(bounds.maxX - anchor.x),
          Math.abs(anchor.x - bounds.minX),
          NODE_RADIUS * 2,
        );
        const extentY = Math.max(
          Math.abs(bounds.maxY - anchor.y),
          Math.abs(anchor.y - bounds.minY),
          NODE_RADIUS * 2,
        );
        const fitScale = Math.min(w / (2 * extentX), h / (2 * extentY)) * 0.9;
        scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min(defaultZoom, fitScale)));
      }
    }

    pan.x = -anchor.x * scale;
    pan.y = -anchor.y * scale;
    draw();
  }

  function drawEdgeLabel(text, x, y) {
    const fontSize = 9;
    ctx.font = `${fontSize}px var(--font-body), sans-serif`;
    const textW = ctx.measureText(text).width;
    const padX = 5;
    const padY = 3;
    const boxW = textW + padX * 2;
    const boxH = fontSize + padY * 2;
    ctx.fillStyle = colors.panel;
    ctx.fillRect(x - boxW / 2, y - boxH / 2, boxW, boxH);
    ctx.fillStyle = colors.ink;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
  }

  function drawArrowhead(x, y, angle, size, color) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x - size * Math.cos(angle - Math.PI / 7), y - size * Math.sin(angle - Math.PI / 7));
    ctx.lineTo(x - size * Math.cos(angle + Math.PI / 7), y - size * Math.sin(angle + Math.PI / 7));
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function shortenEdge(a, b, padA, padB) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    return {
      start: { x: a.x + ux * padA, y: a.y + uy * padA },
      end: { x: b.x - ux * padB, y: b.y - uy * padB },
    };
  }

  function drawEdge(edge) {
    const { start, end } = shortenEdge(edge.a, edge.b, NODE_RADIUS + 4, NODE_RADIUS + 10);
    const stroke = EDGE_STROKE[edge.kind] || colors.muted;
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = stroke;
    ctx.globalAlpha = 0.75;
    ctx.lineWidth = 1.6 / Math.max(scale, 0.55);
    if (edge.kind === "restriction") ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    const angle = Math.atan2(end.y - start.y, end.x - start.x);
    drawArrowhead(end.x, end.y, angle, 12 / Math.max(scale, 0.55), stroke);
    if (edge.predicateLabel) {
      drawEdgeLabel(edge.predicateLabel, (start.x + end.x) / 2, (start.y + end.y) / 2);
    }
    ctx.globalAlpha = 1;
  }

  function wrapLabel(text) {
    const words = String(text || "").split(/\s+/);
    if (words.length <= 2) return [text];
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  }

  function drawNode(node) {
    ctx.beginPath();
    ctx.arc(node.x, node.y, NODE_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = node.palette?.color || colors.nodeFill;
    ctx.fill();
    ctx.strokeStyle = node.palette?.border || colors.accent;
    ctx.lineWidth = selected?.iri === node.iri ? 2.6 : 2;
    ctx.stroke();
    if (selected?.iri === node.iri) {
      ctx.strokeStyle = colors.ink;
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
    const lines = wrapLabel(node.label);
    ctx.font = `600 10px var(--font-body), sans-serif`;
    ctx.fillStyle = colors.nodeFill;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const lineHeight = 12;
    let y = node.y - ((lines.length - 1) * lineHeight) / 2;
    for (const line of lines) {
      ctx.fillText(line.length > 18 ? `${line.slice(0, 16)}…` : line, node.x, y);
      y += lineHeight;
    }
  }

  function draw() {
    const { cx, cy } = viewCenter();
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(cx + pan.x, cy + pan.y);
    ctx.scale(scale, scale);
    for (const edge of edges) drawEdge(edge);
    for (const node of nodes) drawNode(node);
    ctx.restore();
  }

  function hit(pos) {
    for (let i = nodes.length - 1; i >= 0; i -= 1) {
      const node = nodes[i];
      if (Math.hypot(node.x - pos.x, node.y - pos.y) <= NODE_RADIUS + 6) return node;
    }
    return null;
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(stage.clientWidth * dpr);
    canvas.height = Math.floor(stage.clientHeight * dpr);
    canvas.style.width = `${stage.clientWidth}px`;
    canvas.style.height = `${stage.clientHeight}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    colors = readColors();
    ({ min: MIN_SCALE, max: MAX_SCALE } = getScaleLimits());
    draw();
  }

  function onPointerDown(ev) {
    const rect = canvas.getBoundingClientRect();
    const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
    const node = hit(pos);
    pointerStart = node ? { node, x: ev.clientX, y: ev.clientY, moved: false } : null;
    if (node) {
      if (!node.pinned) {
        dragging = node;
        offset = { x: pos.x - node.x, y: pos.y - node.y };
      }
    } else {
      panning = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
    }
    canvas.setPointerCapture(ev.pointerId);
  }

  function onPointerMove(ev) {
    const rect = canvas.getBoundingClientRect();
    if (pointerStart && Math.hypot(ev.clientX - pointerStart.x, ev.clientY - pointerStart.y) > 4) {
      pointerStart.moved = true;
    }
    if (dragging) {
      const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      dragging.x = pos.x - offset.x;
      dragging.y = pos.y - offset.y;
      draw();
    } else if (panning) {
      pan.x = ev.clientX - panning.x;
      pan.y = ev.clientY - panning.y;
      draw();
    }
  }

  function onPointerUp() {
    if (pointerStart && !pointerStart.moved && pointerStart.node) {
      selected = pointerStart.node;
      onSelect?.(selected);
      draw();
    }
    dragging = null;
    panning = null;
    pointerStart = null;
  }

  function onWheel(ev) {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, ev.deltaY < 0 ? 1.1 : 0.9);
  }

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerUp);
  canvas.addEventListener("wheel", onWheel, { passive: false });

  function safeResize({ refit = false } = {}) {
    if (stage.clientWidth < 2 || stage.clientHeight < 2) return;
    const keepNode = selected;
    const keepScale = scale;
    resize();
    if (refit) {
      resetView(keepNode || graphFocus || personAnchorNode(), { fitNetwork: !keepNode });
      return;
    }
    const anchor = keepNode || graphFocus || personAnchorNode();
    if (anchor) {
      pan.x = -anchor.x * keepScale;
      pan.y = -anchor.y * keepScale;
      draw();
    }
  }

  window.addEventListener("resize", safeResize);
  const sizeObserver = new ResizeObserver(() => safeResize());
  sizeObserver.observe(stage);

  renderControls();
  syncLegend();
  stopSimulation = startSimulation();

  requestAnimationFrame(() => {
    resetView(graphFocus || personAnchorNode(), { fitNetwork: true });
    safeResize({ refit: true });
  });

  return {
    setSelected(iri) {
      selected = nodes.find((node) => node.iri === iri) || null;
      draw();
    },
    centreOn(iri) {
      const node = nodes.find((n) => n.iri === iri);
      if (node) resetView(node, { fitNetwork: false });
    },
    resize: (options) => safeResize(options),
    fitNetwork() {
      resetView(selected || graphFocus || personAnchorNode(), { fitNetwork: true });
    },
    destroy() {
      stopSimulation?.();
      sizeObserver.disconnect();
      window.removeEventListener("resize", safeResize);
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointercancel", onPointerUp);
      canvas.removeEventListener("wheel", onWheel);
      host.innerHTML = "";
    },
    remount(nextSelected = selected?.iri || "", nextGraph = graph) {
      this.destroy();
      return mountCockpitStyleGraph(host, nextGraph, {
        selectedIri: nextSelected,
        onSelect,
        appConfig,
      });
    },
  };
}

export function mountCockpitStyleGraph(
  host,
  graph,
  { selectedIri = "", onSelect, theme, appConfig } = {},
) {
  configureBfoBuckets(theme?.bfo_buckets);
  configureOntologyGraph(appConfig || {});
  NODE_RADIUS = appConfig?.graph?.node?.radius ?? NODE_RADIUS;

  host.innerHTML = `
    <div class="graph-stage ontology-graph-stage">
      <div class="graph-legend ontology-graph-legend" hidden></div>
      <canvas class="ontology-graph-canvas" aria-label="Personnel ontology class graph"></canvas>
      <div class="graph-controls ontology-graph-controls"></div>
      <p class="graph-hint">Scroll to zoom · Drag background to pan · Click a class for details</p>
    </div>`;

  const stage = host.querySelector(".ontology-graph-stage");
  const canvas = host.querySelector(".ontology-graph-canvas");
  const ui = {
    legend: host.querySelector(".ontology-graph-legend"),
    controlsHost: host.querySelector(".ontology-graph-controls"),
  };

  return mountCanvas(host, stage, canvas, graph, ui, { selectedIri, onSelect, appConfig });
}
