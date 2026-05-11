import type { GraphNode } from './types';

/**
 * BFO bucket resolution for instance-graph nodes.
 *
 * Variant of `lib/bfo.ts:resolveBucket` tailored to the instance graph: the
 * BFO bucket is read from `properties.bfo_parent_iri` / `properties.parent_iri`
 * (set by the API when classifying individuals), not from a structural parent
 * traversal. Returns `'Unknown'` when no mapping is found.
 *
 * Keep colocated with the graph network view so changes don't ripple into the
 * ontology page or the canonical BFO map.
 */
const BFO_BUCKET_KEYS_GRAPH = new Set([
  'Material Entity',
  'Process',
  'Temporal Region',
  'Site',
  'Quality',
  'Realizable',
  'GDC',
]);

const BFO_URI_TO_BUCKET_GRAPH: Record<string, string> = {
  'http://purl.obolibrary.org/obo/BFO_0000040': 'Material Entity',
  'http://purl.obolibrary.org/obo/BFO_0000015': 'Process',
  'http://purl.obolibrary.org/obo/BFO_0000008': 'Temporal Region',
  'http://purl.obolibrary.org/obo/BFO_0000029': 'Site',
  'http://purl.obolibrary.org/obo/BFO_0000031': 'GDC',
  'http://purl.obolibrary.org/obo/BFO_0000019': 'Quality',
  'http://purl.obolibrary.org/obo/BFO_0000017': 'Realizable',
};

export function resolveGraphNodeBucket(node: GraphNode): string {
  if (BFO_BUCKET_KEYS_GRAPH.has(node.type)) return node.type;
  const bfoParentIri = node.properties?.bfo_parent_iri as string | undefined;
  if (bfoParentIri && bfoParentIri in BFO_URI_TO_BUCKET_GRAPH) {
    return BFO_URI_TO_BUCKET_GRAPH[bfoParentIri];
  }
  const parentIri = node.properties?.parent_iri as string | undefined;
  if (parentIri && parentIri in BFO_URI_TO_BUCKET_GRAPH) {
    return BFO_URI_TO_BUCKET_GRAPH[parentIri];
  }
  return 'Unknown';
}
