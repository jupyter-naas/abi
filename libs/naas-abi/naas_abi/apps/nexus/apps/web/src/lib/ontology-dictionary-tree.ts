export type DictionaryLink = { id: string; name: string; sources?: Array<{path: string; name: string; moduleName: string}> };

export type DictionaryTerm = {
  id: string;
  name: string;
  type: 'entity' | 'relationship' | 'attribute' | 'annotation' | 'individual';
  sources?: Array<{ path: string; name: string; moduleName: string }>;
  definitions?: Array<{ value: string; source_path: string }>;
  parents?: DictionaryLink[];
  equivalents?: DictionaryLink[];
  systemViewKind?: string | null;
  systemViewParents?: DictionaryLink[];
  /** Source ledger wording and business groupings, independent of formal BFO types. */
  processLedger?: {
    code?: string | null;
    buckets: Record<string, Array<{ value: string; sources: NonNullable<DictionaryTerm['sources']> }>>;
    status?: string[];
  } | null;
  sourceValues?: string[];
  domain?: DictionaryLink[];
  range?: DictionaryLink[];
  inverse?: DictionaryLink[];
  examples?: string[];
  aliases?: string[];
  contributors?: string[];
  contacts?: string[];
  relations?: Array<{
    property: { id: string; name: string };
    target: { id: string; name: string };
    kind: 'assertion' | 'restriction';
    constraint?: string;
    sources: Array<{ path: string; name: string; moduleName: string }>;
  }>;
  description?: string;
  parent_id?: string;
  parent_name?: string;
};

export type DictionaryNode = {
  id: string;
  name: string;
  term?: DictionaryTerm;
  children: DictionaryNode[];
};

/** Preserve every named parent, including multiple inheritance, without cycles. */
export function buildDictionaryTree(terms: DictionaryTerm[]): DictionaryNode[] {
  const nodes = new Map<string, DictionaryNode>();
  const key = (term: DictionaryTerm) => `${term.type}:${term.id}`;
  for (const term of terms) nodes.set(key(term), { id: key(term), name: term.name, term, children: [] });
  const children = new Map<string, Set<string>>();
  const hasParent = new Set<string>();
  for (const term of terms) {
    const parents = term.parents || (term.parent_id ? [{ id: term.parent_id, name: term.parent_name || '' }] : []);
    for (const parent of parents) {
      if (!parent.id || parent.id === 'Unknown' || parent.id.startsWith('_:') || parent.id === term.id) continue;
      const parentKey = `${term.type === 'individual' ? 'entity' : term.type}:${parent.id}`;
      if (!nodes.has(parentKey)) nodes.set(parentKey, { id: parentKey, name: parent.name && parent.name !== 'Unknown' ? parent.name : parent.id.split(/[/#]/).pop() || parent.id, children: [] });
      if (!children.has(parentKey)) children.set(parentKey, new Set());
      children.get(parentKey)!.add(key(term));
      hasParent.add(key(term));
    }
  }
  const reached = new Set<string>();
  const ordered = (ids: Iterable<string>) => Array.from(ids).sort((a, b) => nodes.get(a)!.name.localeCompare(nodes.get(b)!.name));
  function branch(id: string, path: Set<string>): DictionaryNode {
    reached.add(id);
    const next = new Set(path).add(id);
    return { ...nodes.get(id)!, children: ordered(children.get(id) || []).filter(child => !next.has(child)).map(child => branch(child, next)) };
  }
  const roots = ordered(nodes.keys()).filter(id => !hasParent.has(id)).map(id => branch(id, new Set()));
  // A component made only of cycles has no root; keep it reachable as well.
  for (const id of ordered(nodes.keys())) if (!reached.has(id)) roots.push(branch(id, new Set()));
  return roots;
}

export function filterDictionaryTree(nodes: DictionaryNode[], query: string): DictionaryNode[] {
  const q = query.trim().toLowerCase();
  if (!q) return nodes;
  return nodes.flatMap(node => {
    const children = filterDictionaryTree(node.children, q);
    const matches = `${node.name} ${node.term?.description || ''}`.toLowerCase().includes(q);
    return matches || children.length ? [{ ...node, children }] : [];
  });
}

export function dictionaryKindLabel(kind: DictionaryTerm['type']): string {
  return { entity: 'Class', relationship: 'Object Property', attribute: 'Data Property', annotation: 'Annotation', individual: 'Individual' }[kind];
}
