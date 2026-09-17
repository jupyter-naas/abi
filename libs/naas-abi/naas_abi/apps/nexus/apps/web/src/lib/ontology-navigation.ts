import type { DictionaryTerm } from './ontology-dictionary-tree';

export const termViews = {
  entity: 'classes', relationship: 'relations', attribute: 'attributes',
  annotation: 'annotations', individual: 'individuals',
} as const;
export const termTabs = [
  ['classes', 'Classes'], ['relations', 'Object Properties'],
  ['attributes', 'Data Properties'], ['annotations', 'Annotations'], ['individuals', 'Individuals'],
] as const;
export function kindForView(view: string) {
  return (Object.keys(termViews) as DictionaryTerm['type'][]).find(kind => termViews[kind] === view);
}
/** Repeated termFilter values accumulate; an empty selection means all types. */
export function dictionaryFilters(current: string): DictionaryTerm['type'][] {
  const params = new URLSearchParams(current);
  const filters = params.getAll('termFilter');
  if (filters.includes('all')) return [];
  const selected = [...new Set(filters.filter((filter): filter is DictionaryTerm['type'] => Object.prototype.hasOwnProperty.call(termViews, filter)))];
  if (selected.length) return selected;
  const inferred = kindForView(params.get('view') || '');
  return inferred ? [inferred] : [];
}
export function dictionaryFilter(current: string): DictionaryTerm['type'] | 'all' {
  const filters = dictionaryFilters(current);
  return filters.length === 1 ? filters[0] : 'all';
}
function writeDictionaryFilters(params: URLSearchParams, filters: DictionaryTerm['type'][]) {
  params.delete('termFilter');
  if (!filters.length) params.set('termFilter', 'all');
  else [...new Set(filters)].forEach(filter => params.append('termFilter', filter));
}
export function dictionaryFiltersRoute(current: string, filters: DictionaryTerm['type'][]) {
  const params = new URLSearchParams(current);
  const selected = [...new Set(filters)].filter(filter => Object.prototype.hasOwnProperty.call(termViews, filter));
  writeDictionaryFilters(params, selected);
  params.delete('dashboardType');
  if (selected.length && !selected.includes(params.get('termType') as DictionaryTerm['type'])) {
    params.delete('term'); params.delete('termType');
    if (kindForView(params.get('view') || '')) params.set('view', termViews[selected[0]]);
  }
  return params;
}
export function dictionaryFilterRoute(current: string, filter: DictionaryTerm['type'] | 'all') {
  return dictionaryFiltersRoute(current, filter === 'all' ? [] : [filter]);
}
export function termRoute(current: string, term: Pick<DictionaryTerm, 'id' | 'type'>) {
  const params = new URLSearchParams(current);
  ['system', 'subsystem', 'process'].forEach(key => params.delete(key));
  params.set('term', term.id); params.set('termType', term.type);
  params.set('view', termViews[term.type]);
  // Following a linked type expands the selection without discarding checked types.
  const filters = dictionaryFilters(current);
  if (params.has('termFilter') && filters.length && !filters.includes(term.type)) writeDictionaryFilters(params, [...filters, term.type]);
  return params;
}
export function viewRoute(current: string, view: string) {
  if (view === 'system') return systemRoute(current);
  const params = new URLSearchParams(current);
  const filters = dictionaryFilters(current);
  const canvasView = ['details', 'network', 'overview'].includes(view);
  if (view === 'details') {
    const selectedKind = params.get('termType');
    const selectedView = selectedKind && Object.prototype.hasOwnProperty.call(termViews, selectedKind) ? termViews[selectedKind as DictionaryTerm['type']] : undefined;
    view = selectedView || (filters.length ? termViews[filters[0]] : 'classes');
  }
  params.set('view', view);
  const kind = kindForView(view);
  if (ontologyBrowser(current) === 'dictionary') writeDictionaryFilters(params, !canvasView && kind ? [kind] : filters);
  if (kind && params.get('termType') !== kind) {
    params.delete('term'); params.delete('termType');
  }
  return params;
}
export function browserRoute(current: string, mode: string) {
  const params = new URLSearchParams(current);
  params.set('browser', mode);
  if (mode === 'files' && params.get('view') === 'system') {
    params.set('view', 'network');
    ['system', 'subsystem', 'process'].forEach(key => params.delete(key));
  }
  // Keep the selected file in the URL; only Files mode uses it as a scope.
  return params;
}

/** Missing sidebar mode means Dictionary; Files is always an explicit choice. */
export function ontologyBrowser(current: string): 'dictionary' | 'files' {
  return new URLSearchParams(current).get('browser') === 'files' ? 'files' : 'dictionary';
}

export function normalizeOntologyRoute(current: string): URLSearchParams {
  const params = new URLSearchParams(current);
  const browser = ontologyBrowser(current);
  params.set('browser', browser);
  if (!params.get('view')) params.set('view', browser === 'files' ? 'network' : 'overview');
  return params;
}

/** Store navigation only, separately for each workspace and browser tab. */
export function rememberOntologyRoute(workspaceId: string, current: string): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(`ontology-route:${workspaceId}`, normalizeOntologyRoute(current).toString());
  } catch { /* Navigation still works when browser storage is unavailable. */ }
}

export function lastOntologyRoute(workspaceId: string | null): URLSearchParams {
  let saved = '';
  if (workspaceId && typeof window !== 'undefined') {
    try { saved = window.sessionStorage.getItem(`ontology-route:${workspaceId}`) || ''; } catch { /* Use the default. */ }
  }
  return normalizeOntologyRoute(saved);
}

/** System navigation preserves file scope and the user's dictionary type filter. */
export function systemRoute(current: string, systemId?: string, subsystemId?: string, processId?: string) {
  const params = new URLSearchParams(current);
  params.set('browser', 'dictionary'); params.set('view', 'system');
  ['term', 'termType', 'subsystem', 'process'].forEach(key => params.delete(key));
  if (systemId) params.set('system', systemId); else params.delete('system');
  if (subsystemId) params.set('subsystem', subsystemId);
  if (processId) params.set('process', processId);
  return params;
}
