import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
import { BFO_BUCKET_BY_URI } from './bfo-buckets';
import { classProperties } from './ontology-class-properties';
import { ontologyConnections, termKey, type TermRef, type TermConnection } from './ontology-context';
import { dictionaryKindLabel, type DictionaryTerm } from './ontology-dictionary-tree';

export type TermGraph = { rootId: string; nodes: GraphNode[]; edges: GraphEdge[] };
export type TermGraphRelations = { hierarchy: boolean; restrictions: boolean; properties: boolean };

/** Adapt the permitted dictionary declarations to the existing network canvas. */
export function buildTermGraph(term: DictionaryTerm, terms: DictionaryTerm[]): TermGraph {
  const byKey = new Map(terms.map(item => [termKey(item), item]));
  const byId = new Map<string, DictionaryTerm[]>();
  terms.forEach(item => byId.set(item.id, [...(byId.get(item.id) || []), item]));
  const resolve = (ref: TermRef, type?: DictionaryTerm['type']): TermRef => {
    const matches = byId.get(ref.id) || [];
    const match = type ? matches.find(item => item.type === type) : matches.length === 1 ? matches[0] : undefined;
    return match ? { id: match.id, name: match.name, type: match.type } : { ...ref, type: type || ref.type };
  };

  // Classify through all named parents, even when those ancestors are not drawn.
  // A generic Entity parent must not mask a more specific bucket on another branch.
  function bucket(ref: TermRef): string | undefined {
    const queue = [ref]; const seen = new Set<string>(); let entity: string | undefined;
    for (let i = 0; i < queue.length; i++) {
      const current = queue[i]; const key = termKey(current);
      if (seen.has(key)) continue;
      seen.add(key);
      const definition = BFO_BUCKET_BY_URI[current.id];
      if (definition && definition.type !== 'Entity') return definition.uri;
      if (definition) entity = definition.uri;
      const loaded = byKey.get(key);
      if (loaded?.type !== 'entity' && loaded?.type !== 'individual') continue;
      for (const equivalent of loaded.equivalents || []) queue.push(resolve(equivalent, 'entity'));
      for (const parent of loaded.parents || []) queue.push(resolve(parent, 'entity'));
    }
    return entity;
  }

  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();
  function addNode(ref: TermRef): string {
    const key = termKey(ref);
    if (!nodes.has(key)) {
      const loaded = byKey.get(key);
      const bfo = bucket(ref);
      nodes.set(key, {
        id: key, label: loaded?.name || ref.name,
        type: bfo ? BFO_BUCKET_BY_URI[bfo].type : 'Unknown',
        properties: {
          iri: ref.id, term_type: ref.type, kind: ref.type ? dictionaryKindLabel(ref.type) : 'Referenced term',
          definition: loaded?.description || '', bfo_parent_iri: bfo,
          source_files: loaded?.sources || [], is_primary: key === termKey(term),
        },
      });
    }
    return key;
  }
  function addEdge(from: TermRef, to: TermRef, label: string, category: string, sources: TermConnection['sources'], extra: Record<string, unknown> = {}) {
    const source = addNode(from); const target = addNode(to);
    // Keep cyclic declarations labelled, without feeding a cycle to the tree layout.
    if (category === 'is_a') {
      const ancestors = [target]; const seen = new Set<string>();
      for (let i = 0; i < ancestors.length; i++) {
        const id = ancestors[i];
        if (id === source) { category = 'hierarchy'; break; }
        if (seen.has(id)) continue;
        seen.add(id);
        for (const edge of edges.values()) if (edge.source === id && edge.properties?.relation_kind === 'is_a') ancestors.push(edge.target);
      }
    }
    const id = JSON.stringify([source, target, label, category, extra.property_iri]);
    const existing = edges.get(id);
    if (existing) {
      const previous = existing.properties?.source_files as TermConnection['sources'];
      existing.properties!.source_files = [...new Map([...previous, ...sources].map(file => [file.path, file])).values()];
      return;
    }
    edges.set(id, { id, source, target, type: label, label, properties: { relation_kind: category, source_files: sources, ...extra } });
  }

  const connections = ontologyConnections(terms);
  const rootId = addNode(term);
  const rootAncestry = new Set([rootId]);
  const pending: TermRef[] = [term];
  for (let i = 0; i < pending.length; i++) {
    const current = pending[i]; const loaded = byKey.get(termKey(current));
    for (const parent of loaded?.parents || []) {
      const ref = resolve(parent, loaded?.type === 'individual' ? 'entity' : loaded?.type);
      if (rootAncestry.has(termKey(ref))) continue;
      rootAncestry.add(termKey(ref)); pending.push(ref);
    }
  }

  for (const edge of connections) {
    const from = termKey(edge.from); const to = termKey(edge.to);
    const inherited = term.type === 'entity' && from !== rootId && rootAncestry.has(from);
    const hierarchy = ['subclass of', 'subproperty of', 'instance of'].includes(edge.label);
    if (hierarchy && (rootAncestry.has(from) || to === rootId)) {
      // Only class subsumption gets the canvas's dashed, unlabelled is_a styling.
      addEdge(edge.from, edge.to, edge.label, edge.label === 'subclass of' ? 'is_a' : 'hierarchy', edge.sources);
      continue;
    }
    if (from !== rootId && to !== rootId && !(inherited && edge.kind === 'restriction')) continue;
    // Properties label their target edges, rather than duplicating "uses property" nodes.
    if (edge.kind !== 'schema' && !edge.property && to !== rootId) continue;
    // Domain declarations for a selected class are projected with their ranges below.
    if (term.type === 'entity' && to === rootId && edge.label === 'has domain') continue;
    const category = edge.kind === 'restriction' ? 'restriction' : 'object_property';
    addEdge(inherited ? term : edge.from, edge.to, edge.label + (inherited ? ' · inherited' : ''), category, edge.sources, {
      property_iri: edge.property?.id, declared_on: inherited ? edge.from.name : undefined,
      declaration: edge.kind,
    });
  }

  for (const { property, declaredOn } of classProperties(term, terms)) {
    const sources = declaredOn.flatMap(domain => domain.sources || []);
    const inherited = !declaredOn.some(domain => domain.id === term.id);
    if (!property.range?.length) {
      addEdge(inherited ? term : property, inherited ? property : term, inherited ? 'inherits property' : 'has domain', 'object_property', sources, { property_iri: property.id, declaration: 'domain', declared_on: declaredOn.map(domain => domain.name).join(', ') });
    }
    for (const range of property.range || []) {
      addEdge(term, resolve(range, property.type === 'relationship' ? 'entity' : undefined), property.name + (inherited ? ' · inherited' : ''), 'object_property', [...sources, ...(range.sources || [])], {
        property_iri: property.id, declaration: 'domain / range', declared_on: declaredOn.map(domain => domain.name).join(', '),
      });
    }
  }
  return { rootId, nodes: [...nodes.values()], edges: [...edges.values()] };
}

/** Hide disconnected neighbours when relation controls change; always retain the selected term. */
export function filterTermGraph(graph: TermGraph, relations: TermGraphRelations, buckets = new Set<string>(), hidden = new Set<string>()): TermGraph {
  const candidates = graph.edges.filter(edge => {
    const kind = edge.properties?.relation_kind;
    return kind === 'is_a' || kind === 'hierarchy' ? relations.hierarchy : kind === 'restriction' ? relations.restrictions : relations.properties;
  });
  const reachable = new Set([graph.rootId]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const edge of candidates) {
      if (reachable.has(edge.source) === reachable.has(edge.target)) continue;
      reachable.add(edge.source); reachable.add(edge.target); changed = true;
    }
  }
  const nodes = graph.nodes.filter(node => reachable.has(node.id) && (node.id === graph.rootId || ((!buckets.size || buckets.has(node.type)) && !hidden.has(node.id))));
  const visible = new Set(nodes.map(node => node.id));
  return { rootId: graph.rootId, nodes, edges: candidates.filter(edge => visible.has(edge.source) && visible.has(edge.target)) };
}
