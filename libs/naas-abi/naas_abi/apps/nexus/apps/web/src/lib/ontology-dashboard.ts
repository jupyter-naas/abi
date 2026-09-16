import type { DictionaryTerm } from './ontology-dictionary-tree';
import type { DictionaryFile } from './ontology-file-filter';
import { termKey } from './ontology-context';

export const DASHBOARD_KINDS = [
  { type: 'entity', label: 'Classes', symbol: 'Cl', color: '#3b82f6' },
  { type: 'relationship', label: 'Object properties', symbol: 'Op', color: '#16a34a' },
  { type: 'attribute', label: 'Data properties', symbol: 'Dp', color: '#9333ea' },
  { type: 'annotation', label: 'Annotations', symbol: 'An', color: '#d97706' },
  { type: 'individual', label: 'Individuals', symbol: 'In', color: '#64748b' },
] as const;
export type DashboardFile = DictionaryFile & { description?: string };
export type DashboardTile = DashboardFile & { symbol: string; index: number; terms: DictionaryTerm[]; failed: boolean };

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
  ['term', 'termType', 'system', 'subsystem', 'process'].forEach(key => params.delete(key));
  if (file) params.set('dashboardFile', file); else params.delete('dashboardFile');
  return params;
}
