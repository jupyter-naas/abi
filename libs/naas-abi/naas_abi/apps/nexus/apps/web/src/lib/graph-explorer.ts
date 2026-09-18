import type { DictionaryTerm } from './ontology-dictionary-tree';

export interface ExplorerGraph {
  id: string;
  uri: string;
  label: string;
  role_label: string;
  can_write?: boolean;
}
export interface ExplorerClass {
  uri: string;
  label: string;
  count: number;
  parents: string[];
}
export interface ExplorerKpis {
  instances: number;
  named_individuals: number;
  triples: number;
  classes: number;
  predicates: number;
  relations: number;
  literal_values: number;
  labeled_instances: number;
}
export interface ExplorerOverview {
  permissions?: { can_create_graph: boolean };
  graphs: ExplorerGraph[];
  selected_graphs: string[];
  kpis: ExplorerKpis;
  graph_metrics: Array<ExplorerGraph & ExplorerKpis>;
  classes: ExplorerClass[];
}
export type ExplorerCatalog = Pick<ExplorerOverview, 'permissions' | 'graphs' | 'selected_graphs' | 'classes'>;

export function graphMode(path: string): 'explorer' | 'composer' {
  return /\/graph\/(composer|explore-next|explore)(?:\/|$)/.test(path) ? 'composer' : 'explorer';
}
export type ExplorerView = 'instances' | 'network' | 'details';
export function explorerScope(query: string) {
  const p = new URLSearchParams(query);
  const view: ExplorerView = p.get('view') === 'network' ? 'network' : p.get('view') === 'details' ? 'details' : 'instances';
  return {
    view,
    graphs: [...new Set(p.getAll('graph'))].sort(),
    classes: [...new Set(p.getAll('classFilter'))].sort(),
    activeClass: p.get('class') || '',
    hierarchy: p.get('list') === 'hierarchy',
    dashboard: !['instances', 'network', 'details'].includes(p.get('view') || '') && !p.get('class') && !p.has('classFilter'),
  };
}
export function explorerQuery(query: string, changes: Record<string, string | string[] | null>) {
  const p = new URLSearchParams(query);
  for (const [key, value] of Object.entries(changes)) {
    p.delete(key);
    for (const entry of Array.isArray(value) ? value : value === null ? [] : [value])
      if (entry) p.append(key, entry);
  }
  return p.toString();
}
export function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}
export function classTerms(classes: ExplorerClass[]): DictionaryTerm[] {
  const names = new Map(classes.map((item) => [item.uri, item.label]));
  return classes.map((item) => ({
    id: item.uri,
    name: item.label,
    type: 'entity',
    parents: item.parents.map((id) => ({ id, name: names.get(id) || id })),
  }));
}
export function groupComposerViews<
  T extends { path?: string | null; name?: string | null; label: string },
>(views: T[]) {
  const groups = new Map<string, T[]>();
  for (const view of views) {
    const path = view.path || '';
    groups.set(path, [...(groups.get(path) || []), view]);
  }
  return [...groups]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, items]) => ({
      path,
      views: items.sort((a, b) => (a.name || a.label).localeCompare(b.name || b.label)),
    }));
}
