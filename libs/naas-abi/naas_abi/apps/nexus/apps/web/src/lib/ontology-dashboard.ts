import type { DictionaryLink, DictionaryTerm } from './ontology-dictionary-tree';
import type { DictionaryFile } from './ontology-file-filter';
import { termKey } from './ontology-context';
import { dictionaryFilter, dictionaryFilterRoute } from './ontology-navigation';

export const DASHBOARD_KINDS = [
  { type: 'ontology', label: 'Ontology', symbol: 'On', color: '#64748b' },
  { type: 'entity', label: 'Class', symbol: 'Cl', color: '#3b82f6' },
  { type: 'relationship', label: 'Object Property', symbol: 'Op', color: '#16a34a' },
  { type: 'attribute', label: 'Data Property', symbol: 'Dp', color: '#9333ea' },
  { type: 'annotation', label: 'Annotation Property', symbol: 'An', color: '#d97706' },
  { type: 'individual', label: 'Individuals', symbol: 'In', color: '#64748b' },
  { type: 'restriction', label: 'OWL Restriction', symbol: 'Re', color: '#e11d48' },
] as const;
export type DashboardKind = typeof DASHBOARD_KINDS[number]['type'];
/** Kinds that are not dictionary term types: selected with ``dashboardType`` instead of the term filter. */
export const DASHBOARD_PSEUDO_KINDS: readonly DashboardKind[] = ['ontology', 'restriction'];
export const isPseudoKind = (kind: string): kind is 'ontology' | 'restriction' => (DASHBOARD_PSEUDO_KINDS as readonly string[]).includes(kind);
export type DashboardRestriction = {
  key: string; subject: DictionaryTerm; property: { id: string; name: string }; target: DictionaryLink;
  constraint?: string; sources: NonNullable<DictionaryTerm['sources']>;
};
export type DashboardFile = DictionaryFile & { description?: string };
export type DashboardTile = DashboardFile & { symbol: string; index: number; terms: DictionaryTerm[]; failed: boolean };
export type OntologyDeclaration = Pick<DictionaryTerm, 'id' | 'name' | 'sources' | 'metadata'> & { type: 'ontology' };

export const DASHBOARD_METADATA = [
  { key: 'label', label: 'RDFS:label', predicate: 'rdfs:label' },
  { key: 'definition', label: 'SKOS definition', predicate: 'skos:definition' },
  { key: 'example', label: 'SKOS example', predicate: 'skos:example' },
] as const;

/** A declaration in several files counts once; file filters also scope its annotations. */
export function dashboardCoverage(items: Array<DictionaryTerm | OntologyDeclaration>, paths: string[]) {
  const declarations = new Map<string, Array<DictionaryTerm | OntologyDeclaration>>();
  for (const item of items) {
    if (!item.sources?.some(source => paths.includes(source.path))) continue;
    const key = `${item.type}:${item.id}`;
    declarations.set(key, [...(declarations.get(key) || []), item]);
  }
  const total = declarations.size;
  return { total, metrics: DASHBOARD_METADATA.map(field => {
    const present = [...declarations.values()].filter(copies => copies.some(item =>
      item.metadata?.[field.key].some(path => paths.includes(path)))).length;
    return { ...field, present, missing: total - present, ratio: total ? present / total : null };
  }) };
}

export function dashboardOntologies(ontologies: OntologyDeclaration[], paths: string[]) {
  return [...new Map(ontologies.filter(item => item.sources?.some(source => paths.includes(source.path)))
    .map(item => [item.id, item])).values()];
}

/**
 * OWL restrictions stated in the given files, once each. A restriction belongs
 * to the file that states it, which need not declare its class: People restricts
 * abi:Person, declared in ABI.
 */
export function dashboardRestrictions(terms: DictionaryTerm[], paths: string[]): DashboardRestriction[] {
  const found = new Map<string, DashboardRestriction>();
  for (const term of terms) for (const relation of term.relations || []) {
    if (relation.kind !== 'restriction') continue;
    const sources = relation.sources.filter(source => paths.includes(source.path));
    if (!sources.length) continue;
    const key = JSON.stringify([term.id, relation.property.id, relation.target.id, relation.constraint || '']);
    const existing = found.get(key);
    if (existing) { existing.sources = [...new Map([...existing.sources, ...sources].map(source => [source.path, source])).values()]; continue; }
    found.set(key, { key, subject: term, property: relation.property, target: relation.target, constraint: relation.constraint, sources });
  }
  return [...found.values()].sort((a, b) => a.subject.name.localeCompare(b.subject.name)
    || a.property.name.localeCompare(b.property.name) || a.target.name.localeCompare(b.target.name));
}

/** Pseudo kinds (ontology, restriction) toggle ``dashboardType``; other kinds retain the term filter route. */
export function dashboardKindRoute(query: string, type: DashboardKind) {
  const params = new URLSearchParams(query);
  const current = params.get('dashboardType');
  const active = current && isPseudoKind(current) ? current : dictionaryFilter(query);
  const next = dictionaryFilterRoute(query, isPseudoKind(type) || active === type ? 'all' : type);
  next.set('view', 'overview');
  next.delete('dashboardType');
  if (isPseudoKind(type) && active !== type) next.set('dashboardType', type);
  return next;
}

export function ontologySymbol(name: string) {
  const words = name.replace(/\.ttl$/i, '').replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(/[^a-zA-Z0-9]+/).filter(word => word && !['ontology', 'ontologies', 'processes'].includes(word.toLowerCase()));
  if (!words.length) return 'On';
  return words.length === 1 ? words[0].slice(0, 3) : words.slice(0, 3).map(word => word[0]).join('');
}

/** Only inventory files admitted by the workspace can become tiles, including empty files. */
export function buildOntologyDashboard(files: DashboardFile[], terms: DictionaryTerm[], failedPaths: string[] = []) {
  const inventory = [...new Map(files.map(file => [file.path, file])).values()]
    .sort((a, b) => a.moduleName.localeCompare(b.moduleName) || a.name.localeCompare(b.name) || a.path.localeCompare(b.path));
  const failed = new Set(failedPaths);
  const byFile = new Map(inventory.map(file => [file.path, new Map<string, DictionaryTerm>()]));
  for (const term of terms) for (const source of term.sources || []) byFile.get(source.path)?.set(termKey(term), term);
  return inventory.map((file, index): DashboardTile => ({ ...file, index: index + 1, symbol: ontologySymbol(file.name), failed: failed.has(file.path),
    terms: [...byFile.get(file.path)!.values()].sort((a, b) => a.name.localeCompare(b.name) || termKey(a).localeCompare(termKey(b))),
  }));
}

export function dashboardTerms(tiles: DashboardTile[]) {
  return [...new Map(tiles.flatMap(tile => tile.terms).map(term => [termKey(term), term])).values()];
}

/**
 * Tile drill-down changes the dashboard selection and selects that ontology in
 * the sidebar file picker, so both show the same file. Leaving the drill-down
 * clears that selection only while it still mirrors the file: a selection the
 * user changed in the sidebar meanwhile is kept. Other sidebar filters are kept.
 */
export function dashboardRoute(query: string, file?: string) {
  const params = new URLSearchParams(query);
  params.set('view', 'overview');
  params.delete('dashboardType');
  ['term', 'termType', 'system', 'subsystem', 'process'].forEach(key => params.delete(key));
  const previous = params.get('dashboardFile');
  const selected = params.getAll('dictionaryFile');
  if (file) {
    params.set('dashboardFile', file);
    params.delete('dictionaryFile');
    params.append('dictionaryFile', file);
  } else {
    params.delete('dashboardFile');
    if (previous && selected.length === 1 && selected[0] === previous) params.delete('dictionaryFile');
  }
  return params;
}
