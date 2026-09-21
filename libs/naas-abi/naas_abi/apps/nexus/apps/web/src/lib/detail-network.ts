import type { GraphEdge, GraphNode } from '@/stores/knowledge-graph';
import { ontologyConnections, termConnections, termKey, type TermRef } from './ontology-context';
import type { DictionaryTerm } from './ontology-dictionary-tree';

export type InstanceRelation = {
  role: 'domain' | 'range';
  predicate_uri: string;
  predicate_label: string;
  other_uri: string;
  other_label: string;
};

function compactUri(uri: string) {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

function addNode(nodes: Map<string, GraphNode>, id: string, label: string, type: string, extra: Record<string, unknown> = {}) {
  if (!nodes.has(id)) {
    nodes.set(id, { id, label: label || compactUri(id), type, properties: extra });
  }
  return id;
}

/** Domain links only. Range rows are the inverse view of someone else's connection. */
export function instanceDomainRelations(relations: InstanceRelation[]) {
  return relations.filter(relation => relation.role === 'domain');
}

export function instanceDomainRelationsKey(relations: InstanceRelation[]) {
  return instanceDomainRelations(relations)
    .map(relation => [relation.predicate_uri, relation.predicate_label, relation.other_uri, relation.other_label].join('\0'))
    .join('\n');
}

/** Ego graph used by the instance Network tab. Stable for identical payloads. */
export function instanceDomainGraph(
  center: { uri: string; label: string; class_label?: string },
  relations: InstanceRelation[],
) {
  return instanceEgoGraph(center, instanceDomainRelations(relations));
}

/** Current instance plus every neighbour already present on the connections payload. */
export function instanceEgoGraph(
  center: { uri: string; label: string; class_label?: string },
  relations: InstanceRelation[],
) {
  const nodes = new Map<string, GraphNode>();
  const rootId = addNode(nodes, center.uri, center.label, center.class_label || 'Resource', {
    uri: center.uri,
    is_primary: true,
  });
  const edges: GraphEdge[] = [];
  for (const relation of relations) {
    if (!relation.other_uri || relation.other_uri === rootId) continue;
    addNode(nodes, relation.other_uri, relation.other_label, 'Resource', { uri: relation.other_uri });
    const source = relation.role === 'range' ? relation.other_uri : rootId;
    const target = relation.role === 'range' ? rootId : relation.other_uri;
    edges.push({
      id: JSON.stringify([source, relation.predicate_uri, target, relation.role]),
      source,
      target,
      type: relation.predicate_uri,
      label: relation.predicate_label || compactUri(relation.predicate_uri),
    });
  }
  return { rootId, nodes: [...nodes.values()], edges };
}

/** Focused term plus immediate incoming and outgoing ontology connections. */
export function termEgoGraph(term: DictionaryTerm, terms: DictionaryTerm[]) {
  const related = termConnections(term, ontologyConnections(terms));
  const connections = related.incoming.length ? related.incoming : related.outgoing;
  const nodes = new Map<string, GraphNode>();
  const add = (ref: TermRef, primary = false) => {
    const loaded = terms.find(item => item.id === ref.id && (!ref.type || item.type === ref.type));
    return addNode(nodes, termKey(loaded || ref), loaded?.name || ref.name, loaded?.type || ref.type || 'Resource', {
      iri: ref.id,
      term_type: loaded?.type || ref.type,
      is_primary: primary,
    });
  };
  const rootId = add(term, true);
  const edges: GraphEdge[] = connections.map(edge => ({
    id: edge.key,
    source: add(edge.from),
    target: add(edge.to),
    type: edge.label,
    label: edge.label,
    properties: { kind: edge.kind },
  }));
  return { rootId, nodes: [...nodes.values()], edges };
}
