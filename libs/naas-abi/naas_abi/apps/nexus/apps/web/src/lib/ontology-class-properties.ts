import type { DictionaryLink, DictionaryTerm } from './ontology-dictionary-tree';
import { propertyPriority } from './instance-property-order';

/** The class and every ancestor the dictionary knows, by IRI, with their names. */
function classAncestry(term: DictionaryTerm, terms: DictionaryTerm[]) {
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
  return ancestry;
}

/** Show explicit named domains, preserving their declarations rather than implying required fields. */
export function classProperties(term: DictionaryTerm, terms: DictionaryTerm[]) {
  if (term.type !== 'entity') return [];
  const ancestry = classAncestry(term, terms);
  return terms.filter(item => item.type === 'relationship' || item.type === 'attribute')
    .map(property => ({property, declaredOn: (property.domain || []).filter(domain => ancestry.has(domain.id))}))
    .filter(entry => entry.declaredOn.length > 0)
    .sort((a, b) => {
      const rank =
        propertyPriority(a.property.id, a.property.name) -
        propertyPriority(b.property.id, b.property.name);
      if (rank !== 0) return rank;
      return a.property.name.localeCompare(b.property.name);
    });
}

export type ClassRestriction = {
  key: string;
  property: { id: string; name: string };
  constraint?: string;
  target: DictionaryLink;
  declaredOn: { id: string; name: string };
  sources: NonNullable<DictionaryTerm['sources']>;
};

/** owl:Restriction statements on the class and inherited from its ancestors, the class's own first. */
export function classRestrictions(term: DictionaryTerm, terms: DictionaryTerm[]): ClassRestriction[] {
  if (term.type !== 'entity') return [];
  const ancestry = [...classAncestry(term, terms)];
  const byId = new Map(terms.filter(item => item.type === 'entity').map(item => [item.id, item]));
  const found = new Map<string, ClassRestriction>();
  ancestry.forEach(([id, name]) => {
    const owner = id === term.id ? term : byId.get(id);
    for (const relation of owner?.relations || []) {
      if (relation.kind !== 'restriction') continue;
      const key = JSON.stringify([id, relation.property.id, relation.constraint || '', relation.target.id]);
      if (!found.has(key)) found.set(key, { key, property: relation.property, constraint: relation.constraint, target: relation.target, declaredOn: { id, name }, sources: relation.sources });
    }
  });
  const depth = new Map(ancestry.map(([id], index) => [id, id === term.id ? 0 : 1 + index]));
  return [...found.values()].sort((a, b) => (depth.get(a.declaredOn.id)! - depth.get(b.declaredOn.id)!)
    || a.property.name.localeCompare(b.property.name) || a.target.name.localeCompare(b.target.name));
}
