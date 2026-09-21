export const INSTANCE_PAGE_SIZE = 25;

export function instancePageRequest(workspaceId: string, graphUri: string, classUri: string, page: number, search: string) {
  return {
    workspace_id: workspaceId,
    graph_uri: graphUri,
    // A single class keeps pagination at one row per distinct instance.
    class_uris: [classUri],
    property_uris: ['http://www.w3.org/2000/01/rdf-schema#label'],
    search: search.trim(),
    limit: INSTANCE_PAGE_SIZE + 1,
    offset: Math.max(0, Math.trunc(page)) * INSTANCE_PAGE_SIZE,
    enrich: false,
  };
}

export function instancePage<T>(rows: T[]) {
  return { rows: rows.slice(0, INSTANCE_PAGE_SIZE), hasMore: rows.length > INSTANCE_PAGE_SIZE };
}

export function individualHref(workspaceId: string, graphUri: string, classUri: string, instanceUri?: string) {
  const query = new URLSearchParams({ graph: graphUri });
  if (classUri) query.set('class', classUri);
  if (instanceUri) query.set('selected', instanceUri);
  return `/workspace/${encodeURIComponent(workspaceId)}/graph/individuals?${query}`;
}

/** Instance page tabs match Ontology/Explorer: Details is the default, Network is `?view=network`. */
export function instancePageView(query: string): 'details' | 'network' {
  return new URLSearchParams(query).get('view') === 'network' ? 'network' : 'details';
}

export function classDefinitionHref(workspaceId: string, classUri: string) {
  const query = new URLSearchParams({ browser: 'dictionary', view: 'classes', term: classUri, termType: 'entity' });
  return `/workspace/${encodeURIComponent(workspaceId)}/ontology?${query}`;
}
