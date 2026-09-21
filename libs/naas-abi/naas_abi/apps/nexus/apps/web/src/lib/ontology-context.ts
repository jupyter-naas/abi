import type { DictionaryTerm } from './ontology-dictionary-tree';

export type TermRef = { id: string; name: string; type?: DictionaryTerm['type'] };
export type TermConnection = {
  key: string; from: TermRef; to: TermRef; label: string;
  kind: 'schema' | 'assertion' | 'restriction';
  property?: TermRef; sources: NonNullable<DictionaryTerm['sources']>;
};
export const termKey = (term: TermRef) => `${term.type || 'reference'}:${term.id}`;
export function ontologyConnections(terms: DictionaryTerm[]): TermConnection[] {
  const byId = new Map<string, DictionaryTerm[]>();
  terms.forEach(term => byId.set(term.id, [...(byId.get(term.id) || []), term]));
  const resolve = (ref: TermRef, kind?: DictionaryTerm['type']): TermRef => {
    const found = byId.get(ref.id) || [];
    const match = kind ? found.find(term => term.type === kind) : found.length === 1 ? found[0] : undefined;
    return match ? {id: match.id, name: match.name, type: match.type} : ref;
  };
  const edges = new Map<string, TermConnection>();
  for (const term of terms) {
    const from = {id: term.id, name: term.name, type: term.type};
    function add(to: TermRef, label: string, kind: TermConnection['kind'] = 'schema', property?: TermRef, sources = term.sources || []) {
      const key = JSON.stringify([termKey(from), termKey(to), label, kind, property?.id]);
      const existing = edges.get(key);
      if (existing) existing.sources = [...new Map([...existing.sources, ...sources].map(source => [source.path, source])).values()];
      else edges.set(key, {key, from, to, label, kind, property, sources});
    }
    for (const parent of term.parents || []) add(resolve(parent, term.type === 'individual' ? 'entity' : term.type), term.type === 'entity' ? 'subclass of' : term.type === 'individual' ? 'instance of' : 'subproperty of', 'schema', undefined, parent.sources || []);
    for (const domain of term.domain || []) add(resolve(domain, 'entity'), 'has domain', 'schema', undefined, domain.sources || []);
    for (const range of term.range || []) add(resolve(range, term.type === 'relationship' ? 'entity' : undefined), 'has range', 'schema', undefined, range.sources || []);
    for (const inverse of term.inverse || []) add(resolve(inverse, 'relationship'), 'inverse of', 'schema', undefined, inverse.sources || []);
    for (const relation of term.relations || []) {
      const targetKind = relation.kind === 'restriction' && relation.constraint !== 'value' ? 'entity' : undefined;
      add(resolve(relation.property, 'relationship'), relation.kind === 'restriction' ? 'uses property in restriction' : 'uses property', relation.kind, undefined, relation.sources);
      const qualifier = relation.constraint ? ` (${relation.constraint})` : '';
      add(resolve(relation.target, targetKind), relation.property.name + qualifier, relation.kind, resolve(relation.property, 'relationship'), relation.sources);
    }
  }
  return [...edges.values()].sort((a, b) => a.from.name.localeCompare(b.from.name) || a.label.localeCompare(b.label) || a.to.name.localeCompare(b.to.name));
}
export function termConnections(term: TermRef, connections: TermConnection[]) {
  const key = termKey(term);
  return {
    incoming: connections.filter(edge => termKey(edge.to) === key),
    outgoing: connections.filter(edge => termKey(edge.from) === key),
  };
}
export function isProcessTerm(ref: TermRef, terms: DictionaryTerm[]): boolean {
  if (ref.type !== 'entity') return false;
  const byId = new Map(terms.filter(term => term.type === 'entity').map(term => [term.id, term]));
  const pending = [ref.id]; const seen = new Set<string>();
  while (pending.length) {
    const id = pending.pop()!;
    if (id === 'http://purl.obolibrary.org/obo/BFO_0000015') return true;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const parent of byId.get(id)?.parents || []) pending.push(parent.id);
  }
  return false;
}
