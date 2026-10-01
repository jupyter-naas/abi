/**
 * The ontology network canvas, drawn the way the Nexus ontology network draws
 * it: square cards in the BFO bucket colour with white labels, square-corner
 * connectors (black and dashed for the class hierarchy, labelled and slate for
 * the rest), pan, zoom, drag, and everything unselected faded while one card is
 * selected. The network view places the cards in BFO zones, as in the BFO 7
 * Buckets diagram. No dependencies: a single 2D canvas.
 */

import { edgeSides, sideLoads } from "./bfo-edge-rules.js";
import { bucketLayout, cardSize, hierarchicalPositions, LABEL_FONT_SIZE, LABEL_LINE_HEIGHT, wrapLabel } from "./network-layout.js";
import { routeDistance, routeEdges, routeLabel } from "./orthogonal-route.js";

const FONT = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";
const EDGE_COLOR = "#94a3b8";
const EDGE_LABEL_COLOR = "#64748b";
const DIMMED_TEXT = "#94a3b8";
const MIN_SCALE = 0.15;
const MAX_SCALE = 2.5;
// A network that fits with room to spare is not blown up past this.
const AUTO_FIT_MAX = 1.2;

function fadeTowardWhite(hex, amount) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!match) return hex;
  const int = parseInt(match[1], 16);
  const mix = (c) => Math.round(c + (255 - c) * amount);
  return `#${[(int >> 16) & 255, (int >> 8) & 255, int & 255].map((c) => mix(c).toString(16).padStart(2, "0")).join("")}`;
}

function withAlpha(hex, alpha) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!match) return hex;
  const int = parseInt(match[1], 16);
  return `rgba(${(int >> 16) & 255}, ${(int >> 8) & 255}, ${int & 255}, ${alpha})`;
}

export function mountNetwork(host, { onSelectNode, onSelectEdge, onOpenNode } = {}) {
  host.innerHTML = `
    <canvas class="network-canvas" aria-label="Ontology network"></canvas>
    <div class="network-zoom" role="group" aria-label="Zoom">
      <button type="button" data-zoom="in" aria-label="Zoom in" title="Zoom in">+</button>
      <button type="button" data-zoom="out" aria-label="Zoom out" title="Zoom out">−</button>
      <button type="button" data-zoom="fit" aria-label="Fit the network to the view" title="Fit to view">⟲</button>
    </div>
    <p class="network-hint">Scroll to zoom · Drag background to pan · Click a class for details</p>`;
  const canvas = host.querySelector(".network-canvas");
  const ctx = canvas.getContext("2d");

  let nodes = [];
  let edges = [];
  let layout = "network";
  let byId = new Map();
  let positions = new Map();
  let boxes = new Map();
  let drawn = [];
  let geometryKey = "";
  let zones = [];
  let bands = [];
  let showBands = true; // the OCCURRENTS / CONTINUANTS bands and their titles
  let showBuckets = false; // the bucket zones and their titles: off until asked for
  let room = {}; // what the layout left outside the outermost cards
  let sidesOf = null; // which sides connectors use, in the BFO zone layout only
  let view = { scale: 1, x: 0, y: 0 }; // screen = world * scale + (x, y)
  let selectedNode = null;
  let selectedEdge = null;
  let hoverEdge = null;
  let hoverNode = null;
  let pointer = null;
  let dragging = null; // the card being dragged, once it has moved
  let colors = readColors();
  // A fit asked for before the panel has a size is kept until it has one.
  let pendingFit = null;
  let lastSize = { w: 0, h: 0 };
  // Room a fit leaves at each side, for what is drawn over the canvas.
  let insets = { top: 0, right: 0, bottom: 0, left: 0 };

  function readColors() {
    const style = getComputedStyle(host);
    return {
      paper: style.getPropertyValue("--paper").trim() || "#ffffff",
      ink: style.getPropertyValue("--ink").trim() || "#10121b",
    };
  }

  const width = () => host.clientWidth;
  const height = () => host.clientHeight;
  const toWorld = (sx, sy) => ({ x: (sx - view.x) / view.scale, y: (sy - view.y) / view.scale });

  function computePositions() {
    zones = [];
    bands = [];
    room = {};
    if (layout === "network") {
      const cards = nodes.map((node) => ({ id: node.id, width: node.w, height: node.h, bucket: node.bucket, bucketLabel: node.bucketLabel, label: node.label }));
      const usable = { w: width() - insets.left - insets.right, h: height() - insets.top - insets.bottom };
      const placed = bucketLayout(cards, edges, { aspect: usable.w > 2 && usable.h > 2 ? usable.w / usable.h : 1.7, sidesFor: sidesOf });
      positions = placed.positions;
      bands = placed.bands;
      room = placed.room;
      // A zone is drawn in the colour of the cards it holds.
      zones = placed.zones.map((zone) => ({ ...zone, color: nodes.find((node) => node.bucket === zone.key)?.color || "#9ca3af" }));
      return;
    }
    const tree = edges.filter((edge) => edge.relation === "hierarchy");
    // Cards must not collide in a row or a column, whatever their label length.
    const widest = Math.max(0, ...nodes.map((node) => node.w));
    const extra = layout === "TD" ? Math.max(0, widest + 28 - 168) : Math.max(0, widest + 60 - 260);
    positions = hierarchicalPositions(nodes, tree, layout, extra);
  }

  function computeBoxes() {
    boxes = new Map();
    for (const node of nodes) {
      const p = positions.get(node.id) || { x: 0, y: 0 };
      boxes.set(node.id, { left: p.x - node.w / 2, right: p.x + node.w / 2, top: p.y - node.h / 2, bottom: p.y + node.h / 2 });
    }
    geometryKey = "";
  }

  function route() {
    const key = JSON.stringify([layout, [...boxes]]);
    if (key === geometryKey) return;
    geometryKey = key;
    // While a card is dragged, only its own connectors are redrawn, as plain
    // elbows behind the cards; everything is routed together once it is dropped.
    if (dragging && drawn.length) {
      drawn = drawn.map((item) => {
        if (item.edge.source !== dragging && item.edge.target !== dragging) return item;
        const from = boxes.get(item.edge.source);
        const to = boxes.get(item.edge.target);
        const a = { x: (from.left + from.right) / 2, y: (from.top + from.bottom) / 2 };
        const b = { x: (to.left + to.right) / 2, y: (to.top + to.bottom) / 2 };
        return { ...item, points: [a, { x: b.x, y: a.y }, b] };
      });
      return;
    }
    const routes = routeEdges(boxes, edges, { direction: layout === "network" ? undefined : layout, sidesFor: sidesOf, room });
    drawn = edges.flatMap((edge) => (routes.has(edge.id) ? [{ edge, points: routes.get(edge.id), labelBox: null }] : []));
  }

  function bounds() {
    if (!boxes.size) return null;
    // The zones and bands are part of what is framed.
    const all = [...boxes.values(), ...zones.map((z) => ({ left: z.x, right: z.x + z.width, top: z.y, bottom: z.y + z.height })), ...bands.map((b) => ({ left: b.x, right: b.x + b.width, top: b.y, bottom: b.y + b.height }))];
    return {
      left: Math.min(...all.map((b) => b.left)),
      right: Math.max(...all.map((b) => b.right)),
      top: Math.min(...all.map((b) => b.top)),
      bottom: Math.max(...all.map((b) => b.bottom)),
    };
  }

  /** A filled arrowhead with its tip at ``tip``, on a line that comes from ``from``. */
  function arrowhead(tip, from, size) {
    const angle = Math.atan2(tip.y - from.y, tip.x - from.x);
    ctx.beginPath();
    ctx.moveTo(tip.x, tip.y);
    ctx.lineTo(tip.x - size * Math.cos(angle) + size * 0.4 * Math.sin(angle), tip.y - size * Math.sin(angle) - size * 0.4 * Math.cos(angle));
    ctx.lineTo(tip.x - size * Math.cos(angle) - size * 0.4 * Math.sin(angle), tip.y - size * Math.sin(angle) + size * 0.4 * Math.cos(angle));
    ctx.closePath();
    ctx.fill();
  }

  /** The realm bands and the bucket zones, under everything else. */
  function drawZones() {
    ctx.save();
    (showBands ? bands : []).forEach((band, i) => {
      if (i === 0 && bands.length > 1) {
        ctx.fillStyle = "rgba(16, 18, 27, 0.03)";
        ctx.fillRect(band.x, band.y, band.width, band.height);
      }
      if (i > 0) {
        ctx.strokeStyle = "rgba(16, 18, 27, 0.14)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(band.x, band.y);
        ctx.lineTo(band.x + band.width, band.y);
        ctx.stroke();
      }
      ctx.fillStyle = "#94a3b8";
      ctx.font = `600 11px ${FONT}`;
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      if ("letterSpacing" in ctx) ctx.letterSpacing = "2px";
      ctx.fillText(band.label, band.x + 20, band.y + 14);
      if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
    });
    for (const zone of showBuckets ? zones : []) {
      ctx.fillStyle = withAlpha(zone.color, 0.07);
      ctx.fillRect(zone.x, zone.y, zone.width, zone.height);
      ctx.strokeStyle = withAlpha(zone.color, 0.55);
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
      ctx.strokeRect(zone.x + 0.5, zone.y + 0.5, zone.width - 1, zone.height - 1);
      ctx.fillStyle = zone.color;
      ctx.font = `700 11px ${FONT}`;
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.fillText(`${zone.label.toUpperCase()} · ${zone.type}`, zone.x + 12, zone.y + 10);
    }
    ctx.restore();
  }

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = width();
    const h = height();
    if (w < 2 || h < 2) return;
    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }
    route();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.scale, view.scale);

    drawZones();
    const active = (item) => item.edge.id === selectedEdge || item.edge.id === hoverEdge;
    // With a class selected, its own connections stand out and the rest recede.
    const incident = (item) =>
      selectedNode !== null && (item.edge.source === selectedNode || item.edge.target === selectedNode);
    const recedes = (item) => !active(item) && (selectedEdge !== null || (selectedNode !== null && !incident(item)));
    // Labels on every connector are unreadable once there are many: at rest
    // they show only where the eye is, on a hovered, selected or incident one.
    const crowded = edges.length > 40;
    const emphasised = (item) => active(item) || incident(item);
    const ordered = [...drawn.filter((item) => !emphasised(item)), ...drawn.filter(emphasised)];
    ctx.lineJoin = "miter";
    ctx.lineCap = "butt";
    for (const item of ordered) {
      const { edge, points } = item;
      const hierarchy = edge.relation === "hierarchy";
      const highlighted = active(item);
      const dimmed = recedes(item);
      const base = hierarchy ? colors.ink : EDGE_COLOR;
      // Many connectors at rest are drawn lighter, so the boxes stay the subject.
      ctx.globalAlpha = dimmed ? 0.35 : crowded && !emphasised(item) ? 0.6 : 1;
      ctx.strokeStyle = dimmed ? "rgba(148,163,184,0.5)" : base;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = highlighted ? 3 : hierarchy ? 1 : 2;
      ctx.setLineDash(hierarchy ? [5, 5] : []);
      ctx.beginPath();
      points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
      ctx.stroke();
      ctx.setLineDash([]);
      const size = Math.max(5, 12 * (highlighted ? 1 : 0.8));
      arrowhead(points[points.length - 1], points[points.length - 2], size);
      // Two relations that are each other's inverse are one line with an arrow at each end.
      if (edge.both) arrowhead(points[0], points[1], size);
    }
    // Labels last, at full opacity, so they stay readable over crossing links.
    ctx.globalAlpha = 1;
    for (const item of ordered) {
      item.labelBox = null;
      if (item.edge.relation === "hierarchy" || !item.edge.label || view.scale < 0.4) continue;
      if (recedes(item) || (crowded && !emphasised(item))) continue;
      const size = active(item) ? 10 : 9;
      ctx.font = `${size}px ${FONT}`;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      const label = routeLabel(item.points);
      const lines = item.edge.label.split("\n");
      const textWidth = Math.max(...lines.map((line) => ctx.measureText(line).width));
      const textHeight = lines.length * (size + 3);
      const x = label.horizontal ? label.x - textWidth / 2 : label.x + 6;
      const y = label.horizontal ? label.y - textHeight / 2 - 4 : label.y;
      item.labelBox = { left: x - 3, right: x + textWidth + 3, top: y - textHeight / 2 - 2, bottom: y + textHeight / 2 + 2 };
      ctx.fillStyle = colors.paper;
      ctx.fillRect(item.labelBox.left, item.labelBox.top, item.labelBox.right - item.labelBox.left, item.labelBox.bottom - item.labelBox.top);
      ctx.fillStyle = EDGE_LABEL_COLOR;
      lines.forEach((line, i) => ctx.fillText(line, x, y + (i - (lines.length - 1) / 2) * (size + 3)));
    }

    for (const node of nodes) {
      const box = boxes.get(node.id);
      const selected = node.id === selectedNode;
      // Faded toward white, not transparent: a transparent card would show the
      // connector that runs beneath it.
      const dimmed = selectedNode !== null && !selected;
      ctx.fillStyle = dimmed ? fadeTowardWhite(node.color, 0.82) : node.color;
      ctx.fillRect(box.left, box.top, node.w, node.h);
      ctx.strokeStyle = dimmed ? fadeTowardWhite(node.border, 0.7) : node.border;
      ctx.lineWidth = selected ? 3 : 2;
      ctx.strokeRect(box.left + 1, box.top + 1, node.w - 2, node.h - 2);
      ctx.fillStyle = dimmed ? DIMMED_TEXT : "#ffffff";
      ctx.font = `600 ${LABEL_FONT_SIZE}px ${FONT}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const cx = (box.left + box.right) / 2;
      const cy = (box.top + box.bottom) / 2;
      node.lines.forEach((line, i) => ctx.fillText(line, cx, cy + (i - (node.lines.length - 1) / 2) * LABEL_LINE_HEIGHT));
    }
    ctx.restore();
  }

  function fit({ minScale = 0, maxScale = MAX_SCALE } = {}) {
    const b = bounds();
    const w = width();
    const h = height();
    if (!b) return;
    if (w < 2 || h < 2) {
      pendingFit = { minScale, maxScale };
      return;
    }
    pendingFit = null;
    const pad = 48;
    const areaW = w - insets.left - insets.right;
    const areaH = h - insets.top - insets.bottom;
    const fitted = Math.min((areaW - pad * 2) / (b.right - b.left), (areaH - pad * 2) / (b.bottom - b.top));
    const scale = Math.min(maxScale, Math.max(MIN_SCALE, Number.isFinite(fitted) ? fitted : 1, minScale));
    // The view is set from the size it has now: the resize observer must not
    // shift it a second time for a resize that already happened.
    lastSize = { w, h };
    view = {
      scale,
      x: insets.left + areaW / 2 - ((b.left + b.right) / 2) * scale,
      y: insets.top + areaH / 2 - ((b.top + b.bottom) / 2) * scale,
    };
    draw();
  }

  /** Pan to a card, keeping the zoom unless it is too small to read. */
  function focus(id) {
    const box = boxes.get(id);
    if (!box) return;
    const scale = Math.max(view.scale, 0.75);
    lastSize = { w: width(), h: height() };
    view = { scale, x: width() / 2 - ((box.left + box.right) / 2) * scale, y: height() / 2 - ((box.top + box.bottom) / 2) * scale };
    draw();
  }

  function zoomAt(sx, sy, factor) {
    const world = toWorld(sx, sy);
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale * factor));
    view = { scale, x: sx - world.x * scale, y: sy - world.y * scale };
    draw();
  }

  function nodeAt(world) {
    for (let i = nodes.length - 1; i >= 0; i -= 1) {
      const box = boxes.get(nodes[i].id);
      if (world.x >= box.left && world.x <= box.right && world.y >= box.top && world.y <= box.bottom) return nodes[i].id;
    }
    return null;
  }

  function edgeAt(world) {
    const tolerance = 6 / Math.max(view.scale, 0.05);
    let nearest = tolerance;
    let id = null;
    for (const item of drawn) {
      const box = item.labelBox;
      if (box && world.x >= box.left && world.x <= box.right && world.y >= box.top && world.y <= box.bottom) return item.edge.id;
      const d = routeDistance(world, item.points);
      if (d <= nearest) {
        nearest = d;
        id = item.edge.id;
      }
    }
    return id;
  }

  const local = (event) => {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  function onPointerDown(event) {
    const at = local(event);
    const world = toWorld(at.x, at.y);
    const node = nodeAt(world);
    pointer = { id: node, edge: node ? null : edgeAt(world), sx: at.x, sy: at.y, moved: false, grab: node ? { x: world.x - positions.get(node).x, y: world.y - positions.get(node).y } : null, view: { ...view } };
    canvas.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event) {
    const at = local(event);
    if (!pointer) {
      const world = toWorld(at.x, at.y);
      const node = nodeAt(world);
      const edge = node ? null : edgeAt(world);
      if (node !== hoverNode || edge !== hoverEdge) {
        hoverNode = node;
        hoverEdge = edge;
        canvas.style.cursor = node || edge ? "pointer" : "";
        draw();
      }
      return;
    }
    if (Math.hypot(at.x - pointer.sx, at.y - pointer.sy) > 4) pointer.moved = true;
    if (!pointer.moved) return;
    if (pointer.id) {
      dragging = pointer.id;
      const world = toWorld(at.x, at.y);
      positions.set(pointer.id, { x: world.x - pointer.grab.x, y: world.y - pointer.grab.y });
      computeBoxes();
    } else {
      view = { ...pointer.view, x: pointer.view.x + at.x - pointer.sx, y: pointer.view.y + at.y - pointer.sy };
    }
    draw();
  }

  function onPointerUp() {
    if (dragging) {
      // Dropped: route every connector again, together.
      dragging = null;
      geometryKey = "";
      draw();
    }
    if (pointer && !pointer.moved) {
      if (pointer.id) onSelectNode?.(pointer.id);
      else if (pointer.edge) onSelectEdge?.(pointer.edge);
      else {
        onSelectNode?.(null);
        onSelectEdge?.(null);
      }
    }
    pointer = null;
  }

  function onDoubleClick(event) {
    const at = local(event);
    const node = nodeAt(toWorld(at.x, at.y));
    if (node) onOpenNode?.(node);
  }

  function onLeave() {
    if (hoverNode || hoverEdge) {
      hoverNode = null;
      hoverEdge = null;
      canvas.style.cursor = "";
      draw();
    }
  }

  function onWheel(event) {
    event.preventDefault();
    const at = local(event);
    zoomAt(at.x, at.y, event.deltaY < 0 ? 1.1 : 1 / 1.1);
  }

  function onZoomButton(event) {
    const kind = event.target.closest("[data-zoom]")?.dataset.zoom;
    if (kind === "in") zoomAt(width() / 2, height() / 2, 1.2);
    else if (kind === "out") zoomAt(width() / 2, height() / 2, 1 / 1.2);
    else if (kind === "fit") fit();
  }

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerUp);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("dblclick", onDoubleClick);
  canvas.addEventListener("wheel", onWheel, { passive: false });
  host.querySelector(".network-zoom").addEventListener("click", onZoomButton);

  // Keep whatever is at the centre of the view there when the panel resizes.
  const observer = new ResizeObserver(() => {
    const w = width();
    const h = height();
    if (w < 2 || h < 2) return;
    if (lastSize.w >= 2 && lastSize.h >= 2) {
      view = { ...view, x: view.x + (w - lastSize.w) / 2, y: view.y + (h - lastSize.h) / 2 };
    }
    lastSize = { w, h };
    colors = readColors();
    if (pendingFit) fit({ ...pendingFit });
    else draw();
  });
  observer.observe(host);

  return {
    /**
     * Replace the network. ``nodes`` are {id, label, bucket, color, border};
     * ``edges`` {id, source, target, label, relation}. Refits unless ``refit`` is false.
     */
    setData(next, { refit = true } = {}) {
      layout = next.layout || "network";
      insets = { top: 0, right: 0, bottom: 0, left: 0, ...(next.insets || {}) };
      const known = new Set(next.nodes.map((node) => node.id));
      edges = next.edges.filter((edge) => known.has(edge.source) && known.has(edge.target));
      // The zone layout fixes the sides connectors use, by the buckets they join;
      // the tree layouts leave every connector free.
      const bucketOf = new Map(next.nodes.map((node) => [node.id, node.bucket]));
      sidesOf = layout === "network" ? edgeSides((id) => bucketOf.get(id)) : null;
      // Each connector needs room of its own along a side: a class that many end on is a larger card.
      const loads = sideLoads(edges, sidesOf);
      nodes = next.nodes.map((node) => {
        const lines = wrapLabel(node.label);
        const { width: w, height: h } = cardSize(lines, loads.get(node.id));
        return { ...node, lines, w, h };
      });
      byId = new Map(nodes.map((node) => [node.id, node]));
      if (selectedNode && !byId.has(selectedNode)) selectedNode = null;
      if (selectedEdge && !edges.some((edge) => edge.id === selectedEdge)) selectedEdge = null;
      computePositions();
      computeBoxes();
      colors = readColors();
      if (refit) fit({ minScale: layout === "network" ? 0.5 : 0.35, maxScale: AUTO_FIT_MAX });
      else draw();
    },
    /**
     * Which zones are drawn, each with its title: the top level (Occurrents,
     * Continuants) and the seven buckets. The cards do not move.
     */
    setZonesVisible({ topLevel = showBands, buckets = showBuckets } = {}) {
      showBands = Boolean(topLevel);
      showBuckets = Boolean(buckets);
      draw();
    },
    setSelection({ nodeId = null, edgeId = null } = {}) {
      selectedNode = nodeId;
      selectedEdge = edgeId;
      draw();
    },
    focus,
    fit: () => fit(),
    resize() {
      requestAnimationFrame(draw);
    },
    /** For tests: where a card is, in screen pixels. */
    cardAt(id) {
      const box = boxes.get(id);
      if (!box) return null;
      return { x: ((box.left + box.right) / 2) * view.scale + view.x, y: ((box.top + box.bottom) / 2) * view.scale + view.y };
    },
    get scale() {
      return view.scale;
    },
    destroy() {
      observer.disconnect();
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointercancel", onPointerUp);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("dblclick", onDoubleClick);
      canvas.removeEventListener("wheel", onWheel);
      host.innerHTML = "";
    },
  };
}
