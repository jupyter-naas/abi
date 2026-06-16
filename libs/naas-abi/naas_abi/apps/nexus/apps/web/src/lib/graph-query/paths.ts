// Pure URL/path builders for the Explore APIs. Kept free of any `authFetch`/store import
// so they can be unit-tested in a plain node environment.

export const GRAPH_BASE = '/api/graph'
export const VIEW_BASE = '/api/view'

export interface ColumnsParams {
  workspaceId: string
  graphUris: string[]
  classUris: string[]
}

/** GET /api/graph/columns — repeated graph_uri / class_uri params. */
export function buildColumnsPath(params: ColumnsParams): string {
  const qs = new URLSearchParams()
  qs.set('workspace_id', params.workspaceId)
  for (const g of params.graphUris) qs.append('graph_uri', g)
  for (const c of params.classUris) qs.append('class_uri', c)
  return `${GRAPH_BASE}/columns?${qs.toString()}`
}

export interface ListViewsParams {
  workspaceId: string
  path?: string
  recursive?: boolean
}

/** GET /api/view/list — folder-scoped listing. */
export function buildListViewsPath(params: ListViewsParams): string {
  const qs = new URLSearchParams()
  qs.set('workspace_id', params.workspaceId)
  if (params.path !== undefined) qs.set('path', params.path)
  if (params.recursive) qs.set('recursive', 'true')
  return `${VIEW_BASE}/list?${qs.toString()}`
}

export function viewPath(viewId: string, workspaceId?: string): string {
  const base = `${VIEW_BASE}/${encodeURIComponent(viewId)}`
  if (!workspaceId) return base
  return `${base}?${new URLSearchParams({ workspace_id: workspaceId }).toString()}`
}

export function foldersPath(workspaceId: string): string {
  return `${VIEW_BASE}/folders?${new URLSearchParams({ workspace_id: workspaceId }).toString()}`
}
