import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
import type { DictionaryTerm } from './ontology-dictionary-tree';
import { termKey } from './ontology-context';

/** Resolve only an actual, permitted term; ledger labels need not be OWL classes. */
export function inspectorTerm(node: GraphNode, terms: DictionaryTerm[]): DictionaryTerm | undefined {
  const key = typeof node.properties.formal_term_id === 'string' ? node.properties.formal_term_id : node.id;
  return terms.find(term => termKey(term) === key);
}

export function inspectorConnections(node: GraphNode, nodes: GraphNode[], edges: GraphEdge[]) {
  const byId = new Map(nodes.map(item => [item.id, item]));
  return edges.filter(edge => edge.source === node.id || edge.target === node.id).flatMap(edge => {
    const other = byId.get(edge.source === node.id ? edge.target : edge.source);
    if (!other) return [];
    return [{ edge, other, incoming: edge.target === node.id }];
  });
}

export function inspectorSources(node: GraphNode, term?: DictionaryTerm): NonNullable<DictionaryTerm['sources']> {
  const sourceFiles = node.properties.source_files;
  const sources = Array.isArray(sourceFiles) ? sourceFiles.filter((source): source is NonNullable<DictionaryTerm['sources']>[number] =>
    source && typeof source.path === 'string' && typeof source.name === 'string') : [];
  return [...new Map([...sources, ...(term?.sources || [])].map(source => [source.path, source])).values()];
}
