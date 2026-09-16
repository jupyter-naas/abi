import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
import { BFO_BUCKET_DEFS, type BfoBucketDef } from './bfo-buckets';

export type BucketTreeNode = { node: GraphNode; children: BucketTreeNode[] };
export type BucketTree = { bucket: BfoBucketDef; roots: BucketTreeNode[]; count: number };
const compare = (a: GraphNode, b: GraphNode) => a.label.localeCompare(b.label, undefined, { numeric: true });

/** A navigation tree over the current graph, not a new set of ontology assertions. */
export function buildBucketTree(nodes: GraphNode[], edges: GraphEdge[], definitions = BFO_BUCKET_DEFS): BucketTree[] {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const parents = new Map<string, Set<string>>();
  for (const edge of edges) {
    const kind = edge.properties?.relation_kind;
    if (kind !== 'is_a' && kind !== 'system_group') continue;
    const [child, parent] = kind === 'is_a' ? [edge.source, edge.target] : [edge.target, edge.source];
    if (child === parent || !byId.has(child) || !byId.has(parent) || byId.get(child)!.type !== byId.get(parent)!.type) continue;
    if (!parents.has(child)) parents.set(child, new Set());
    parents.get(child)!.add(parent);
  }
  function reaches(from: string, target: string) {
    const pending = [from], seen = new Set<string>();
    while (pending.length) {
      const id = pending.pop()!;
      if (id === target) return true;
      if (seen.has(id)) continue;
      seen.add(id); pending.push(...(parents.get(id) || []));
    }
    return false;
  }
  // Prefer a specific parent over its ancestor; show multiply-inherited nodes once.
  const chosen = new Map<string, string>();
  for (const node of [...nodes].sort(compare)) {
    const candidates = [...(parents.get(node.id) || [])];
    const specific = candidates.filter(parent => !candidates.some(other => other !== parent && reaches(other, parent) && !reaches(parent, other)));
    for (const parent of specific.sort((a, b) => compare(byId.get(a)!, byId.get(b)!))) {
      let current: string | undefined = parent;
      while (current && current !== node.id) current = chosen.get(current);
      if (current === node.id) continue;
      chosen.set(node.id, parent); break;
    }
  }
  const entries = new Map(nodes.map(node => [node.id, { node, children: [] } as BucketTreeNode]));
  for (const [child, parent] of chosen) entries.get(parent)!.children.push(entries.get(child)!);
  for (const entry of entries.values()) entry.children.sort((a, b) => compare(a.node, b.node));
  return definitions.map(bucket => {
    const members = nodes.filter(node => node.type === bucket.type || (bucket.type === 'Unknown' && !definitions.some(def => def.type === node.type)));
    return { bucket, count: members.length, roots: members.filter(node => !chosen.has(node.id)).sort(compare).map(node => entries.get(node.id)!) };
  }).filter(({ bucket, count }) => !['Entity', 'Unknown'].includes(bucket.type) || count > 0);
}

/** Keep the ancestors of a search match so its position remains understandable. */
export function filterBucketTree(tree: BucketTree[], query: string): BucketTree[] {
  const search = query.trim().toLowerCase();
  if (!search) return tree;
  function filter(entry: BucketTreeNode): BucketTreeNode | null {
    if (`${entry.node.label} ${entry.node.properties.definition || ''}`.toLowerCase().includes(search)) return entry;
    const children = entry.children.map(filter).filter((item): item is BucketTreeNode => item !== null);
    return children.length ? { ...entry, children } : null;
  }
  return tree.map(group => ({ ...group, roots: `${group.bucket.label} ${group.bucket.type}`.toLowerCase().includes(search) ? group.roots : group.roots.map(filter).filter((item): item is BucketTreeNode => item !== null) }))
    .filter(group => group.roots.length > 0);
}
