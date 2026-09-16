import type { DictionaryTerm } from './ontology-dictionary-tree';

/** Show explicit named domains, preserving their declarations rather than implying required fields. */
export function classProperties(term: DictionaryTerm, terms: DictionaryTerm[]) {
  if (term.type !== 'entity') return [];
  const classes = new Map(terms.filter(item => item.type === 'entity').map(item => [item.id, item]));
  const ancestry = new Map<string, string>([[term.id, term.name]]);
  const pending = [term.id];
  while (pending.length) {
    const id = pending.pop()!;
    for (const parent of classes.get(id)?.parents || []) {
      if (ancestry.has(parent.id)) continue;
      ancestry.set(parent.id, parent.name);
      pending.push(parent.id);
    }
  }
  return terms.filter(item => item.type === 'relationship' || item.type === 'attribute')
    .map(property => ({property, declaredOn: (property.domain || []).filter(domain => ancestry.has(domain.id))}))
    .filter(entry => entry.declaredOn.length > 0)
    .sort((a, b) => a.property.name.localeCompare(b.property.name));
}
