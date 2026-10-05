import type { GraphEdge, GraphNode } from '../stores/knowledge-graph';
import { BFO_BUCKET_DEFS } from './bfo-buckets';
import { bfoBucketResolver } from './detail-network';
import { termKey } from './ontology-context';
import type { DashboardRestriction } from './ontology-dashboard';
import { dictionaryKindLabel, type DictionaryTerm } from './ontology-dictionary-tree';

/** One process slice consolidated into a module ontology, as the API reports it. */
export type ProcessSlice = {
  id: string; name: string; path: string; classes: string[];
  restrictions: Array<{ subject: string; property: string; target: string }>;
};
export type FileNetwork = { nodes: GraphNode[]; edges: GraphEdge[] };

const sliceKey = (subject: string, property: string, target: string) => JSON.stringify([subject, property, target]);

/**
 * The classes of one ontology file and the restrictions it states, for the BFO
 * 7 buckets layout. With processes selected, only what those slices state is
 * kept: their classes and their restrictions. Without, every class the file
 * declares is a card, restricted or not.
 */
export function buildFileNetwork(
  fileTerms: DictionaryTerm[], restrictions: DashboardRestriction[], allTerms: DictionaryTerm[],
  slices: ProcessSlice[] = [], selected: ReadonlySet<string> = new Set(),
): FileNetwork {
  const chosen = slices.filter(slice => selected.has(slice.id));
  const allowed = chosen.length ? new Set(chosen.flatMap(slice => slice.restrictions.map(item => sliceKey(item.subject, item.property, item.target)))) : null;
  const kept = allowed ? restrictions.filter(item => allowed.has(sliceKey(item.subject.id, item.property.id, item.target.id))) : restrictions;
  const resolve = bfoBucketResolver(allTerms, { entityFallback: true });
  const declared = new Map(allTerms.filter(term => term.type === 'entity').map(term => [term.id, term]));
  const nodes = new Map<string, GraphNode>();
  const addNode = (id: string, name: string): string => {
    const term = declared.get(id);
    const key = termKey({ id, name, type: 'entity' });
    if (!nodes.has(key)) {
      const bucket = resolve(id);
      nodes.set(key, {
        id: key, label: term?.name || name,
        type: BFO_BUCKET_DEFS.find(def => def.uri === bucket)?.type || 'Unknown',
        properties: {
          iri: id, term_type: 'entity', kind: term ? dictionaryKindLabel('entity') : 'Referenced term',
          definition: term?.description || '', bfo_parent_iri: bucket, source_files: term?.sources || [], is_primary: false,
        },
      });
    }
    return key;
  };
  const cards = chosen.length
    ? chosen.flatMap(slice => slice.classes).map(id => declared.get(id)).filter((term): term is DictionaryTerm => Boolean(term))
    : fileTerms.filter(term => term.type === 'entity');
  for (const term of cards) addNode(term.id, term.name);
  const edges: GraphEdge[] = kept.map(item => {
    const source = addNode(item.subject.id, item.subject.name);
    const target = addNode(item.target.id, item.target.name);
    return {
      id: item.key, source, target, type: item.property.name, label: item.property.name,
      properties: { relation_kind: 'restriction', property_iri: item.property.id, declaration: 'restriction', constraint: item.constraint, source_files: item.sources },
    };
  });
  return { nodes: [...nodes.values()], edges };
}
