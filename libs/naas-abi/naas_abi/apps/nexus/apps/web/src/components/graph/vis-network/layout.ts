/**
 * Pure layout / rendering helpers for the vis-network canvas.
 *
 * These functions are deliberately framework-free — no React, no DOM, no
 * vis-network types — so they can be unit tested in isolation and tree-shaken
 * if not used.
 */

import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';
import {
  resolveBucket,
  wrapLabelTwoLines as sharedWrapLabelTwoLines,
  type BfoBucket,
} from '@/lib/bfo';

export const EDGE_COLORS: Record<string, string> = {
  // 'participates in': '#22c55e',
  // 'has participant': '#22c55e',
  // 'occurs in': '#f97316',
  // 'located in': '#f97316',
  // 'bearer of': '#ec4899',
  // 'inheres in': '#ec4899',
  // 'has role': '#eab308',
  // 'has disposition': '#f59e0b',
  // 'realizes': '#a855f7',
  // 'precedes': '#8b5cf6',
  // 'preceded by': '#8b5cf6',
  // 'concretizes': '#06b6d4',
  // 'is carrier of': '#06b6d4',
  // 'generically depends on': '#06b6d4',
};

export const DEFAULT_NODE_BOX_WIDTH = 128;
export const DEFAULT_NODE_BOX_HEIGHT = 88;

const LR_LEVEL_GAP = 260; // px between depth levels  (main axis = x)
const LR_NODE_SLOT = 110; // px per leaf slot in cross-axis (y)
const TD_LEVEL_GAP = 180; // px between depth levels  (main axis = y)
const TD_NODE_SLOT = 168; // px per leaf slot in cross-axis (x)

export const wrapLabelTwoLines = sharedWrapLabelTwoLines;

/**
 * Sunflower-spiral seeding for force-directed layouts.
 *
 * Distributes points across a 2D plane using golden-angle sampling so physics
 * starts from a spread-out state instead of every node piling up at the origin
 * (which produces an exploding hairball on first tick).
 */
export function computeSpreadPositions(
  nodeIds: string[],
  spacing = 300,
): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>();
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  nodeIds.forEach((id, i) => {
    const r = spacing * Math.sqrt(i);
    const theta = i * goldenAngle;
    result.set(id, { x: r * Math.cos(theta), y: r * Math.sin(theta) });
  });
  return result;
}

/**
 * Subtree-based hierarchical layout (Reingold-Tilford style).
 *
 * Algorithm:
 *  1. Build parent→children tree from `is_a` edges (source=child, target=parent).
 *  2. Sort each node's children by BFO bucket so same-bucket siblings are adjacent.
 *  3. DFS: leaves consume one slot in the cross-axis; internal nodes are centred
 *     over their children's range.  A small extra gap is injected when the bucket
 *     changes within a sibling list, visually packing same-bucket nodes together.
 *  4. Centre the whole layout at cross-axis = 0.
 *
 * Collision-free by construction: every subtree occupies a contiguous, non-
 * overlapping range of the cross-axis cursor.
 */
export function computeHierarchicalPositions(
  nodes: GraphNode[],
  edges: GraphEdge[],
  direction: 'LR' | 'TD',
): Map<string, { x: number; y: number }> {
  if (nodes.length === 0) return new Map();

  const nodesById = new Map(nodes.map((n) => [n.id, n]));
  const nodeIds = new Set(nodes.map((n) => n.id));
  const isaEdges = edges.filter((e) => e.properties?.relation_kind === 'is_a');

  // ── 1. Build tree ──────────────────────────────────────────────────────────
  const childrenOf = new Map<string, string[]>();
  const parentOf = new Map<string, string>();

  for (const edge of isaEdges) {
    const child = edge.source,
      parent = edge.target;
    if (!nodeIds.has(child) || !nodeIds.has(parent)) continue;
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent)!.push(child);
    if (!parentOf.has(child)) parentOf.set(child, parent);
  }

  // ── 2. Bucket key per node (pre-computed for sorting) ─────────────────────
  const bucketOf = new Map<string, BfoBucket>();
  for (const node of nodes) bucketOf.set(node.id, resolveBucket(node, nodesById));

  for (const [, children] of childrenOf) {
    children.sort((a, b) => {
      const ba = bucketOf.get(a) ?? 'Unknown';
      const bb = bucketOf.get(b) ?? 'Unknown';
      if (ba !== bb) return ba.localeCompare(bb);
      return (nodesById.get(a)?.label ?? a).localeCompare(nodesById.get(b)?.label ?? b);
    });
  }

  // ── 3. Roots — prefer BFO entity (BFO_0000001) first ─────────────────────
  const roots = nodes
    .map((n) => n.id)
    .filter((id) => !parentOf.has(id))
    .sort((a, b) => {
      if (a.includes('BFO_0000001')) return -1;
      if (b.includes('BFO_0000001')) return 1;
      return (nodesById.get(a)?.label ?? a).localeCompare(nodesById.get(b)?.label ?? b);
    });

  // ── 4. DFS placement ───────────────────────────────────────────────────────
  const SLOT = direction === 'LR' ? LR_NODE_SLOT : TD_NODE_SLOT;
  const LEVEL = direction === 'LR' ? LR_LEVEL_GAP : TD_LEVEL_GAP;
  const BUCKET_XTRA = Math.round(SLOT * 0.55);

  const positions = new Map<string, { x: number; y: number }>();
  let cursor = 0;

  const setPos = (id: string, depth: number, cross: number) =>
    positions.set(
      id,
      direction === 'LR'
        ? { x: depth * LEVEL, y: cross }
        : { x: cross, y: depth * LEVEL },
    );

  const place = (id: string, depth: number): number => {
    const children = childrenOf.get(id) ?? [];

    if (children.length === 0) {
      const pos = cursor + SLOT / 2;
      cursor += SLOT;
      setPos(id, depth, pos);
      return pos;
    }

    let prevBucket = '';
    const centers: number[] = [];

    for (const child of children) {
      const b = bucketOf.get(child) ?? 'Unknown';
      if (prevBucket && prevBucket !== b) cursor += BUCKET_XTRA;
      prevBucket = b;
      centers.push(place(child, depth + 1));
    }

    const mid = (centers[0] + centers[centers.length - 1]) / 2;
    setPos(id, depth, mid);
    return mid;
  };

  for (let i = 0; i < roots.length; i++) {
    if (i > 0) cursor += SLOT;
    place(roots[i], 0);
  }

  for (const node of nodes) {
    if (!positions.has(node.id)) {
      cursor += SLOT;
      setPos(node.id, 0, cursor + SLOT / 2);
      cursor += SLOT;
    }
  }

  // ── 5. Centre layout at cross-axis 0 ──────────────────────────────────────
  // Manual loop instead of Math.min/max(...spread) — the spread call stack blows
  // up at ~100k args, which a fully-loaded BFO+CCO ontology can exceed.
  let lo = Infinity,
    hi = -Infinity;
  for (const p of positions.values()) {
    const v = direction === 'LR' ? p.y : p.x;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  const mid = (lo + hi) / 2;
  for (const [id, pos] of positions) {
    positions.set(
      id,
      direction === 'LR'
        ? { x: pos.x, y: pos.y - mid }
        : { x: pos.x - mid, y: pos.y },
    );
  }

  return positions;
}

function escapeXml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

/**
 * Render a node's "card" to an SVG data URI used as a vis-network image shape.
 * Embedding the logo as base64 inside the SVG keeps each node a single asset
 * (no separate image fetch per node, no CORS / cache issues at paint time).
 */
export function nodeCardSvgDataUri(args: {
  width: number;
  height: number;
  background: string;
  border: string;
  label: string;
  logoDataUri?: string;
}): string {
  const { width, height, background, border, label, logoDataUri } = args;
  const [line1, line2] = label.split('\n');

  const pad = 10;
  const logoSize = 32;
  const hasLogo = Boolean(logoDataUri);
  const logoX = Math.round((width - logoSize) / 2);
  const logoY = pad;

  const textStartY = hasLogo ? logoY + logoSize + 20 : Math.round(height / 2) + 6;
  const lineHeight = 16;
  const textY1 = line2 ? textStartY - 6 : textStartY;
  const textY2 = textY1 + lineHeight;

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect x="1" y="1" width="${width - 2}" height="${height - 2}" rx="0" ry="0" fill="${background}" stroke="${border}" stroke-width="2"/>
  ${
    hasLogo
      ? `<image href="${escapeXml(logoDataUri!)}" x="${logoX}" y="${logoY}" width="${logoSize}" height="${logoSize}" preserveAspectRatio="xMidYMid meet" />`
      : ''
  }
  <text x="${Math.round(width / 2)}" y="${textY1}" text-anchor="middle"
        font-family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
        font-size="13" font-weight="600" fill="#ffffff">
    <tspan x="${Math.round(width / 2)}" dy="0">${escapeXml(line1 ?? '')}</tspan>
    ${line2 ? `<tspan x="${Math.round(width / 2)}" dy="${lineHeight}">${escapeXml(line2)}</tspan>` : ''}
  </text>
</svg>`;

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
