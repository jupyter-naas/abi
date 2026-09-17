import type { DictionaryTerm } from './ontology-dictionary-tree';
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
] as const;
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

/** Ontology tiles open their existing file view; other kinds retain the term filter route. */
export function dashboardKindRoute(query: string, type: typeof DASHBOARD_KINDS[number]['type']) {
  const params = new URLSearchParams(query);
  const active = params.get('dashboardType') === 'ontology' ? 'ontology' : dictionaryFilter(query);
  const next = dictionaryFilterRoute(query, type === 'ontology' || active === type ? 'all' : type);
  next.set('view', 'overview');
  next.delete('dashboardType');
  if (type === 'ontology' && active !== type) next.set('dashboardType', 'ontology');
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

/** Tile drill-down changes the dashboard selection, preserving accumulated sidebar filters. */
export function dashboardRoute(query: string, file?: string) {
  const params = new URLSearchParams(query);
  params.set('view', 'overview');
  params.delete('dashboardType');
  ['term', 'termType', 'system', 'subsystem', 'process'].forEach(key => params.delete(key));
  if (file) params.set('dashboardFile', file); else params.delete('dashboardFile');
  return params;
}
