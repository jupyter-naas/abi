import { BFO_BUCKET_BY_TYPE, BFO_BUCKET_DEFS, type BfoBucketDef } from './bfo-buckets';
import { bfoBucketResolver } from './detail-network';
import { buildDictionaryTree, type DictionaryLink, type DictionaryNode, type DictionaryTerm } from './ontology-dictionary-tree';

export type BfoBucketGroup = { bucket: BfoBucketDef; terms: DictionaryTerm[]; tree: DictionaryNode[] };

/**
 * Subclass hierarchy inside one bucket. A class sits under its nearest
 * ancestor from the same group, however far up the import chain that is:
 * people:ActOfStudying (-> CCO Planned Act -> bfo:process) goes under
 * abi:Process, which is equivalent to bfo:process. A class with no such
 * ancestor is a top-level entry of its bucket.
 */
function bucketTree(terms: DictionaryTerm[]): DictionaryNode[] {
  // A class answers to its own IRI and to those of its equivalents.
  const keys = new Map(terms.map(term => [term.id, new Set([term.id, ...(term.equivalents || []).map(link => link.id)])]));
  const above = new Map(terms.map(term => [term.id, new Set([...(term.bfoAncestors || []), ...(term.parents || []).map(link => link.id)])]));
  const isAbove = (upper: DictionaryTerm, lower: DictionaryTerm) =>
    upper.id !== lower.id && [...keys.get(upper.id)!].some(key => above.get(lower.id)!.has(key));
  return buildDictionaryTree(terms.map(term => {
    // Strictly above: equivalent classes (abi:Person, CCO Person) must not nest under each other.
    const candidates = terms.filter(other => isAbove(other, term) && !isAbove(term, other));
    const nearest = candidates.filter(candidate => !candidates.some(other => other !== candidate && isAbove(candidate, other)));
    return { ...term, parent_id: undefined, parents: nearest.map(parent => ({ id: parent.id, name: parent.name })) };
  }));
}

/**
 * Classes a selected class points at without the workspace declaring them,
 * such as cco:ont00000270 (Educational Facility) as the place Act of Studying
 * occurs in. They carry the bucket and ancestors the server resolved through imports.
 */
function referencedClasses(terms: DictionaryTerm[], allTerms: DictionaryTerm[]): DictionaryTerm[] {
  const declared = new Set(allTerms.filter(term => term.type === 'entity').map(term => term.id));
  const found = new Map<string, DictionaryTerm>();
  const add = (link: DictionaryLink) => {
    if (declared.has(link.id) || found.has(link.id) || link.id.startsWith('_:')) return;
    found.set(link.id, { id: link.id, name: link.name, type: 'entity', referenced: true, bfoBucket: link.bfoBucket, bfoAncestors: link.bfoAncestors });
  };
  for (const term of terms) {
    if (term.type !== 'entity') continue;
    for (const relation of term.relations || []) add(relation.target);
  }
  return [...found.values()];
}

/** Display order of the BFO 7 Buckets view: the process first, then what frames and fills it. */
export const BFO_GROUP_ORDER = [
  'Process', 'Temporal Region', 'Material Entity', 'Site', 'GDC', 'Quality', 'Realizable', 'Entity', 'Unknown',
] as const;

/**
 * Group classes by BFO bucket, in ``BFO_GROUP_ORDER``. Every bucket is
 * returned, empty ones included, so gaps are visible: Entity holds classes that
 * only reach bfo:entity, Unknown those that reach no BFO root at all.
 * ``allTerms`` is the whole workspace dictionary: a class may reach its bucket
 * through a parent outside the current selection. Classes the selection only
 * references are grouped too, flagged ``referenced``.
 */
export function groupClassesByBfoBucket(terms: DictionaryTerm[], allTerms: DictionaryTerm[]): BfoBucketGroup[] {
  const referenced = referencedClasses(terms, allTerms);
  const resolve = bfoBucketResolver([...allTerms, ...referenced], { entityFallback: true });
  const byType = new Map<string, DictionaryTerm[]>();
  for (const term of [...terms, ...referenced]) {
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
