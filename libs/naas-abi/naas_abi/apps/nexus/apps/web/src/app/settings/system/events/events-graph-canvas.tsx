'use client';

/**
 * Minimum canvas engine adapted from the personnel cockpit graph page
 * (force step, overlap resolve, 2D/3D camera projection, node/edge draw).
 * Visualizes one event JSON tree plus BFO bucket hubs for mapped columns.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  bfoColumnSwatch,
  buildEventJsonGraph,
  emptyEventsGraph,
  pathIsOnTrail,
  type EventsGraph,
  type EventsGraphEdgeKind,
  type EventsGraphKind,
  type EventsGraphNode,
} from './events-graph';
import { type PlatformEvent } from './bfo-event-projection';

type GraphView = '2d' | '3d';

interface SimNode extends EventsGraphNode {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  homeX: number;
  homeY: number;
  _px?: number;
  _py?: number;
  _ds?: number;
  _depth?: number;
}

interface SimEdge {
  a: SimNode;
  b: SimNode;
  label: string;
  kind: EventsGraphEdgeKind;
  hidden: boolean;
  physicsLength?: number;
  linkWeight?: number;
}

const NODE_RADIUS: Record<EventsGraphKind, number> = {
  root: 36,
  object: 28,
  array: 28,
  value: 20,
  bucket: 32,
};

const KIND_PALETTE: Record<EventsGraphKind, { color: string; border: string }> = {
  root: { color: '#3f3f46', border: '#18181b' },
  object: { color: '#71717a', border: '#52525b' },
  array: { color: '#71717a', border: '#52525b' },
  value: { color: '#a1a1aa', border: '#71717a' },
  bucket: { color: '#6b7280', border: '#4b5563' },
};

const CAMERA_DISTANCE = 2400;
const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;
const LABEL_FONT = 13;
const LABEL_LINE = 16;

const VIEW_PARAMS: Record<GraphView, { linkDistance: number; repulsion: number; zoom: number; settleMs: number }> = {
  '2d': { linkDistance: 190, repulsion: 5000, zoom: 0.7, settleMs: 1600 },
  '3d': { linkDistance: 260, repulsion: 7000, zoom: 0.5, settleMs: 2200 },
};

function palette(node: EventsGraphNode) {
  if (node.kind === 'bucket' && node.bucket) return bfoColumnSwatch(node.bucket);
  return KIND_PALETTE[node.kind];
}

function nodeRadius(kind: EventsGraphKind) {
  return NODE_RADIUS[kind];
}

function nodeHighlighted(node: EventsGraphNode, trail: string | null, edges: SimEdge[]) {
  if (pathIsOnTrail(node.path, trail)) return true;
  if (!trail) return false;
  if (node.kind === 'bucket') {
    return edges.some((edge) => edge.kind === 'bucket' && edge.a.id === node.id && pathIsOnTrail(edge.b.path, trail));
  }
  return edges.some(
    (edge) => edge.kind === 'bucket' && edge.b.path === node.path && (edge.a.path === trail || pathIsOnTrail(edge.a.path, trail)),
  );
}

function wrapLabel(label: string, maxChars: number, maxLines: number): string[] {
  const words = label.trim().replace(/\s+/g, ' ').split(' ');
  const lines: string[] = [];
  let current = '';
  const flush = () => {
    if (!current) return;
    lines.push(current.length > maxChars ? `${current.slice(0, maxChars - 3)}...` : current);
    current = '';
  };
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
      continue;
    }
    flush();
    if (lines.length >= maxLines) break;
    current = word.length > maxChars ? `${word.slice(0, maxChars - 3)}...` : word;
  }
  if (current && lines.length < maxLines) flush();
  return lines.slice(0, maxLines);
}

function fitLabel(text: string, maxChars: number): string {
  const label = text.trim();
  if (!label) return '';
  if (label.length <= maxChars) return label;
  if (!/\s/.test(label)) return `${label.slice(0, maxChars - 3)}...`;
  return wrapLabel(label, maxChars, 1)[0] ?? `${label.slice(0, maxChars - 3)}...`;
}

function labelLines(node: EventsGraphNode): string[] {
  if (node.kind === 'root' || node.kind === 'bucket') {
    const line = fitLabel(node.label, 22);
    return line ? [line] : [];
  }
  const key = node.key.trim();
  const isIndex = key.startsWith('[');
  const lines: string[] = [];
  if (key && !isIndex) lines.push(fitLabel(key, 20));
  if (node.kind === 'value') {
    const value = node.label.trim();
    if (value && value !== key) lines.push(fitLabel(value, 20));
  } else if (!key) {
    const line = fitLabel(node.label, 20);
    if (line) lines.push(line);
  }
  return lines.slice(0, 2);
}

function resolveOverlaps(nodes: SimNode[], iterations = 80, minGap = 28) {
  for (let iter = 0; iter < iterations; iter++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const need = nodeRadius(a.kind) + nodeRadius(b.kind) + 18 + minGap;
        const overlap = need - dist;
        if (overlap <= 0) continue;
        if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) {
          dx = (j - i) * 0.37;
          dy = 1;
        }
        const push = overlap * 0.55 + 0.5;
        const nx = dx / dist;
        const ny = dy / dist;
        a.x -= nx * push * 0.5;
        a.y -= ny * push * 0.5;
        b.x += nx * push * 0.5;
        b.y += ny * push * 0.5;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

function placeBucketHubs(nodes: SimNode[], edges: SimEdge[], stored: Map<string, { x: number; y: number; z: number }>) {
  const hubs = nodes.filter((node) => node.kind === 'bucket');
  hubs.forEach((hub, index) => {
    const prev = stored.get(hub.id);
    if (prev) {
      hub.x = prev.x;
      hub.y = prev.y;
      hub.z = prev.z;
      hub.homeX = hub.x;
      hub.homeY = hub.y;
      return;
    }
    const targets = edges.filter((edge) => edge.kind === 'bucket' && edge.a.id === hub.id).map((edge) => edge.b);
    const cx = targets.length ? targets.reduce((sum, node) => sum + node.x, 0) / targets.length : 0;
    const cy = targets.length ? targets.reduce((sum, node) => sum + node.y, 0) / targets.length : 0;
    const angle = -Math.PI / 2 + (index - (hubs.length - 1) / 2) * 0.42;
    hub.x = cx + Math.cos(angle) * 170;
    hub.y = cy + Math.sin(angle) * 140 - 52;
    hub.z = hub.y * 0.18;
    hub.homeX = hub.x;
    hub.homeY = hub.y;
  });
}

function seedTreeLayout(nodes: SimNode[], edges: SimEdge[], stored: Map<string, { x: number; y: number; z: number }>) {
  const children = new Map<string, SimNode[]>();
  for (const edge of edges) {
    if (edge.kind !== 'json') continue;
    const list = children.get(edge.a.id) ?? [];
    list.push(edge.b);
    children.set(edge.a.id, list);
  }
  const root = nodes.find((n) => n.kind === 'root') ?? nodes[0];
  if (!root) return;

  const GAP_X = 140;
  const GAP_Y = 160;

  const widthCache = new Map<string, number>();
  const subtreeWidth = (id: string): number => {
    const cached = widthCache.get(id);
    if (cached != null) return cached;
    const kids = children.get(id) ?? [];
    const width = kids.length === 0 ? 1 : kids.reduce((sum, kid) => sum + subtreeWidth(kid.id), 0);
    widthCache.set(id, width);
    return width;
  };

  const place = (node: SimNode, x: number, y: number) => {
    const prev = stored.get(node.id);
    if (prev) {
      node.x = prev.x;
      node.y = prev.y;
      node.z = prev.z;
    } else {
      node.x = x;
      node.y = y;
      node.z = y * 0.18;
    }
    node.homeX = node.x;
    node.homeY = node.y;
    const kids = children.get(node.id) ?? [];
    const widths = kids.map((kid) => subtreeWidth(kid.id));
    const total = widths.reduce((sum, w) => sum + w, 0) || 1;
    let cursor = x - ((total - 1) * GAP_X) / 2;
    kids.forEach((kid, i) => {
      const w = widths[i];
      const cx = cursor + ((w - 1) * GAP_X) / 2;
      place(kid, cx, y + GAP_Y);
      cursor += w * GAP_X;
    });
  };

  place(root, 0, 0);
  placeBucketHubs(nodes, edges, stored);
  resolveOverlaps(nodes, 80, 28);
  for (const node of nodes) {
    if (!stored.has(node.id)) {
      node.homeX = node.x;
      node.homeY = node.y;
    }
  }
}

function physicsStep(
  nodes: SimNode[],
  edges: SimEdge[],
  alpha: number,
  params: { linkDistance: number; repulsion: number },
) {
  for (const node of nodes) {
    node.vx *= 0.68;
    node.vy *= 0.68;
  }

  if (!(edges as SimEdge[] & { degreesCounted?: boolean }).degreesCounted) {
    const degree = new Map<string, number>();
    for (const edge of edges) {
      degree.set(edge.a.id, (degree.get(edge.a.id) || 0) + 1);
      degree.set(edge.b.id, (degree.get(edge.b.id) || 0) + 1);
    }
    for (const edge of edges) {
      edge.linkWeight = 1 / Math.max(1, Math.min(degree.get(edge.a.id) || 1, degree.get(edge.b.id) || 1));
    }
    (edges as SimEdge[] & { degreesCounted?: boolean }).degreesCounted = true;
  }

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let distance = Math.hypot(dx, dy);
      if (distance < 0.01) {
        dx = (j - i) * 0.37;
        dy = 1;
        distance = Math.hypot(dx, dy);
      }
      const minimumDistance = 80;
      let strength = (alpha * params.repulsion) / (distance * distance);
      if (distance < minimumDistance) {
        strength += ((minimumDistance - distance) / minimumDistance) * 1.2 * alpha;
      }
      const forceX = (dx / distance) * strength;
      const forceY = (dy / distance) * strength;
      a.vx -= forceX;
      a.vy -= forceY;
      b.vx += forceX;
      b.vy += forceY;
    }
  }

  for (const edge of edges) {
    const a = edge.a;
    const b = edge.b;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.hypot(dx, dy) || 0.01;
    if (!Number.isFinite(edge.physicsLength)) {
      edge.physicsLength = edge.kind === 'bucket' ? params.linkDistance * 1.15 : params.linkDistance;
    }
    const strength = (distance - (edge.physicsLength ?? params.linkDistance)) * 0.5 * (edge.linkWeight ?? 1) * alpha;
    const forceX = (dx / distance) * strength;
    const forceY = (dy / distance) * strength;
    a.vx += forceX;
    a.vy += forceY;
    b.vx -= forceX;
    b.vy -= forceY;
  }

  for (const node of nodes) {
    node.vx += (node.homeX - node.x) * 0.04 * alpha;
    node.vy += (node.homeY - node.y) * 0.04 * alpha;
    if (node.kind === 'root' || node.kind === 'bucket') {
      node.vx += (node.homeX - node.x) * 0.05 * alpha;
      node.vy += (node.homeY - node.y) * 0.05 * alpha;
    }
  }

  for (const node of nodes) {
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 10) {
      node.vx = (node.vx / speed) * 10;
      node.vy = (node.vy / speed) * 10;
    }
    node.x += node.vx;
    node.y += node.vy;
  }
  resolveOverlaps(nodes, 2, 24);
}

function projectNodes(nodes: SimNode[], view: GraphView, yaw: number, pitch: number) {
  if (view !== '3d') {
    for (const node of nodes) {
      node._px = undefined;
      node._py = undefined;
      node._ds = 1;
      node._depth = 0;
    }
    return;
  }
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  for (const node of nodes) {
    const z = node.z || 0;
    const x1 = node.x * cosYaw + z * sinYaw;
    const z1 = -node.x * sinYaw + z * cosYaw;
    const y1 = node.y * cosPitch - z1 * sinPitch;
    const z2 = node.y * sinPitch + z1 * cosPitch;
    const k = CAMERA_DISTANCE / Math.max(400, CAMERA_DISTANCE + z2);
    node._px = x1 * k;
    node._py = y1 * k;
    node._ds = k;
    node._depth = z2;
  }
}

function viewX(node: SimNode) {
  return node._px ?? node.x;
}

function viewY(node: SimNode) {
  return node._py ?? node.y;
}

function viewScale(node: SimNode) {
  return node._ds ?? 1;
}

function readTheme(el: HTMLElement) {
  const style = getComputedStyle(el);
  return {
    ink: style.getPropertyValue('--foreground-hex').trim() || '#18181B',
    muted: style.getPropertyValue('--muted-foreground-hex').trim() || '#71717A',
    canvas: style.getPropertyValue('--background-hex').trim() || '#FCFCFC',
  };
}

type GraphApi = {
  dispose: () => void;
  focusPath: (path: string | null) => void;
  reset: () => void;
  redraw: () => void;
};

interface MountOptions {
  graph: EventsGraph;
  view: GraphView;
  highlightedPath: () => string | null;
  onSelectPath: (path: string) => void;
  stored: Map<string, { x: number; y: number; z: number }>;
  camera: { x: number; y: number; scale: number; view: GraphView } | null;
  onCamera: (camera: { x: number; y: number; scale: number; view: GraphView }) => void;
}

function mountEventsGraph(stage: HTMLElement, canvas: HTMLCanvasElement, options: MountOptions): GraphApi {
  const maybeCtx = canvas.getContext('2d');
  const noop: GraphApi = {
    dispose() {},
    focusPath() {},
    reset() {},
    redraw() {},
  };
  if (!maybeCtx) return noop;
  const ctx: CanvasRenderingContext2D = maybeCtx;

  const params = VIEW_PARAMS[options.view];
  const nodeMap = new Map<string, SimNode>();
  const simNodes: SimNode[] = options.graph.nodes.map((n) => {
    const node: SimNode = {
      ...n,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      homeX: 0,
      homeY: 0,
    };
    nodeMap.set(n.id, node);
    return node;
  });
  const simEdges: SimEdge[] = [];
  for (const edge of options.graph.edges) {
    const a = nodeMap.get(edge.source);
    const b = nodeMap.get(edge.target);
    if (!a || !b) continue;
    simEdges.push({ a, b, label: edge.label, kind: edge.kind, hidden: false });
  }
  seedTreeLayout(simNodes, simEdges, options.stored);

  let pan = { x: options.camera?.view === options.view ? options.camera.x : 0, y: options.camera?.view === options.view ? options.camera.y : 0 };
  let scale = options.camera?.view === options.view ? options.camera.scale : params.zoom;
  let recentreToken = 0;
  let dragging: SimNode | null = null;
  let panning: { x: number; y: number } | null = null;
  let orbiting: { x: number; y: number; yaw: number; pitch: number } | null = null;
  let pointerStart: { node: SimNode | null; x: number; y: number; moved: boolean } | null = null;
  let offset = { x: 0, y: 0 };
  const persistCamera = () => {
    options.onCamera({ x: pan.x, y: pan.y, scale, view: options.view });
  };
  const orbit = { yaw: -0.6, pitch: 0.35 };
  let raf = 0;
  let running = true;

  const persist = () => {
    for (const node of simNodes) {
      options.stored.set(node.id, { x: node.x, y: node.y, z: node.z });
    }
  };

  const colors = () => readTheme(stage);

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function screenToWorld(sx: number, sy: number) {
    return {
      x: (sx - canvas.clientWidth / 2 - pan.x) / scale,
      y: (sy - canvas.clientHeight / 2 - pan.y) / scale,
    };
  }

  function zoomAt(sx: number, sy: number, factor: number) {
    const wx = (sx - canvas.clientWidth / 2 - pan.x) / scale;
    const wy = (sy - canvas.clientHeight / 2 - pan.y) / scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
    pan.x = sx - canvas.clientWidth / 2 - wx * scale;
    pan.y = sy - canvas.clientHeight / 2 - wy * scale;
    draw();
  }

  function centreOnNode(node: SimNode) {
    const targetX = -viewX(node) * scale;
    const targetY = -viewY(node) * scale;
    const startX = pan.x;
    const startY = pan.y;
    const startedAt = performance.now();
    const duration = 260;
    const token = ++recentreToken;
    const frame = (now: number) => {
      if (token !== recentreToken) return;
      const t = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - (1 - t) ** 3;
      pan.x = startX + (targetX - startX) * eased;
      pan.y = startY + (targetY - startY) * eased;
      persistCamera();
      draw();
      if (t < 1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  function hit(pos: { x: number; y: number }) {
    for (let i = simNodes.length - 1; i >= 0; i--) {
      const n = simNodes[i];
      const r = nodeRadius(n.kind) * viewScale(n) + 5;
      if (Math.hypot(viewX(n) - pos.x, viewY(n) - pos.y) <= r) return n;
    }
    return null;
  }

  function drawEdge(e: SimEdge, theme: ReturnType<typeof readTheme>) {
    const trail = options.highlightedPath();
    const onTrail =
      nodeHighlighted(e.a, trail, simEdges) || nodeHighlighted(e.b, trail, simEdges);
    const pal = palette(e.kind === 'bucket' ? e.a : e.b);
    const ax = viewX(e.a);
    const ay = viewY(e.a);
    const bx = viewX(e.b);
    const by = viewY(e.b);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = onTrail ? theme.ink : pal.border;
    ctx.globalAlpha = options.view === '3d' ? 0.55 : onTrail ? 0.95 : 0.55;
    ctx.lineWidth = (onTrail ? 2.4 : e.kind === 'bucket' ? 1.8 : 1.6) / Math.max(scale, 0.6);
    if (e.kind === 'bucket') ctx.setLineDash([7 / Math.max(scale, 0.6), 5 / Math.max(scale, 0.6)]);
    ctx.stroke();
    ctx.setLineDash([]);
    const angle = Math.atan2(by - ay, bx - ax);
    const size = 12 / Math.max(scale, 0.6);
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx - size * Math.cos(angle - Math.PI / 7), by - size * Math.sin(angle - Math.PI / 7));
    ctx.lineTo(bx - size * Math.cos(angle + Math.PI / 7), by - size * Math.sin(angle + Math.PI / 7));
    ctx.closePath();
    ctx.fillStyle = onTrail ? theme.ink : pal.border;
    ctx.fill();
    ctx.globalAlpha = 1;
    if (e.kind === 'bucket') return;
    if (e.label === e.b.key || e.label === e.b.label) return;
    if (options.view === '3d' && (viewScale(e.a) + viewScale(e.b)) / 2 < 0.88) return;
    const mx = (ax + bx) / 2;
    const my = (ay + by) / 2;
    ctx.font = `12px ui-sans-serif, system-ui, sans-serif`;
    const textW = ctx.measureText(e.label).width;
    ctx.fillStyle = theme.canvas;
    ctx.fillRect(mx - textW / 2 - 4, my - 9, textW + 8, 18);
    ctx.fillStyle = onTrail ? theme.ink : theme.muted;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(e.label, mx, my);
  }

  function drawNode(n: SimNode, theme: ReturnType<typeof readTheme>) {
    const r = nodeRadius(n.kind) * viewScale(n);
    const pal = palette(n);
    const trail = options.highlightedPath();
    const selected = trail != null && n.path === trail;
    const onTrail = nodeHighlighted(n, trail, simEdges);
    ctx.beginPath();
    ctx.arc(viewX(n), viewY(n), r, 0, Math.PI * 2);
    ctx.fillStyle = pal.color;
    ctx.fill();
    ctx.strokeStyle = pal.border;
    ctx.lineWidth = n.kind === 'root' || n.kind === 'bucket' ? 2.4 : 1.8;
    ctx.stroke();
    if (n.kind === 'bucket') {
      ctx.beginPath();
      ctx.arc(viewX(n), viewY(n), r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = pal.border;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    if (onTrail) {
      ctx.strokeStyle = theme.ink;
      ctx.lineWidth = selected ? 3 : 2.2;
      ctx.stroke();
    }
    const depth = viewScale(n);
    if (options.view === '3d' && depth < 0.88) return;
    const lines = labelLines(n);
    ctx.font = `600 ${LABEL_FONT * depth}px ui-sans-serif, system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const lh = LABEL_LINE * depth;
    let y = viewY(n) + r + 6 * depth;
    for (const line of lines) {
      ctx.lineWidth = 4 * depth;
      ctx.strokeStyle = theme.canvas;
      ctx.strokeText(line, viewX(n), y);
      ctx.fillStyle = theme.ink;
      ctx.fillText(line, viewX(n), y);
      y += lh;
    }
  }

  function draw() {
    const theme = colors();
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = theme.canvas;
    ctx.fillRect(0, 0, w, h);
    projectNodes(simNodes, options.view, orbit.yaw, orbit.pitch);
    ctx.save();
    ctx.translate(w / 2 + pan.x, h / 2 + pan.y);
    ctx.scale(scale, scale);
    if (options.view === '3d') {
      const orderedEdges = [...simEdges].sort(
        (a, b) => ((a.a._depth ?? 0) + (a.b._depth ?? 0)) / 2 - ((b.a._depth ?? 0) + (b.b._depth ?? 0)) / 2,
      );
      orderedEdges.reverse();
      for (const e of orderedEdges) drawEdge(e, theme);
      const ordered = [...simNodes].sort((a, b) => (b._depth ?? 0) - (a._depth ?? 0));
      for (const n of ordered) {
        const fade = Math.min(1, Math.max(0.42, (viewScale(n) - 0.6) / 0.4));
        ctx.globalAlpha = fade;
        drawNode(n, theme);
      }
      ctx.globalAlpha = 1;
    } else {
      for (const e of simEdges) drawEdge(e, theme);
      for (const n of simNodes) drawNode(n, theme);
    }
    ctx.restore();
  }

  const onPointerDown = (ev: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
    const node = hit(pos);
    pointerStart = { node, x: ev.clientX, y: ev.clientY, moved: false };
    if (node && options.view === '2d') {
      dragging = node;
      offset = { x: pos.x - node.x, y: pos.y - node.y };
    } else if (options.view === '3d' && !node) {
      orbiting = { x: ev.clientX, y: ev.clientY, yaw: orbit.yaw, pitch: orbit.pitch };
    } else if (!node) {
      panning = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
    }
    recentreToken += 1;
    canvas.setPointerCapture(ev.pointerId);
  };

  const onPointerMove = (ev: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    if (pointerStart && Math.hypot(ev.clientX - pointerStart.x, ev.clientY - pointerStart.y) > 4) {
      pointerStart.moved = true;
    }
    if (orbiting) {
      orbit.yaw = orbiting.yaw + (ev.clientX - orbiting.x) * 0.008;
      orbit.pitch = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, orbiting.pitch + (ev.clientY - orbiting.y) * 0.006));
      draw();
    } else if (dragging) {
      const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      dragging.x = pos.x - offset.x;
      dragging.y = pos.y - offset.y;
      resolveOverlaps(simNodes, 12, 12);
      persist();
      persistCamera();
      draw();
    } else if (panning) {
      pan.x = ev.clientX - panning.x;
      pan.y = ev.clientY - panning.y;
      persistCamera();
      draw();
    } else {
      const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      const hovered = hit(pos);
      canvas.title = hovered?.title ?? '';
    }
  };

  const onPointerUp = () => {
    if (pointerStart && !pointerStart.moved && pointerStart.node) {
      options.onSelectPath(pointerStart.node.path);
    }
    dragging = null;
    panning = null;
    orbiting = null;
    pointerStart = null;
    persist();
  };

  const resetView = () => {
    scale = params.zoom;
    const focus =
      simNodes.find((n) => n.path === options.highlightedPath()) ??
      simNodes.find((n) => n.kind === 'root') ??
      simNodes[0];
    pan.x = -(focus?.x ?? 0) * scale;
    pan.y = -(focus?.y ?? 0) * scale;
    persistCamera();
    draw();
  };

  const onDblClick = (ev: MouseEvent) => {
    const rect = canvas.getBoundingClientRect();
    const node = hit(screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top));
    if (!node) {
      resetView();
      return;
    }
    options.onSelectPath(node.path);
    centreOnNode(node);
  };

  const onWheel = (ev: WheelEvent) => {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, ev.deltaY < 0 ? 1.1 : 0.9);
    persistCamera();
  };

  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('dblclick', onDblClick);
  canvas.addEventListener('wheel', onWheel, { passive: false });

  const ro = new ResizeObserver(resize);
  ro.observe(stage);
  resize();

  const started = performance.now();
  const tick = () => {
    if (!running) return;
    const elapsed = performance.now() - started;
    if (elapsed < params.settleMs) {
      const alpha = Math.max(0.04, 1 - elapsed / params.settleMs);
      physicsStep(simNodes, simEdges, alpha, params);
      persist();
      draw();
      raf = requestAnimationFrame(tick);
      return;
    }
    persist();
    draw();
  };
  raf = requestAnimationFrame(tick);

  if (!options.camera || options.camera.view !== options.view) {
    const root = simNodes.find((n) => n.kind === 'root') ?? simNodes[0];
    if (root) {
      pan.x = -root.x * scale;
      pan.y = -root.y * scale;
    }
  }

  return {
    dispose() {
      running = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('dblclick', onDblClick);
      canvas.removeEventListener('wheel', onWheel);
      persist();
      persistCamera();
    },
    focusPath(path: string | null) {
      if (!path) {
        draw();
        return;
      }
      const node = simNodes.find((n) => n.path === path);
      if (node) centreOnNode(node);
      else draw();
    },
    reset() {
      resetView();
    },
    redraw: draw,
  };
}

export function EventsGraphCanvas({
  event,
  projection = '2d',
  onViewJson,
}: {
  event: PlatformEvent | null;
  projection?: GraphView;
  onViewJson?: () => void;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const apiRef = useRef<GraphApi | null>(null);
  const highlightRef = useRef<string | null>(null);
  const storedRef = useRef(new Map<string, { x: number; y: number; z: number }>());
  const cameraRef = useRef<{ x: number; y: number; scale: number; view: GraphView } | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string | null>(null);

  highlightRef.current = highlightedPath;

  const eventUri = event?._uri ?? '';
  const graph = useMemo(
    () => (event ? buildEventJsonGraph(event) : emptyEventsGraph()),
    [event],
  );
  const selectedNode = highlightedPath
    ? graph.nodes.find((node) => node.path === highlightedPath) ?? null
    : null;

  useEffect(() => {
    storedRef.current = new Map();
    cameraRef.current = null;
    setHighlightedPath(null);
  }, [eventUri]);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas || !event) return;
    const api = mountEventsGraph(stage, canvas, {
      graph,
      view: projection,
      highlightedPath: () => highlightRef.current,
      onSelectPath: (path) => {
        setHighlightedPath((prev) => (prev === path ? null : path));
      },
      stored: storedRef.current,
      camera: cameraRef.current,
      onCamera: (next) => {
        cameraRef.current = next;
      },
    });
    apiRef.current = api;
    return () => {
      api.dispose();
      apiRef.current = null;
    };
  }, [graph, projection, event]);

  useEffect(() => {
    apiRef.current?.redraw();
  }, [highlightedPath]);

  if (!event) {
    return (
      <div
        className="flex min-h-0 flex-1 items-center justify-center bg-background text-sm text-muted-foreground"
        data-testid="admin-events-graph-empty"
      >
        Select an event
      </div>
    );
  }

  return (
    <div
      ref={stageRef}
      className="relative min-h-0 flex-1 overflow-hidden bg-background"
    >
      <canvas
        ref={canvasRef}
        data-testid="admin-events-graph"
        className="absolute inset-0 h-full w-full touch-none"
        aria-label="Event JSON and BFO bucket graph"
      />
      {selectedNode ? (
        <div
          className="absolute inset-x-0 bottom-0 max-h-[36%] border-t bg-background/95"
          data-testid="admin-events-graph-inspect"
        >
          <div className="flex items-center gap-2 px-3 py-1.5 text-[11px]">
            <span className="min-w-0 truncate font-mono text-muted-foreground">
              {selectedNode.path}
            </span>
            {onViewJson ? (
              <button
                type="button"
                onClick={onViewJson}
                data-testid="admin-events-graph-view-json"
                className="ml-auto shrink-0 text-muted-foreground hover:text-foreground"
              >
                View JSON
              </button>
            ) : null}
          </div>
          <pre className="max-h-40 overflow-auto px-3 pb-2 font-mono text-[11px] text-foreground">
            {selectedNode.title}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
