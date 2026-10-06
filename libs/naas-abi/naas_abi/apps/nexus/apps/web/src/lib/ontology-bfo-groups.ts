import { BFO_BUCKET_BY_TYPE, BFO_BUCKET_DEFS, type BfoBucketDef } from './bfo-buckets';
import { bfoBucketResolver } from './detail-network';
import { buildDictionaryTree, type DictionaryLink, type DictionaryNode, type DictionaryTerm } from './ontology-dictionary-tree';

export type BfoBucketGroup = { bucket: BfoBucketDef; terms: DictionaryTerm[]; tree: DictionaryNode[] };

/**
 * Subclass hierarchy inside one bucket. A class sits under its nearest
 * ancestor from the same group, however far up the import chain that is:
 * abi:ActOfStudying (-> CCO Planned Act -> bfo:process) goes under
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
 * Classes the selection points at without declaring them, flagged
 * ``referenced``: abi:GeospatialRegion, declared in ABIOntology, as the place
 * PeopleOntology's Act of Working occurs in; cco:ont00000270 (Educational
 * Facility), declared nowhere in the workspace, carries the bucket and
 * ancestors the server resolved through imports. ``paths`` adds restrictions
 * those files state on classes declared elsewhere.
 */
export function referencedClasses(terms: DictionaryTerm[], allTerms: DictionaryTerm[], paths: string[] = []): DictionaryTerm[] {
  const selected = new Set(terms.filter(term => term.type === 'entity').map(term => term.id));
  const declared = new Map(allTerms.filter(term => term.type === 'entity').map(term => [term.id, term]));
  const found = new Map<string, DictionaryTerm>();
  const add = (link: DictionaryLink) => {
    if (selected.has(link.id) || found.has(link.id) || link.id.startsWith('_:')) return;
    const known = declared.get(link.id);
    found.set(link.id, known ? { ...known, referenced: true }
      : { id: link.id, name: link.name, type: 'entity', referenced: true, bfoBucket: link.bfoBucket, bfoAncestors: link.bfoAncestors });
  };
  for (const term of terms) {
    if (term.type !== 'entity') continue;
    for (const relation of term.relations || []) add(relation.target);
  }
  if (paths.length) for (const term of allTerms) for (const relation of term.relations || []) {
    if (relation.kind === 'restriction' && relation.sources.some(source => paths.includes(source.path))) add(relation.target);
  }
  return [...found.values()].sort((a, b) => a.name.localeCompare(b.name));
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
