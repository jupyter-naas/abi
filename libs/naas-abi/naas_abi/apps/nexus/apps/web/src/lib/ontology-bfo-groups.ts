import { BFO_BUCKET_BY_TYPE, BFO_BUCKET_DEFS, type BfoBucketDef } from './bfo-buckets';
import { bfoBucketResolver } from './detail-network';
import { buildDictionaryTree, type DictionaryNode, type DictionaryTerm } from './ontology-dictionary-tree';

export type BfoBucketGroup = { bucket: BfoBucketDef; terms: DictionaryTerm[]; tree: DictionaryNode[] };

/**
 * Subclass hierarchy inside one bucket. Only parents in the same group are
 * kept: a class whose parents sit elsewhere (abi:Person under CCO Animal) is a
 * top-level entry of its bucket rather than under a placeholder parent.
 */
function bucketTree(terms: DictionaryTerm[]): DictionaryNode[] {
  const ids = new Set(terms.map(term => term.id));
  return buildDictionaryTree(terms.map(term => ({ ...term, parent_id: undefined, parents: (term.parents || []).filter(parent => ids.has(parent.id)) })));
}

/** Display order of the 7 buckets view: the process first, then what frames and fills it. */
export const BFO_GROUP_ORDER = [
  'Process', 'Temporal Region', 'Material Entity', 'Site', 'GDC', 'Quality', 'Realizable', 'Entity', 'Unknown',
] as const;

/**
 * Group classes by BFO bucket, in ``BFO_GROUP_ORDER``. Every bucket is
 * returned, empty ones included, so gaps are visible: Entity holds classes that
 * only reach bfo:entity, Unknown those that reach no BFO root at all.
 * ``allTerms`` is the whole workspace dictionary: a class may reach its bucket
 * through a parent outside the current selection.
 */
export function groupClassesByBfoBucket(terms: DictionaryTerm[], allTerms: DictionaryTerm[]): BfoBucketGroup[] {
  const resolve = bfoBucketResolver(allTerms, { entityFallback: true });
  const byType = new Map<string, DictionaryTerm[]>();
  for (const term of terms) {
    if (term.type !== 'entity') continue;
    const iri = resolve(term.id);
    const type = iri ? BFO_BUCKET_DEFS.find(def => def.uri === iri)?.type ?? 'Unknown' : 'Unknown';
    byType.set(type, [...(byType.get(type) || []), term]);
  }
  return BFO_GROUP_ORDER.map(type => {
    const grouped = byType.get(type) || [];
    return { bucket: BFO_BUCKET_BY_TYPE[type], terms: grouped, tree: bucketTree(grouped) };
  });
}
