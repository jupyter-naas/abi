'use client';

import { useEffect, useLayoutEffect, useRef, useCallback, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Network, DataSet, type Options, type Node, type Edge } from 'vis-network/standalone';
import 'vis-network/styles/vis-network.css';
import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

// BFO 7 Buckets color scheme (simplified)
const BFO_COLORS = {
  'Material Entity': { background: '#3b82f6', border: '#2563eb', highlight: '#60a5fa' },
  'Process': { background: '#22c55e', border: '#16a34a', highlight: '#4ade80' },
  'Temporal Region': { background: '#a855f7', border: '#9333ea', highlight: '#c084fc' },
  'Site': { background: '#f97316', border: '#ea580c', highlight: '#fb923c' },
  'Quality': { background: '#ec4899', border: '#db2777', highlight: '#f472b6' },
  'Realizable': { background: '#eab308', border: '#ca8a04', highlight: '#facc15' },
  'GDC': { background: '#06b6d4', border: '#0891b2', highlight: '#22d3ee' },
  'Entity': { background: '#6b7280', border: '#4b5563', highlight: '#9ca3af' },
  'Unknown': { background: '#9ca3af', border: '#6b7280', highlight: '#d1d5db' },
};

// BFO URI → color bucket (full URI and short ID forms)
const BFO_URI_TO_BUCKET: Record<string, keyof typeof BFO_COLORS> = {
  'http://purl.obolibrary.org/obo/BFO_0000001': 'Entity',
  'http://purl.obolibrary.org/obo/BFO_0000040': 'Material Entity',
  'http://purl.obolibrary.org/obo/BFO_0000015': 'Process',
  'http://purl.obolibrary.org/obo/BFO_0000008': 'Temporal Region',
  'http://purl.obolibrary.org/obo/BFO_0000029': 'Site',
  'http://purl.obolibrary.org/obo/BFO_0000031': 'GDC',
  'http://purl.obolibrary.org/obo/BFO_0000019': 'Quality',
  'http://purl.obolibrary.org/obo/BFO_0000017': 'Realizable',
  'BFO_0000001': 'Entity',
  'BFO_0000040': 'Material Entity',
  'BFO_0000015': 'Process',
  'BFO_0000008': 'Temporal Region',
  'BFO_0000029': 'Site',
  'BFO_0000031': 'GDC',
  'BFO_0000019': 'Quality',
  'BFO_0000017': 'Realizable',
};

// Lowercase label → color bucket (covers common BFO/CCO labels)
const LABEL_TO_BUCKET: Record<string, keyof typeof BFO_COLORS> = {
  'entity': 'Entity',
  'process': 'Process',
  'process boundary': 'Process',
  'temporal region': 'Temporal Region',
  'temporal interval': 'Temporal Region',
  'zero-dimensional temporal region': 'Temporal Region',
  'one-dimensional temporal region': 'Temporal Region',
  'material entity': 'Material Entity',
  'object': 'Material Entity',
  'object aggregate': 'Material Entity',
  'fiat object part': 'Material Entity',
  'site': 'Site',
  'immaterial entity': 'Site',
  'spatial region': 'Site',
  'continuant fiat boundary': 'Site',
  'generically dependent continuant': 'GDC',
  'quality': 'Quality',
  'specifically dependent continuant': 'Quality',
  'role': 'Realizable',
  'disposition': 'Realizable',
  'realizable entity': 'Realizable',
};

function resolveBFOColor(node: GraphNode, nodesById?: Map<string, GraphNode>, visited: Set<string> = new Set()) {
  // bfo_parent_iri: authoritative BFO ancestor from backend SPARQL — check first
  const bfoParentIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoParentIri && bfoParentIri in BFO_URI_TO_BUCKET) return BFO_COLORS[BFO_URI_TO_BUCKET[bfoParentIri]];

  // Direct BFO_COLORS key match (e.g. KG nodes already tagged with bucket name)
  if (node.type in BFO_COLORS) return BFO_COLORS[node.type as keyof typeof BFO_COLORS];

  // Lowercase label match
  const lowerType = node.type?.toLowerCase?.() ?? '';
  if (lowerType in LABEL_TO_BUCKET) return BFO_COLORS[LABEL_TO_BUCKET[lowerType]];

  // Full/short BFO URI in node.type (KG nodes where type IS the BFO URI)
  if (node.type in BFO_URI_TO_BUCKET) return BFO_COLORS[BFO_URI_TO_BUCKET[node.type]];

  // parent_iri: direct parent — check BFO first, then walk the loaded graph recursively
  const parentIri = node.properties?.parent_iri as string | undefined;
  if (parentIri && parentIri in BFO_URI_TO_BUCKET) return BFO_COLORS[BFO_URI_TO_BUCKET[parentIri]];

  if (nodesById && parentIri && !visited.has(node.id)) {
    visited.add(node.id);
    const parentNode = nodesById.get(parentIri);
    if (parentNode) return resolveBFOColor(parentNode, nodesById, visited);
  }

  return null;
}

function computeSpreadPositions(nodeIds: string[], spacing = 300): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>();
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  nodeIds.forEach((id, i) => {
    const r = spacing * Math.sqrt(i);
    const theta = i * goldenAngle;
    result.set(id, { x: r * Math.cos(theta), y: r * Math.sin(theta) });
  });
  return result;
}

const EDGE_COLORS: Record<string, string> = {
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

const DEFAULT_NODE_BOX_WIDTH = 128;
const DEFAULT_NODE_BOX_HEIGHT = 88;
const DEFAULT_MAX_CHARS_PER_LINE = 14;

// Spacing constants for hierarchical layout
const LR_LEVEL_GAP   = 260; // px between depth levels  (main axis = x)
const LR_NODE_SLOT   = 110; // px per leaf slot in cross-axis (y)
const TD_LEVEL_GAP   = 180; // px between depth levels  (main axis = y)
const TD_NODE_SLOT   = 168; // px per leaf slot in cross-axis (x)

// Bucket grid layout constants (flat / no-edge case)
const GRID_BUCKET_ORDER = [
  'Material Entity', 'Process', 'Quality', 'Realizable',
  'Temporal Region', 'Site', 'GDC', 'Unknown',
];
const GRID_ZONE_COLS    = 3;    // bucket zones per row
const GRID_ZONE_W       = 1400; // px between bucket zone centres (x)
const GRID_ZONE_H       = 900;  // px between bucket zone centres (y)
const GRID_NODE_W       = 240;  // horizontal node spacing within a zone
const GRID_NODE_H       = 160;  // vertical node spacing within a zone
const GRID_NODES_PER_ROW = 5;   // nodes per row inside a zone

/**
 * 2-D bucket grid layout used when no is_a edges exist.
 * Zones are arranged in a GRID_ZONE_COLS-column grid; nodes within each zone
 * are arranged in rows of GRID_NODES_PER_ROW, sorted alphabetically.
 */
function computeBucketGridPositions(
  nodes: GraphNode[],
  nodesById: Map<string, GraphNode>,
): Map<string, { x: number; y: number }> {
  const byBucket = new Map<string, string[]>();
  for (const node of nodes) {
    const bucket = resolveNodeBucketKey(node, nodesById);
    const list = byBucket.get(bucket) ?? [];
    list.push(node.id);
    byBucket.set(bucket, list);
  }

  for (const [, ids] of byBucket) {
    ids.sort((a, b) =>
      (nodesById.get(a)?.label ?? a).localeCompare(nodesById.get(b)?.label ?? b)
    );
  }

  const activeBuckets = [
    ...GRID_BUCKET_ORDER.filter((b) => byBucket.has(b)),
    ...Array.from(byBucket.keys()).filter((b) => !GRID_BUCKET_ORDER.includes(b)),
  ];

  const positions = new Map<string, { x: number; y: number }>();

  activeBuckets.forEach((bucket, zoneIdx) => {
    const ids = byBucket.get(bucket) ?? [];
    const zoneCol = zoneIdx % GRID_ZONE_COLS;
    const zoneRow = Math.floor(zoneIdx / GRID_ZONE_COLS);
    const zoneOriginX = zoneCol * GRID_ZONE_W;
    const zoneOriginY = zoneRow * GRID_ZONE_H;
    const cols = GRID_NODES_PER_ROW;
    const usedW = (Math.min(ids.length, cols) - 1) * GRID_NODE_W;
    const usedH = (Math.ceil(ids.length / cols) - 1) * GRID_NODE_H;

    ids.forEach((id, i) => {
      positions.set(id, {
        x: zoneOriginX - usedW / 2 + (i % cols) * GRID_NODE_W,
        y: zoneOriginY - usedH / 2 + Math.floor(i / cols) * GRID_NODE_H,
      });
    });
  });

  if (positions.size > 0) {
    const xs = Array.from(positions.values()).map((p) => p.x);
    const ys = Array.from(positions.values()).map((p) => p.y);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    for (const [id, pos] of positions) {
      positions.set(id, { x: pos.x - cx, y: pos.y - cy });
    }
  }

  return positions;
}

// Resolve a stable bucket key for a node (used to sort / group siblings)
function resolveNodeBucketKey(
  node: GraphNode,
  nodesById: Map<string, GraphNode>,
  visited = new Set<string>(),
): string {
  const bfoIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoIri && bfoIri in BFO_URI_TO_BUCKET) return BFO_URI_TO_BUCKET[bfoIri];
  if (node.type in BFO_COLORS) return node.type;
  const lower = node.type?.toLowerCase?.() ?? '';
  if (lower in LABEL_TO_BUCKET) return LABEL_TO_BUCKET[lower];
  if (node.type in BFO_URI_TO_BUCKET) return BFO_URI_TO_BUCKET[node.type];
  const parentIri = node.properties?.parent_iri as string | undefined;
  if (parentIri && parentIri in BFO_URI_TO_BUCKET) return BFO_URI_TO_BUCKET[parentIri];
  if (parentIri && !visited.has(node.id)) {
    visited.add(node.id);
    const parent = nodesById.get(parentIri);
    if (parent) return resolveNodeBucketKey(parent, nodesById, visited);
  }
  return 'Unknown';
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
function computeHierarchicalPositions(
  nodes: GraphNode[],
  edges: GraphEdge[],
  direction: 'LR' | 'TD',
): Map<string, { x: number; y: number }> {
  if (nodes.length === 0) return new Map();

  const nodesById  = new Map(nodes.map((n) => [n.id, n]));
  const nodeIds    = new Set(nodes.map((n) => n.id));
  const isaEdges   = edges.filter((e) => e.properties?.relation_kind === 'is_a');

  // Flat case: no is_a edges → use the 2-D bucket grid instead of a 1-D tree row.
  if (isaEdges.length === 0) {
    return computeBucketGridPositions(nodes, nodesById);
  }

  // ── 1. Build tree ──────────────────────────────────────────────────────────
  const childrenOf = new Map<string, string[]>();
  const parentOf   = new Map<string, string>();

  for (const edge of isaEdges) {
    const child = edge.source, parent = edge.target;
    if (!nodeIds.has(child) || !nodeIds.has(parent)) continue;
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent)!.push(child);
    if (!parentOf.has(child)) parentOf.set(child, parent);
  }

  // ── 2. Bucket key per node (pre-computed for sorting) ─────────────────────
  const bucketOf = new Map<string, string>();
  for (const node of nodes) bucketOf.set(node.id, resolveNodeBucketKey(node, nodesById));

  // Sort children: group by bucket, then alphabetically by label within bucket
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
  const SLOT        = direction === 'LR' ? LR_NODE_SLOT  : TD_NODE_SLOT;
  const LEVEL       = direction === 'LR' ? LR_LEVEL_GAP  : TD_LEVEL_GAP;
  const BUCKET_XTRA = Math.round(SLOT * 0.55); // extra gap between bucket groups

  const positions = new Map<string, { x: number; y: number }>();
  let cursor = 0; // running cross-axis cursor (y for LR, x for TD)

  const setPos = (id: string, depth: number, cross: number) =>
    positions.set(id, direction === 'LR'
      ? { x: depth * LEVEL, y: cross }
      : { x: cross,         y: depth * LEVEL });

  const place = (id: string, depth: number): number => {
    const children = childrenOf.get(id) ?? [];

    if (children.length === 0) {
      // Leaf: occupy one slot
      const pos = cursor + SLOT / 2;
      cursor += SLOT;
      setPos(id, depth, pos);
      return pos;
    }

    // Internal node: place children left-to-right / top-to-bottom,
    // injecting extra gap when the bucket changes.
    let prevBucket = '';
    const centers: number[] = [];

    for (const child of children) {
      const b = bucketOf.get(child) ?? 'Unknown';
      if (prevBucket && prevBucket !== b) cursor += BUCKET_XTRA;
      prevBucket = b;
      centers.push(place(child, depth + 1));
    }

    // Centre the parent over its children's span
    const mid = (centers[0] + centers[centers.length - 1]) / 2;
    setPos(id, depth, mid);
    return mid;
  };

  for (let i = 0; i < roots.length; i++) {
    if (i > 0) cursor += SLOT; // gap between independent root subtrees
    place(roots[i], 0);
  }

  // Nodes unreachable from any root (shouldn't occur, but guard anyway)
  for (const node of nodes) {
    if (!positions.has(node.id)) {
      cursor += SLOT;
      setPos(node.id, 0, cursor + SLOT / 2);
      cursor += SLOT;
    }
  }

  // ── 5. Centre layout at cross-axis 0 ──────────────────────────────────────
  const crossVals = Array.from(positions.values()).map((p) => direction === 'LR' ? p.y : p.x);
  const mid = (Math.min(...crossVals) + Math.max(...crossVals)) / 2;
  for (const [id, pos] of positions) {
    positions.set(id, direction === 'LR'
      ? { x: pos.x, y: pos.y - mid }
      : { x: pos.x - mid, y: pos.y });
  }

  return positions;
}

function wrapLabelTwoLines(label: string, maxCharsPerLine = DEFAULT_MAX_CHARS_PER_LINE): string {
  const normalized = (label ?? '').trim().replace(/\s+/g, ' ');
  if (!normalized) return '';
  if (normalized.length <= maxCharsPerLine) return normalized;

  const words = normalized.split(' ');
  const lines: string[] = [];
  let current = '';

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxCharsPerLine) {
      current = candidate;
      continue;
    }

    if (current) lines.push(current);
    current = word;
    if (lines.length === 2) break;
  }
  if (lines.length < 2 && current) lines.push(current);

  const line1 = lines[0] ?? '';
  let line2 = lines[1] ?? '';

  if (!line2 && words.length > 1) {
    // Hard split if we couldn't build a second line from words.
    line2 = normalized.slice(line1.length).trim();
  }

  if (line2.length > maxCharsPerLine) {
    line2 = `${line2.slice(0, Math.max(0, maxCharsPerLine - 1)).trimEnd()}…`;
  }

  return line2 ? `${line1}\n${line2}` : line1;
}

function escapeXml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function nodeCardSvgDataUri(args: {
  width: number;
  height: number;
  background: string;
  border: string;
  label: string;
  logoDataUri?: string;
}): string {
  const { width, height, background, border, label, logoDataUri } = args;
  const [line1, line2] = label.split('\n');

  // Layout
  const pad = 10;
  const logoSize = 32;
  const hasLogo = Boolean(logoDataUri);
  const logoX = Math.round((width - logoSize) / 2);
  const logoY = pad;

  // Text below the logo (or centered if no logo)
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

interface VisNetworkProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edgeId: string | null) => void;
  stabilizeKey?: number;
  layoutDirection?: 'LR' | 'TD';
  /**
   * Stable id for the current graph “mode” (e.g. ontology relation toggles).
   * When this changes before the canvas updates, the previous zoom/pan is stored
   * and reapplied when returning to that mode.
   */
  viewStateKey?: string;
  /**
   * When true (and not in hierarchical layout), physics stays continuously
   * enabled instead of freezing after stabilization. Set by the parent when
   * filters that benefit from a live force-directed layout are active
   * (e.g. Restrictions / Object Properties).
   */
  physicsEnabled?: boolean;
}

export function VisNetwork({
  nodes,
  edges,
  selectedNodeId,
  onNodeSelect,
  onEdgeSelect,
  stabilizeKey,
  layoutDirection,
  viewStateKey,
  physicsEnabled = false,
}: VisNetworkProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const nodesDataRef = useRef<DataSet<Node>>(new DataSet());
  const edgesDataRef = useRef<DataSet<Edge>>(new DataSet());
  const onNodeSelectRef = useRef(onNodeSelect);
  const onEdgeSelectRef = useRef(onEdgeSelect);
  const prevSelectedNodeIdRef = useRef<string | null>(null);
  const [logoDataByUrl, setLogoDataByUrl] = useState<Record<string, string>>({});

  const savedFilterViewsRef = useRef(
    new Map<string, { scale: number; position: { x: number; y: number } }>()
  );
  const prevFilterViewKeyRef = useRef<string | undefined>(undefined);
  const currentFilterViewKeyRef = useRef<string>('__default');
  /** True after filter key changed: next graph update should restore or fit for the new key. */
  const pendingFilterViewportApplyRef = useRef(false);

  /** Restore saved zoom/pan for `currentFilterViewKeyRef`, or fit if unseen. */
  const applySavedViewportOrFit = useCallback((opts?: { fitDurationMs?: number }) => {
    const net = networkRef.current;
    if (!net || nodesDataRef.current.length === 0) return;
    const key = currentFilterViewKeyRef.current;
    const saved = savedFilterViewsRef.current.get(key);
    const fitDurationMs = opts?.fitDurationMs ?? 300;
    if (saved) {
      try {
        net.moveTo({
          scale: saved.scale,
          position: saved.position,
          animation: { duration: 0, easingFunction: 'linear' },
        });
        return;
      } catch {
        // fallthrough to fit
      }
    }
    net.fit({ animation: { duration: fitDurationMs, easingFunction: 'easeInOutQuad' } });
  }, []);

  useLayoutEffect(() => {
    const key = viewStateKey ?? '__default';
    const net = networkRef.current;
    const prevKey = prevFilterViewKeyRef.current;
    if (net && prevKey !== undefined && prevKey !== key) {
      try {
        savedFilterViewsRef.current.set(prevKey, {
          scale: net.getScale(),
          position: net.getViewPosition(),
        });
      } catch {
        // Ignore read errors during teardown / empty graph.
      }
      pendingFilterViewportApplyRef.current = true;
    }
    prevFilterViewKeyRef.current = key;
    currentFilterViewKeyRef.current = key;
  }, [viewStateKey]);

  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
    onEdgeSelectRef.current = onEdgeSelect;
  }, [onNodeSelect, onEdgeSelect]);

  const nodesByIri = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const hierarchicalPositions = useMemo(
    () => (layoutDirection ? computeHierarchicalPositions(nodes, edges, layoutDirection) : null),
    [layoutDirection, nodes, edges],
  );

  const getNodeLogoUrl = useCallback((node: GraphNode): string | undefined => {
    const properties = node.properties ?? {};
    const candidates: unknown[] = [
      properties.logo_url,
      properties.logoUrl,
      properties['logo url'],
      properties['http://ontology.naas.ai/nexus/logo_url'],
      properties['https://ontology.naas.ai/nexus/logo_url'],
      (node as GraphNode & { logo_url?: unknown }).logo_url,
      (node as GraphNode & { logoUrl?: unknown }).logoUrl,
    ];

    const found = candidates.find((value) => {
      if (typeof value !== 'string') return false;
      const normalized = value.trim();
      if (!normalized) return false;
      if (normalized.toLowerCase() === 'unknown') return false;
      return true;
    });
    return typeof found === 'string' ? found.trim() : undefined;
  }, []);

  // Fetch and cache logo images as data URIs so they can be embedded in SVG.
  useEffect(() => {
    const urls = Array.from(
      new Set(
        nodes
          .map((n) => getNodeLogoUrl(n))
          .filter((u): u is string => Boolean(u))
      )
    );

    const missing = urls.filter((u) => !logoDataByUrl[u]);
    if (missing.length === 0) return;

    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      await Promise.all(
        missing.map(async (url) => {
          try {
            const res = await fetch(`/api/image-data?url=${encodeURIComponent(url)}`);
            if (!res.ok) return;
            const json = (await res.json()) as { dataUri?: string };
            if (json.dataUri) updates[url] = json.dataUri;
          } catch {
            // Ignore broken/missing logos; nodes will render without them.
          }
        })
      );
      if (cancelled) return;
      if (Object.keys(updates).length > 0) {
        setLogoDataByUrl((prev) => ({ ...prev, ...updates }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [getNodeLogoUrl, logoDataByUrl, nodes]);

  const toVisNode = useCallback((node: GraphNode): Node => {
    const colors = resolveBFOColor(node, nodesByIri) ?? BFO_COLORS['Entity'];
    const logoUrl = getNodeLogoUrl(node);
    const wrapped = wrapLabelTwoLines(node.label);
    const logoDataUri = logoUrl ? logoDataByUrl[logoUrl] : undefined;
    const image = nodeCardSvgDataUri({
      width: DEFAULT_NODE_BOX_WIDTH,
      height: DEFAULT_NODE_BOX_HEIGHT,
      background: colors.background,
      border: colors.border,
      label: wrapped,
      logoDataUri,
    });

    const hierPos = hierarchicalPositions?.get(node.id);
    return {
      id: node.id,
      label: '',
      title: `${node.type}\n${node.label}`,
      shape: 'image',
      image,
      shapeProperties: { useImageSize: true, interpolation: true, coordinateOrigin: 'center' },
      x: hierPos?.x ?? node.x,
      y: hierPos?.y ?? node.y,
    };
  }, [getNodeLogoUrl, logoDataByUrl, nodesByIri, hierarchicalPositions]);

  const toVisEdge = useCallback((edge: GraphEdge): Edge => {
    const isHierarchical = edge.properties?.relation_kind === 'is_a';
    const color = isHierarchical ? '#000000' : (EDGE_COLORS[edge.type] || '#94a3b8');
    return {
      id: edge.id,
      from: edge.source,
      to: edge.target,
      label: isHierarchical ? undefined : (edge.label || edge.type),
      title: edge.type,
      color: { color, highlight: color, hover: color },
      arrows: { to: { enabled: true, scaleFactor: 0.8 } },
      font: { size: 9, color: isHierarchical ? '#000000' : '#64748b', face: 'Inter, sans-serif', align: 'middle', background: '#ffffff' },
      smooth: { enabled: false, type: 'continuous', roundness: 0 },
      width: edge.weight || (isHierarchical ? 1 : 2),
      dashes: isHierarchical,
    };
  }, []);

  // Network options - simple config, let vis-network handle zoom
  const options: Options = {
    autoResize: true,
    height: '100%',
    width: '100%',
    nodes: {
      shape: 'image',
      borderWidth: 2,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.2)', size: 5, x: 2, y: 2 },
    },
    edges: {
      width: 2,
      selectionWidth: 3,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.1)', size: 3, x: 1, y: 1 },
    },
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -120,
        centralGravity: 0.005,
        springLength: 250,
        springConstant: 0.04,
        damping: 0.5,
        avoidOverlap: 1,
      },
      stabilization: { enabled: true, iterations: 200, updateInterval: 25 },
      minVelocity: 0.75,
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      multiselect: true,
      navigationButtons: true,  // Enable built-in navigation buttons
      keyboard: { enabled: true, bindToWindow: false },
      zoomView: true,
      dragView: true,
    },
    layout: {
      improvedLayout: false,
    },
  };

  // Initialize network once
  useEffect(() => {
    if (!containerRef.current) return;

    networkRef.current = new Network(
      containerRef.current,
      { nodes: nodesDataRef.current, edges: edgesDataRef.current },
      options
    );

    networkRef.current.on('click', (params) => {
      if (params.nodes.length > 0) {
        onNodeSelectRef.current(params.nodes[0] as string);
      } else if (params.edges.length > 0) {
        onEdgeSelectRef.current(params.edges[0] as string);
      } else {
        onNodeSelectRef.current(null);
        onEdgeSelectRef.current(null);
      }
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, []);

  // Track if initial stabilization is done
  const isStabilizedRef = useRef(false);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  /** Last `layoutDirection` from the nodes effect — used to detect leaving hierarchical layout. */
  const prevLayoutDirectionRef = useRef<'LR' | 'TD' | undefined>(undefined);
  /**
   * Mirror of the `physicsEnabled` prop, readable from inside async vis-network
   * event callbacks (`stabilizationIterationsDone`) where the closure-captured
   * prop value would be stale.
   */
  const physicsEnabledRef = useRef(physicsEnabled);
  useEffect(() => {
    physicsEnabledRef.current = physicsEnabled;
  }, [physicsEnabled]);

  // Toggle live physics on/off when the prop changes. Hierarchical layout always
  // runs with physics off (positions are baked in), so this is a no-op there.
  useEffect(() => {
    const net = networkRef.current;
    if (!net) return;
    if (layoutDirection) return;
    if (physicsEnabled) {
      net.setOptions({ physics: { enabled: true } });
      return;
    }
    // Disabling: capture positions so they survive future updates / context switches.
    const positions = net.getPositions();
    Object.entries(positions).forEach(([id, pos]) => {
      nodePositionsRef.current.set(id, pos as { x: number; y: number });
    });
    net.setOptions({ physics: { enabled: false } });
  }, [physicsEnabled, layoutDirection]);

  // Update nodes
  useEffect(() => {
    const prevLayoutDir = prevLayoutDirectionRef.current;
    const exitedHierarchicalLayout = prevLayoutDir !== undefined && layoutDirection === undefined;

    const seenIds = new Set<string>();
    const uniqueNodes = nodes.filter((node) => {
      if (seenIds.has(node.id)) return false;
      seenIds.add(node.id);
      return true;
    });

    try {
    if (layoutDirection) {
      // Hierarchical layout: positions are baked into toVisNode via hierarchicalPositions.
      // Disable physics and fit the view to the positioned graph.
      nodesDataRef.current.clear();
      nodesDataRef.current.add(uniqueNodes.map(toVisNode));
      if (networkRef.current && uniqueNodes.length > 0) {
        networkRef.current.setOptions({ physics: { enabled: false } });
        if (pendingFilterViewportApplyRef.current) {
          pendingFilterViewportApplyRef.current = false;
          applySavedViewportOrFit({ fitDurationMs: 500 });
        } else {
          networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
        }
      }
      isStabilizedRef.current = true;
      return;
    }

    // SubclassOf / hierarchy layout turned off: force a fresh force-directed pass (physics was disabled above).
    if (exitedHierarchicalLayout && networkRef.current) {
      isStabilizedRef.current = false;
      // Drop baked coordinates so ForceAtlas2 can lay out from scratch, not the hierarchy positions.
      nodePositionsRef.current.clear();
      networkRef.current.setOptions({ physics: { enabled: true } });
    }

    if (isStabilizedRef.current && networkRef.current) {
      // Save the latest positions for all currently displayed nodes.
      const livePositions = networkRef.current.getPositions();
      Object.entries(livePositions).forEach(([id, pos]) => {
        nodePositionsRef.current.set(id, pos as { x: number; y: number });
      });

      // Compute bounding box so new nodes (parents) appear above the existing layout.
      const yValues = Array.from(nodePositionsRef.current.values()).map((p) => p.y);
      const xValues = Array.from(nodePositionsRef.current.values()).map((p) => p.x);
      const minY = yValues.length > 0 ? Math.min(...yValues) : 0;
      const avgX = xValues.length > 0 ? xValues.reduce((s, v) => s + v, 0) / xValues.length : 0;
      const xSpread = xValues.length > 0 ? Math.max(...xValues) - Math.min(...xValues) : 600;

      const existingIds = new Set(nodesDataRef.current.getIds() as string[]);
      const incomingIds = new Set(uniqueNodes.map((n) => n.id));

      // Remove nodes that are no longer in the visible set.
      const removedIds = [...existingIds].filter((id) => !incomingIds.has(id));
      if (removedIds.length > 0) nodesDataRef.current.remove(removedIds);

      // Update existing nodes (preserving their current position) and add new ones.
      const toUpdate: Node[] = [];
      const toAdd: Node[] = [];
      let newIdx = 0;
      for (const node of uniqueNodes) {
        const base = toVisNode(node);
        const saved = nodePositionsRef.current.get(node.id);
        if (existingIds.has(node.id)) {
          // Keep current position — overwrite with saved coords to prevent vis-network drift.
          toUpdate.push({ ...base, x: saved?.x, y: saved?.y });
        } else {
          // New node (e.g. a loaded parent): place it in a row above existing nodes.
          const col = newIdx % 5;
          const row = Math.floor(newIdx / 5);
          const newX = avgX + (col - 2) * (xSpread / 4 + 150);
          const newY = minY - 350 - row * 180;
          toAdd.push({ ...base, x: newX, y: newY });
          newIdx++;
        }
      }
      if (toUpdate.length > 0) nodesDataRef.current.update(toUpdate);
      if (toAdd.length > 0) nodesDataRef.current.add(toAdd);
      if (pendingFilterViewportApplyRef.current && networkRef.current) {
        pendingFilterViewportApplyRef.current = false;
        requestAnimationFrame(() => applySavedViewportOrFit({ fitDurationMs: 300 }));
      }
      return;
    }

    // Initial load — full clear + add, then let physics stabilize.
    // Pre-spread nodes without a saved position using a sunflower spiral so
    // physics starts from a distributed layout rather than piling up at the origin.
    const unsavedIds = uniqueNodes
      .filter((n) => !nodePositionsRef.current.has(n.id))
      .map((n) => n.id);
    const spreadPositions = computeSpreadPositions(unsavedIds);

    const visNodes = uniqueNodes.map((node) => {
      const baseNode = toVisNode(node);
      const savedPos = nodePositionsRef.current.get(node.id);
      if (savedPos) return { ...baseNode, x: savedPos.x, y: savedPos.y };
      const initPos = spreadPositions.get(node.id);
      if (initPos) return { ...baseNode, x: initPos.x, y: initPos.y };
      return baseNode;
    });

    nodesDataRef.current.clear();
    nodesDataRef.current.add(visNodes);

    if (networkRef.current && visNodes.length > 0) {
      networkRef.current.once('stabilizationIterationsDone', () => {
        if (networkRef.current) {
          const positions = networkRef.current.getPositions();
          Object.entries(positions).forEach(([id, pos]) => {
            nodePositionsRef.current.set(id, pos as { x: number; y: number });
          });
          isStabilizedRef.current = true;
          if (!physicsEnabledRef.current) {
            networkRef.current.setOptions({ physics: { enabled: false } });
          }
          if (pendingFilterViewportApplyRef.current) {
            pendingFilterViewportApplyRef.current = false;
            applySavedViewportOrFit({ fitDurationMs: 500 });
          } else {
            networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
          }
        }
      });
      if (exitedHierarchicalLayout) {
        networkRef.current.stabilize(200);
      }
    }
    } finally {
      prevLayoutDirectionRef.current = layoutDirection;
    }
  }, [nodes, toVisNode, layoutDirection, applySavedViewportOrFit]);

  /**
   * If no code path consumes `pendingFilterViewportApplyRef` this frame (e.g. edges-only refresh),
   * still restore viewport after the graph settles.
   */
  useEffect(() => {
    if (!pendingFilterViewportApplyRef.current) return;
    const timer = window.setTimeout(() => {
      if (
        !pendingFilterViewportApplyRef.current ||
        !networkRef.current ||
        nodesDataRef.current.length === 0
      ) {
        return;
      }
      pendingFilterViewportApplyRef.current = false;
      applySavedViewportOrFit({ fitDurationMs: 300 });
    }, 420);
    return () => clearTimeout(timer);
  }, [
    viewStateKey,
    nodes.length,
    edges.length,
    layoutDirection,
    applySavedViewportOrFit,
  ]);

  // Update edges
  useEffect(() => {
    const seenIds = new Set<string>();
    const uniqueEdges = edges.filter((edge) => {
      if (seenIds.has(edge.id)) return false;
      seenIds.add(edge.id);
      return true;
    });
    edgesDataRef.current.clear();
    edgesDataRef.current.add(uniqueEdges.map(toVisEdge));
  }, [edges, toVisEdge]);

  // Re-run physics when stabilizeKey changes (bucket filter, relations, parents toggled).
  // Skip when in hierarchical layout — positions are already fixed.
  useEffect(() => {
    if (stabilizeKey === undefined || stabilizeKey === 0) return;
    if (!networkRef.current || layoutDirection) return;
    isStabilizedRef.current = false;
    networkRef.current.setOptions({ physics: { enabled: true } });
    networkRef.current.once('stabilizationIterationsDone', () => {
      if (!networkRef.current) return;
      const positions = networkRef.current.getPositions();
      Object.entries(positions).forEach(([id, pos]) => {
        nodePositionsRef.current.set(id, pos as { x: number; y: number });
      });
      isStabilizedRef.current = true;
      if (!physicsEnabledRef.current) {
        networkRef.current.setOptions({ physics: { enabled: false } });
      }
    });
    networkRef.current.stabilize(200);
  }, [stabilizeKey, layoutDirection]);

  // Handle selected node — select visually and pan to center on it without changing zoom.
  // Double-RAF delay lets the canvas finish resizing (inspector open/close) before we pan.
  useEffect(() => {
    if (!networkRef.current) return;

    const hadSelected = prevSelectedNodeIdRef.current !== null;
    prevSelectedNodeIdRef.current = selectedNodeId;

    let cancelled = false;

    if (!selectedNodeId) {
      // Inspector closing: re-fit the graph into the now-wider canvas.
      if (!hadSelected) return;
      requestAnimationFrame(() => {
        if (cancelled) return;
        requestAnimationFrame(() => {
          if (cancelled || !networkRef.current || nodesDataRef.current.length === 0) return;
          networkRef.current.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
        });
      });
      return () => { cancelled = true; };
    }

    if (!nodesDataRef.current.get(selectedNodeId)) return;
    networkRef.current.selectNodes([selectedNodeId]);

    // Wait for the canvas to finish resizing (inspector open shrinks it) before centering.
    requestAnimationFrame(() => {
      if (cancelled) return;
      requestAnimationFrame(() => {
        if (cancelled || !networkRef.current) return;
        const currentScale = networkRef.current.getScale();
        const targetScale = Math.max(currentScale, 1.35);
        networkRef.current.focus(selectedNodeId, {
          scale: targetScale,
          animation: { duration: 300, easingFunction: 'easeInOutQuad' },
        });
      });
    });

    return () => { cancelled = true; };
  }, [selectedNodeId]);

  return (
    <>
      <style jsx global>{`
        /* Style vis-network navigation buttons to match platform */
        .vis-navigation {
          position: absolute !important;
          bottom: 16px !important;
          right: 16px !important;
          left: auto !important;
          top: auto !important;
        }
        .vis-button {
          width: 32px !important;
          height: 32px !important;
          background-color: hsl(var(--card)) !important;
          border: 1px solid hsl(var(--border)) !important;
          border-radius: 8px !important;
          box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1) !important;
          background-size: 16px 16px !important;
          background-position: center !important;
          margin: 2px !important;
          cursor: pointer !important;
        }
        .vis-button:hover {
          background-color: hsl(var(--accent)) !important;
        }
        .vis-button.vis-up, .vis-button.vis-down, 
        .vis-button.vis-left, .vis-button.vis-right {
          display: none !important; /* Hide pan buttons, keep zoom */
        }
        .vis-button.vis-zoomIn {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='12' y1='5' x2='12' y2='19'%3E%3C/line%3E%3Cline x1='5' y1='12' x2='19' y2='12'%3E%3C/line%3E%3C/svg%3E") !important;
        }
        .vis-button.vis-zoomOut {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='5' y1='12' x2='19' y2='12'%3E%3C/line%3E%3C/svg%3E") !important;
        }
        .vis-button.vis-zoomExtends {
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='15 3 21 3 21 9'%3E%3C/polyline%3E%3Cpolyline points='9 21 3 21 3 15'%3E%3C/polyline%3E%3Cline x1='21' y1='3' x2='14' y2='10'%3E%3C/line%3E%3Cline x1='3' y1='21' x2='10' y2='14'%3E%3C/line%3E%3C/svg%3E") !important;
        }
      `}</style>
      <div
        ref={containerRef}
        className="h-full w-full"
        style={{ minHeight: '400px' }}
      />
    </>
  );
}

export const BFO_BUCKET_DEFS = [
  { type: 'Material Entity', label: 'Who', description: 'Objects, people, organizations' },
  { type: 'Process', label: 'What', description: 'Events, activities, changes' },
  { type: 'Temporal Region', label: 'When', description: 'Time periods, instants' },
  { type: 'Site', label: 'Where', description: 'Locations, places' },
  { type: 'Quality', label: 'How it is', description: 'Properties, attributes' },
  { type: 'Realizable', label: 'Why', description: 'Roles & dispositions' },
  { type: 'GDC', label: 'How we know', description: 'Documents, data, plans' },
  { type: 'Entity', label: 'Entity', description: 'Entity' },
  { type: 'Unknown', label: 'Unknown', description: 'Unclassified or unresolved bucket' },
];

export function BFOBucketFilters({
  activeBuckets,
  effectiveActiveBuckets,
  onToggle,
  nodesPerBucket,
  hiddenNodeIds,
  onNodeToggle,
}: {
  activeBuckets: Set<string>;
  effectiveActiveBuckets?: Set<string>;
  onToggle: (bucketType: string) => void;
  nodesPerBucket?: Map<string, Array<{ id: string; label: string }>>;
  hiddenNodeIds?: Set<string>;
  onNodeToggle?: (nodeId: string) => void;
}) {
  const [tooltip, setTooltip] = useState<{
    label: string;
    type: string;
    description: string;
    position: { top: number; left: number };
  } | null>(null);
  const [expandedBuckets, setExpandedBuckets] = useState<Set<string>>(new Set());

  const displayActive = effectiveActiveBuckets ?? activeBuckets;

  return (
    <div className="absolute top-4 right-4 z-10 max-h-[calc(100vh-8rem)] w-44 overflow-y-auto rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        BFO 7 Buckets
      </h4>
      <div className="flex flex-col gap-0.5">
        {BFO_BUCKET_DEFS.map((bucket) => {
          const colors = BFO_COLORS[bucket.type as keyof typeof BFO_COLORS];
          const anySelected = displayActive.size > 0;
          const isActive = displayActive.has(bucket.type);
          const bucketNodes = nodesPerBucket?.get(bucket.type) ?? [];
          const isExpanded = expandedBuckets.has(bucket.type);

          return (
            <div
              key={bucket.type}
              className={cn('rounded-md transition-all', anySelected && !isActive ? 'opacity-30' : 'opacity-100')}
            >
              <div className="flex items-center">
                <button
                  onClick={() => onToggle(bucket.type)}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setTooltip({
                      label: bucket.label,
                      type: bucket.type,
                      description: bucket.description,
                      position: { top: rect.top, left: rect.left - 8 },
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                  className="flex flex-1 items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted"
                >
                  <div
                    className="h-3 w-3 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: colors.background }}
                  />
                  <strong className="flex-1">{bucket.label}</strong>
                  {bucketNodes.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">{bucketNodes.length}</span>
                  )}
                </button>
                {bucketNodes.length > 0 && (
                  <button
                    onClick={() =>
                      setExpandedBuckets((prev) => {
                        const next = new Set(prev);
                        if (next.has(bucket.type)) next.delete(bucket.type);
                        else next.add(bucket.type);
                        return next;
                      })
                    }
                    className="px-1 py-1 text-muted-foreground hover:text-foreground"
                  >
                    <ChevronRight size={10} className={cn('transition-transform', isExpanded && 'rotate-90')} />
                  </button>
                )}
              </div>
              {isExpanded && bucketNodes.length > 0 && (
                <div className="ml-3 mt-0.5 space-y-0.5 border-l border-border pl-2">
                  {bucketNodes.map((node) => {
                    const isHidden = hiddenNodeIds?.has(node.id) ?? false;
                    return (
                      <label
                        key={node.id}
                        className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 hover:bg-muted"
                      >
                        <input
                          type="checkbox"
                          checked={!isHidden}
                          onChange={() => onNodeToggle?.(node.id)}
                          className="h-3 w-3 cursor-pointer"
                        />
                        <span className="max-w-[100px] truncate text-[11px]">{node.label}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {tooltip && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed z-[100] whitespace-nowrap rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-lg animate-in fade-in-0 zoom-in-95 duration-100"
          style={{ top: tooltip.position.top, left: tooltip.position.left, transform: 'translateX(-100%)' }}
        >
          <p className="font-medium">{tooltip.label} <span className="font-normal text-muted-foreground">({tooltip.type})</span></p>
          <p className="text-xs text-muted-foreground">{tooltip.description}</p>
        </div>,
        document.body
      )}
    </div>
  );
}

// Static legend for pages that don't need interactive bucket filtering
export function BFOLegend() {
  return (
    <div className="absolute top-4 right-4 z-10 rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        BFO 7 Buckets
      </h4>
      <div className="grid grid-cols-2 gap-2">
        {BFO_BUCKET_DEFS.map((bucket) => {
          const colors = BFO_COLORS[bucket.type as keyof typeof BFO_COLORS];
          return (
            <div key={bucket.type} className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: colors.background }} />
              <span className="text-xs"><strong>{bucket.label}</strong></span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
