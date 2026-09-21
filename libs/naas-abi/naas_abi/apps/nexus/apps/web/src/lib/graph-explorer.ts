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
export interface ExplorerInstanceHit {
  uri: string;
  label: string;
  graph_uri: string;
  class_uri: string;
  class_label: string;
}

export interface ClassInstanceGroup {
  class_uri: string;
  class_label: string;
  instance_count: number;
  instances: ExplorerInstanceHit[];
}

export const EXPLORER_SIDEBAR_INSTANCE_LIMIT = 50;

/** All Graphs (empty selection) or two or more named graphs. One selected graph is never mixed. */
export function explorerScopeHasMultipleGraphs(
  scopeGraphs: readonly string[],
  workspaceGraphCount: number,
): boolean {
  return scopeGraphs.length > 1 || (scopeGraphs.length === 0 && workspaceGraphCount > 1);
}

/** Trailing graph hint only when the current list can actually mix graphs. */
export function explorerShowsGraphHint(
  scopeGraphs: readonly string[],
  workspaceGraphCount: number,
  visibleGraphUris: readonly string[],
): boolean {
  if (!explorerScopeHasMultipleGraphs(scopeGraphs, workspaceGraphCount)) return false;
  const seen = new Set<string>();
  for (const uri of visibleGraphUris) {
    if (uri) seen.add(uri);
  }
  return seen.size > 1;
}

/** Nest search hits as class parents with instance children. Class-only hits stay empty so the sidebar can load members. */
export function groupSearchHitsByClass(
  hits: Array<{
    uri: string;
    label: string;
    kind: 'class' | 'individual';
    class_uri: string;
    class_label: string;
    graph_uri: string;
    instance_count: number;
  }>,
): ClassInstanceGroup[] {
  const groups = new Map<string, ClassInstanceGroup>();
  function group(uri: string, label: string, count = 0): ClassInstanceGroup {
    const existing = groups.get(uri);
    if (existing) {
      if (label && existing.class_label === existing.class_uri) existing.class_label = label;
      if (count) existing.instance_count = count;
      return existing;
    }
    const created: ClassInstanceGroup = {
      class_uri: uri,
      class_label: label || uri,
      instance_count: count,
      instances: [],
    };
    groups.set(uri, created);
    return created;
  }
  for (const hit of hits) {
    if (hit.kind === 'class') {
      group(hit.uri, hit.class_label || hit.label, hit.instance_count);
      continue;
    }
    const parent = group(hit.class_uri || hit.uri, hit.class_label || hit.class_uri || hit.label);
    parent.instances.push({
      uri: hit.uri,
      label: hit.label,
      graph_uri: hit.graph_uri,
      class_uri: hit.class_uri,
      class_label: hit.class_label,
    });
  }
  for (const item of groups.values()) {
    item.instances.sort((a, b) => a.label.localeCompare(b.label) || a.uri.localeCompare(b.uri));
  }
  return [...groups.values()].sort(
    (a, b) => a.class_label.localeCompare(b.class_label) || a.class_uri.localeCompare(b.class_uri),
  );
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
