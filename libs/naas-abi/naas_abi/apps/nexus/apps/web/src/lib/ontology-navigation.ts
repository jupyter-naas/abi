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
export function dictionaryFilter(current: string): DictionaryTerm['type'] | 'all' {
  const params = new URLSearchParams(current);
  const filter = params.get('termFilter');
  if (filter === 'all') return 'all';
  if (filter && Object.prototype.hasOwnProperty.call(termViews, filter)) return filter as DictionaryTerm['type'];
  return kindForView(params.get('view') || '') || 'all';
}
export function dictionaryFilterRoute(current: string, filter: DictionaryTerm['type'] | 'all') {
  const params = new URLSearchParams(current);
  params.set('termFilter', filter);
  if (filter !== 'all' && params.get('termType') !== filter) {
    params.delete('term'); params.delete('termType');
  }
  if (kindForView(params.get('view') || '') && filter !== 'all') params.set('view', termViews[filter]);
  return params;
}
export function termRoute(current: string, term: Pick<DictionaryTerm, 'id' | 'type'>) {
  const params = new URLSearchParams(current);
  ['system', 'subsystem', 'process'].forEach(key => params.delete(key));
  params.set('term', term.id); params.set('termType', term.type);
  params.set('view', termViews[term.type]);
  // A linked term must remain visible when it belongs to a different kind.
  if (params.has('termFilter') && params.get('termFilter') !== 'all') params.set('termFilter', term.type);
  return params;
}
export function viewRoute(current: string, view: string) {
  if (view === 'system') return systemRoute(current);
  const params = new URLSearchParams(current);
  const filter = dictionaryFilter(current);
  const canvasView = ['details', 'network', 'overview'].includes(view);
  if (view === 'details') {
    const selectedKind = params.get('termType');
    const selectedView = selectedKind && Object.prototype.hasOwnProperty.call(termViews, selectedKind) ? termViews[selectedKind as DictionaryTerm['type']] : undefined;
    view = selectedView || (filter === 'all' ? 'classes' : termViews[filter]);
  }
  params.set('view', view);
  const kind = kindForView(view);
  if (ontologyBrowser(current) === 'dictionary') params.set('termFilter', !canvasView && kind ? kind : filter);
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
  if (!params.get('view')) params.set('view', browser === 'files' ? 'network' : 'classes');
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
