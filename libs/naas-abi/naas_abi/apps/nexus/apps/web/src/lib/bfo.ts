/**
 * BFO (Basic Formal Ontology) bucket resolution + colors.
 *
 * Single source of truth replacing the three forked implementations that used to
 * live in `vis-network.tsx`, `graph/page.tsx`, and `ontology/page.tsx`. Coloring
 * and panel grouping are now provably consistent: a node coloured "Material
 * Entity" can no longer be listed under "Unknown" in the bucket panel.
 */

export type BfoBucket =
  | 'Material Entity'
  | 'Process'
  | 'Temporal Region'
  | 'Site'
  | 'Quality'
  | 'Realizable'
  | 'GDC'
  | 'Entity'
  | 'Unknown';

export interface BucketColors {
  background: string;
  border: string;
  highlight: string;
}

export const BFO_COLORS: Record<BfoBucket, BucketColors> = {
  'Material Entity': { background: '#3b82f6', border: '#2563eb', highlight: '#60a5fa' },
  Process: { background: '#22c55e', border: '#16a34a', highlight: '#4ade80' },
  'Temporal Region': { background: '#a855f7', border: '#9333ea', highlight: '#c084fc' },
  Site: { background: '#f97316', border: '#ea580c', highlight: '#fb923c' },
  Quality: { background: '#ec4899', border: '#db2777', highlight: '#f472b6' },
  Realizable: { background: '#eab308', border: '#ca8a04', highlight: '#facc15' },
  GDC: { background: '#06b6d4', border: '#0891b2', highlight: '#22d3ee' },
  Entity: { background: '#6b7280', border: '#4b5563', highlight: '#9ca3af' },
  Unknown: { background: '#9ca3af', border: '#6b7280', highlight: '#d1d5db' },
};

export const BFO_BUCKET_DEFS: ReadonlyArray<{
  type: BfoBucket;
  label: string;
  description: string;
}> = [
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

const BFO_URI_TO_BUCKET: Record<string, BfoBucket> = {
  'http://purl.obolibrary.org/obo/BFO_0000001': 'Entity',
  'http://purl.obolibrary.org/obo/BFO_0000040': 'Material Entity',
  'http://purl.obolibrary.org/obo/BFO_0000015': 'Process',
  'http://purl.obolibrary.org/obo/BFO_0000008': 'Temporal Region',
  'http://purl.obolibrary.org/obo/BFO_0000029': 'Site',
  'http://purl.obolibrary.org/obo/BFO_0000031': 'GDC',
  'http://purl.obolibrary.org/obo/BFO_0000019': 'Quality',
  'http://purl.obolibrary.org/obo/BFO_0000017': 'Realizable',
  BFO_0000001: 'Entity',
  BFO_0000040: 'Material Entity',
  BFO_0000015: 'Process',
  BFO_0000008: 'Temporal Region',
  BFO_0000029: 'Site',
  BFO_0000031: 'GDC',
  BFO_0000019: 'Quality',
  BFO_0000017: 'Realizable',
};

const LABEL_TO_BUCKET: Record<string, BfoBucket> = {
  entity: 'Entity',
  process: 'Process',
  'process boundary': 'Process',
  'temporal region': 'Temporal Region',
  'temporal interval': 'Temporal Region',
  'zero-dimensional temporal region': 'Temporal Region',
  'one-dimensional temporal region': 'Temporal Region',
  'material entity': 'Material Entity',
  object: 'Material Entity',
  'object aggregate': 'Material Entity',
  'fiat object part': 'Material Entity',
  site: 'Site',
  'immaterial entity': 'Site',
  'spatial region': 'Site',
  'continuant fiat boundary': 'Site',
  'generically dependent continuant': 'GDC',
  quality: 'Quality',
  'specifically dependent continuant': 'Quality',
  role: 'Realizable',
  disposition: 'Realizable',
  'realizable entity': 'Realizable',
};

/** Minimal node shape this module needs. Compatible with all callers. */
export interface BucketResolvable {
  id: string;
  type: string;
  properties?: Record<string, unknown> | null;
}

/**
 * Resolve a node to its BFO bucket, walking the parent chain when needed.
 *
 * Resolution order:
 *  1. `properties.bfo_parent_iri` — authoritative ancestor from backend SPARQL
 *  2. `node.type` directly matches a bucket key (already-tagged KG nodes)
 *  3. `node.type` lowercase matches a known BFO/CCO label
 *  4. `node.type` is a BFO URI (full or short form)
 *  5. `properties.parent_iri` matches a BFO URI
 *  6. Walk `properties.parent_iri` recursively in `nodesById`
 *  7. Fallback: `'Unknown'`
 */
export function resolveBucket(
  node: BucketResolvable,
  nodesById?: ReadonlyMap<string, BucketResolvable>,
  visited: Set<string> = new Set(),
): BfoBucket {
  const bfoParentIri = node.properties?.bfo_parent_iri;
  if (typeof bfoParentIri === 'string' && bfoParentIri in BFO_URI_TO_BUCKET) {
    return BFO_URI_TO_BUCKET[bfoParentIri];
  }

  if (node.type in BFO_COLORS) return node.type as BfoBucket;

  const lowerType = node.type?.toLowerCase?.() ?? '';
  if (lowerType in LABEL_TO_BUCKET) return LABEL_TO_BUCKET[lowerType];

  if (node.type in BFO_URI_TO_BUCKET) return BFO_URI_TO_BUCKET[node.type];

  const parentIri = node.properties?.parent_iri;
  if (typeof parentIri === 'string') {
    if (parentIri in BFO_URI_TO_BUCKET) return BFO_URI_TO_BUCKET[parentIri];
    if (nodesById && !visited.has(node.id)) {
      visited.add(node.id);
      const parent = nodesById.get(parentIri);
      if (parent) return resolveBucket(parent, nodesById, visited);
    }
  }

  return 'Unknown';
}

/** Convenience: resolve directly to colors (with `Entity` fallback). */
export function resolveBucketColors(
  node: BucketResolvable,
  nodesById?: ReadonlyMap<string, BucketResolvable>,
): BucketColors {
  const bucket = resolveBucket(node, nodesById);
  return BFO_COLORS[bucket] ?? BFO_COLORS.Entity;
}

const DEFAULT_MAX_CHARS_PER_LINE = 14;

/**
 * Wrap a label across at most two lines, with a trailing ellipsis when the
 * second line overflows. Used for vis-network node SVG cards.
 */
export function wrapLabelTwoLines(label: string, maxCharsPerLine = DEFAULT_MAX_CHARS_PER_LINE): string {
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
    line2 = normalized.slice(line1.length).trim();
  }
  if (line2.length > maxCharsPerLine) {
    line2 = `${line2.slice(0, Math.max(0, maxCharsPerLine - 1)).trimEnd()}…`;
  }

  return line2 ? `${line1}\n${line2}` : line1;
}
