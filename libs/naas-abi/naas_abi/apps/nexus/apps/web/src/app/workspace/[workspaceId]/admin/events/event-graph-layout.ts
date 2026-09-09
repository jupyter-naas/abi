/**
 * Seeding and projection for the events graph.
 *
 * Ported from the Personnel Cockpit graph (`domains/personnel/apps/cockpit/
 * web/components/pages/graph/GraphPage.js`): the simulation stays 2D and each
 * cluster gets a fixed z at seed time, so orbiting reveals the grouping as
 * depth without re-running any layout.
 */

import { EVENT_GRAPH_BUCKETS, type BfoBucketType, type EventGraphField } from './bfo-event-projection';
import type { EventGraphModel, ModelNode } from './event-graph-model';
import type { GraphParams } from './event-graph-params';
import type { PhysicsEdge, PhysicsNode } from './event-graph-physics';

export const NODE_RADIUS = 34;
export const PROCESS_RADIUS = 46;
export const CAMERA_DISTANCE = 2400;
export const NODE_LABEL_FONT_SIZE = 11;
export const NODE_LABEL_LINE_HEIGHT = 13;

/** Distance from a process to the first satellite of a bucket. */
const SATELLITE_RADIUS = 255;
/** Extra reach for every other node in the same bucket, so labels miss. */
const RING_STAGGER = 100;
/** Angular gap between nodes sharing a bucket sector. */
const SECTOR_SPREAD = 0.32;
/** Radius of the ring the non-focus processes are seeded onto. */
const PROCESS_RING = 660;
/** Depth assigned per cluster. Orbiting turns this into visible grouping. */
const CLUSTER_DEPTH_STEP = 130;
/** How much every edge bends. Straight stars read flat under rotation. */
const EDGE_ROUNDNESS = 0.09;

export interface LayoutNode extends PhysicsNode {
  bucket: BfoBucketType;
  label: string;
  known: boolean;
  fields: EventGraphField[];
  isProcess: boolean;
  typeLabel: string;
  processIds: string[];
  z: number;
  /** Projected screen position and perspective scale, filled by projectNodes. */
  px: number;
  py: number;
  ds: number;
  depth: number;
}

export interface LayoutEdge extends PhysicsEdge<LayoutNode> {
  label: string;
  roundness: number;
  dashed: boolean;
}

export interface EventLayout {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  focus: LayoutNode | null;
}

function clusterKeyOf(node: ModelNode, params: GraphParams): string | null {
  if (params.clusterBy === 'process') return node.processIds[0] ?? node.id;
  if (params.clusterBy === 'bucket') return node.bucket;
  return null;
}

export function seedEventGraph(model: EventGraphModel, params: GraphParams): EventLayout {
  const processes = model.nodes.filter((node) => node.isProcess);
  const ordered = model.focusId
    ? [
        ...processes.filter((node) => node.id === model.focusId),
        ...processes.filter((node) => node.id !== model.focusId),
      ]
    : processes;

  const processIndex = new Map<string, number>(ordered.map((node, index) => [node.id, index]));
  const processPoint = new Map<string, { x: number; y: number }>();
  ordered.forEach((node, index) => {
    if (index === 0) {
      processPoint.set(node.id, { x: 0, y: 0 });
      return;
    }
    const spokes = Math.max(1, ordered.length - 1);
    const angle = ((index - 1) / spokes) * Math.PI * 2;
    processPoint.set(node.id, {
      x: Math.cos(angle) * PROCESS_RING,
      y: Math.sin(angle) * PROCESS_RING,
    });
  });

  const depthOf = (node: ModelNode): number => {
    if (params.clusterBy === 'bucket') {
      const index = EVENT_GRAPH_BUCKETS.indexOf(node.bucket as (typeof EVENT_GRAPH_BUCKETS)[number]);
      if (index < 0) return 0;
      return (index - (EVENT_GRAPH_BUCKETS.length - 1) / 2) * CLUSTER_DEPTH_STEP;
    }
    if (params.clusterBy === 'process') {
      const index = processIndex.get(node.processIds[0] ?? '') ?? 0;
      return (index - (ordered.length - 1) / 2) * CLUSTER_DEPTH_STEP;
    }
    return 0;
  };

  // Satellites fan out of their owning process; a shared one starts at the
  // centroid of everything that references it.
  const bucketSlot = new Map<string, number>();
  const nodes: LayoutNode[] = model.nodes.map((node) => {
    let x = 0;
    let y = 0;
    if (node.isProcess) {
      const point = processPoint.get(node.id) ?? { x: 0, y: 0 };
      x = point.x;
      y = point.y;
    } else {
      let sumX = 0;
      let sumY = 0;
      let count = 0;
      for (const processId of node.processIds) {
        const point = processPoint.get(processId);
        if (!point) continue;
        sumX += point.x;
        sumY += point.y;
        count += 1;
      }
      const originX = count ? sumX / count : 0;
      const originY = count ? sumY / count : 0;
      const bucketIndex = EVENT_GRAPH_BUCKETS.indexOf(
        node.bucket as (typeof EVENT_GRAPH_BUCKETS)[number],
      );
      const slotKey = `${node.processIds[0]}::${node.bucket}`;
      const slot = bucketSlot.get(slotKey) ?? 0;
      bucketSlot.set(slotKey, slot + 1);
      const sectorAngle =
        -Math.PI / 2 + (Math.max(0, bucketIndex) * Math.PI * 2) / EVENT_GRAPH_BUCKETS.length;
      const angle = sectorAngle + (slot - 1) * SECTOR_SPREAD;
      const radius = SATELLITE_RADIUS + (slot % 2) * RING_STAGGER;
      x = originX + Math.cos(angle) * radius;
      y = originY + Math.sin(angle) * radius;
    }

    const isFocus = node.id === model.focusId;
    return {
      id: node.id,
      bucket: node.bucket,
      label: node.label,
      known: node.known,
      fields: node.fields,
      isProcess: node.isProcess,
      typeLabel: node.typeLabel,
      processIds: node.processIds,
      x,
      y,
      vx: 0,
      vy: 0,
      homeX: x,
      homeY: y,
      // The focus is the reader's anchor: the simulation moves everything else.
      pinned: isFocus,
      physicsEnabled: !isFocus,
      clusterKey: clusterKeyOf(node, params),
      radius: node.isProcess ? PROCESS_RADIUS : NODE_RADIUS,
      z: node.isProcess && isFocus ? 0 : depthOf(node),
      px: x,
      py: y,
      ds: 1,
      depth: 0,
    };
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));

  // Parallel edges between the same pair get spread apart, as the cockpit's
  // annotateEdgeCurves does, so they do not overdraw each other.
  const pairCount = new Map<string, number>();
  const pairSeen = new Map<string, number>();
  for (const edge of model.edges) {
    const key = [edge.fromId, edge.toId].sort().join('|');
    pairCount.set(key, (pairCount.get(key) ?? 0) + 1);
  }

  const edges: LayoutEdge[] = [];
  for (const edge of model.edges) {
    const from = byId.get(edge.fromId);
    const to = byId.get(edge.toId);
    if (!from || !to) continue;
    const key = [edge.fromId, edge.toId].sort().join('|');
    const total = pairCount.get(key) ?? 1;
    const seen = pairSeen.get(key) ?? 0;
    pairSeen.set(key, seen + 1);
    const spread = total > 1 ? (seen - (total - 1) / 2) * 0.16 : 0;
    edges.push({
      from,
      to,
      label: edge.label,
      roundness: EDGE_ROUNDNESS + spread,
      dashed: edge.dashed,
    });
  }

  return { nodes, edges, focus: model.focusId ? (byId.get(model.focusId) ?? null) : null };
}

export function nodeRadiusOf(node: LayoutNode): number {
  return node.radius;
}

/**
 * Rotate every node about the vertical then horizontal axis and project.
 * In 2D the projection is the identity: there is no depth to reveal.
 */
export function projectNodes(
  nodes: LayoutNode[],
  yaw: number,
  pitch: number,
  view: '2d' | '3d' = '3d',
): void {
  if (view !== '3d') {
    for (const node of nodes) {
      node.px = node.x;
      node.py = node.y;
      node.ds = 1;
      node.depth = 0;
    }
    return;
  }
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  for (const node of nodes) {
    const x1 = node.x * cosYaw + node.z * sinYaw;
    const z1 = -node.x * sinYaw + node.z * cosYaw;
    const y1 = node.y * cosPitch - z1 * sinPitch;
    const z2 = node.y * sinPitch + z1 * cosPitch;
    // Clamped so a node level with the camera cannot blow the scale up.
    const k = CAMERA_DISTANCE / Math.max(400, CAMERA_DISTANCE + z2);
    node.px = x1 * k;
    node.py = y1 * k;
    node.ds = k;
    node.depth = z2;
  }
}

/**
 * Fade nodes with distance so the foreground reads as the foreground. Near
 * nodes stay fully opaque; far ones recede rather than competing.
 */
export function depthAlpha(node: LayoutNode, view: '2d' | '3d' = '3d'): number {
  if (view !== '3d') return 1;
  return Math.min(1, Math.max(0.42, (node.ds - 0.6) / 0.4));
}

export function pointOnQuadratic(
  t: number,
  start: { x: number; y: number },
  control: { x: number; y: number },
  end: { x: number; y: number },
): { x: number; y: number } {
  const u = 1 - t;
  return {
    x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
    y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
  };
}

export function tangentOnQuadratic(
  t: number,
  start: { x: number; y: number },
  control: { x: number; y: number },
  end: { x: number; y: number },
): { x: number; y: number } {
  const u = 1 - t;
  return {
    x: 2 * u * (control.x - start.x) + 2 * t * (end.x - control.x),
    y: 2 * u * (control.y - start.y) + 2 * t * (end.y - control.y),
  };
}

function boundaryPoint(from: LayoutNode, to: LayoutNode, radius: number) {
  const dx = to.px - from.px;
  const dy = to.py - from.py;
  const distance = Math.hypot(dx, dy) || 1;
  return { x: from.px + (dx / distance) * radius, y: from.py + (dy / distance) * radius };
}

export function edgeGeometry(edge: LayoutEdge) {
  const start = boundaryPoint(edge.from, edge.to, nodeRadiusOf(edge.from) * edge.from.ds + 4);
  const end = boundaryPoint(edge.to, edge.from, nodeRadiusOf(edge.to) * edge.to.ds + 4);
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy) || 1;
  const offset = edge.roundness * length;
  return {
    start,
    end,
    control: { x: midX + (-dy / length) * offset, y: midY + (dx / length) * offset },
  };
}

function truncate(line: string, maxChars: number, forceEllipsis = false): string {
  if (!forceEllipsis && line.length <= maxChars) return line;
  if (maxChars <= 1) return '…';
  if (forceEllipsis && line.length < maxChars) return `${line}…`;
  return `${line.slice(0, maxChars - 1)}…`;
}

/** Wrap a node label to fit inside its circle, breaking long tokens hard. */
export function wrapNodeLabel(label: string, maxCharsPerLine: number, maxLines: number): string[] {
  const normalized = (label || '').trim().replace(/\s+/g, ' ');
  if (!normalized) return [''];
  const tokens = normalized.split(' ');
  const lines: string[] = [];
  let current = '';
  let index = 0;
  let dropped = false;

  const flush = () => {
    if (!current) return;
    lines.push(current);
    current = '';
  };

  while (index < tokens.length && lines.length < maxLines) {
    const token = tokens[index];
    const candidate = current ? `${current} ${token}` : token;
    if (candidate.length <= maxCharsPerLine) {
      current = candidate;
      index += 1;
      continue;
    }
    flush();
    if (lines.length >= maxLines) break;
    if (token.length <= maxCharsPerLine) {
      current = token;
      index += 1;
      continue;
    }
    let rest = token;
    while (rest.length > maxCharsPerLine && lines.length < maxLines) {
      lines.push(rest.slice(0, maxCharsPerLine));
      rest = rest.slice(maxCharsPerLine);
    }
    if (rest.length > maxCharsPerLine) dropped = true;
    else current = rest;
    index += 1;
  }
  if (lines.length < maxLines && current) {
    lines.push(current);
    current = '';
  }

  // Anything the line budget could not hold has to show as an ellipsis, or the
  // label reads as complete when it is not.
  const overflowed = dropped || index < tokens.length || current.length > 0;
  const result = lines.slice(0, maxLines);
  if (overflowed && result.length > 0) {
    result[result.length - 1] = truncate(result[result.length - 1], maxCharsPerLine, true);
  }
  return result.length ? result : [truncate(normalized, maxCharsPerLine)];
}

export function nodeLabelLines(node: LayoutNode): string[] {
  const radius = nodeRadiusOf(node);
  const maxCharsPerLine = Math.max(4, Math.floor((radius * 1.75) / (NODE_LABEL_FONT_SIZE * 0.52)));
  const maxLines = Math.max(1, Math.floor((radius * 1.55) / NODE_LABEL_LINE_HEIGHT));
  return wrapNodeLabel(node.label, maxCharsPerLine, maxLines);
}
