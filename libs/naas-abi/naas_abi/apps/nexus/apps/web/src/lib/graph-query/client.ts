// Typed client for the Explore query + views APIs.
//
// The URL/body builders are pure and unit-tested; the thin fetch wrappers go through
// `authFetch` (auth + 401-refresh) and are covered by the Playwright e2e suite.

import { authFetch } from '@/stores/auth'
import {
  buildColumnsPath,
  buildListViewsPath,
  foldersPath,
  GRAPH_BASE,
  VIEW_BASE,
  viewPath,
  type ColumnsParams,
  type ListViewsParams,
} from './paths'
import type {
  GraphColumnsResponse,
  GraphFacetsRequest,
  GraphFacetsResponse,
  GraphQueryRequest,
  GraphQueryResponse,
  ListSpec,
  ViewQuerySpec,
} from './types'

export { buildColumnsPath, buildListViewsPath } from './paths'
export type { ColumnsParams, ListViewsParams } from './paths'

export class GraphApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`)
    this.name = 'GraphApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseError(res: Response): Promise<GraphApiError> {
  let detail = res.statusText
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body?.detail === 'string') detail = body.detail
    else if (body?.detail != null) detail = JSON.stringify(body.detail)
  } catch {
    /* non-JSON error body */
  }
  return new GraphApiError(res.status, detail)
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await authFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as T
}

async function getJson<T>(path: string): Promise<T> {
  const res = await authFetch(path)
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as T
}

// ── Query endpoints ──────────────────────────────────────────────────────────────

export interface RunQueryOptions {
  cursor?: string | null
  limit?: number | null
  includeSparql?: boolean
  forceCountRefresh?: boolean
}

export function runQuery(
  workspaceId: string,
  spec: ViewQuerySpec,
  opts: RunQueryOptions = {},
): Promise<GraphQueryResponse> {
  const body: GraphQueryRequest = {
    workspace_id: workspaceId,
    spec,
    cursor: opts.cursor ?? null,
    limit: opts.limit ?? null,
    include_sparql: opts.includeSparql ?? false,
    force_count_refresh: opts.forceCountRefresh ?? false,
  }
  return postJson<GraphQueryResponse>(`${GRAPH_BASE}/query`, body)
}

export interface FacetsOptions {
  search?: string
  limit?: number
}

export function fetchFacets(
  workspaceId: string,
  spec: ListSpec,
  targetColumnId: string,
  opts: FacetsOptions = {},
): Promise<GraphFacetsResponse> {
  const body: GraphFacetsRequest = {
    workspace_id: workspaceId,
    spec,
    target_column_id: targetColumnId,
    search: opts.search ?? '',
    limit: opts.limit ?? 50,
  }
  return postJson<GraphFacetsResponse>(`${GRAPH_BASE}/query/facets`, body)
}

export function fetchColumns(params: ColumnsParams): Promise<GraphColumnsResponse> {
  return getJson<GraphColumnsResponse>(buildColumnsPath(params))
}

// ── Entity search (google-like) ────────────────────────────────────────────────────

export interface SearchHit {
  uri: string
  label: string
  kind: 'class' | 'individual'
  /** Individual: its rdf:type class; Class: same as `uri`. */
  class_uri: string
  class_label: string
  /** A data graph that contains this hit (set the grain's graph from this). */
  graph_uri: string
  /** Class hits: instances of the class in that graph; individuals: 0. */
  instance_count: number
}

export interface GraphSearchResponse {
  query: string
  results: SearchHit[]
}

export interface SearchEntitiesParams {
  workspaceId: string
  query: string
  /** Optional: restrict to these graphs. Omit to search all graphs the workspace owns. */
  graphUris?: string[]
  limit?: number
}

/** GET /api/graph/search — free-text search returning mixed class + individual hits. */
export function searchEntities(params: SearchEntitiesParams): Promise<GraphSearchResponse> {
  const qs = new URLSearchParams()
  qs.set('workspace_id', params.workspaceId)
  qs.set('q', params.query)
  for (const g of params.graphUris ?? []) qs.append('graph_uri', g)
  if (params.limit != null) qs.set('limit', String(params.limit))
  return getJson<GraphSearchResponse>(`${GRAPH_BASE}/search?${qs.toString()}`)
}

// ── Instance detail (for the inspect drawer) ───────────────────────────────────────

export interface InstanceDataProperty {
  predicate_uri: string
  predicate_label: string
  value: string
}
export interface InstanceRelation {
  role: 'domain' | 'range'
  predicate_uri: string
  predicate_label: string
  other_uri: string
  other_label: string
}
export interface InstanceDetail {
  uri: string
  label: string
  class_uri: string
  class_label: string
  data_properties: InstanceDataProperty[]
  relations: InstanceRelation[]
}

/** POST /api/graph/discovery/instance-detail — full detail for one individual in a graph. */
export function fetchInstanceDetail(params: {
  workspaceId: string
  graphUri: string
  instanceUri: string
}): Promise<InstanceDetail> {
  return postJson<InstanceDetail>(`/api/graph/discovery/instance-detail`, {
    workspace_id: params.workspaceId,
    graph_uri: params.graphUri,
    instance_uri: params.instanceUri,
  })
}

// ── Views CRUD ───────────────────────────────────────────────────────────────────

export interface SavedView {
  workspace_id: string
  id: string
  uri: string
  label: string
  name?: string | null
  description?: string | null
  view_type: string
  kind: string
  visibility: string
  creator_id?: string | null
  graph_id?: string | null
  graph_uri?: string | null
  graph_names: string[]
  state: Record<string, unknown>
  path: string
  scope: string
  created_at?: string | null
  updated_at?: string | null
}

export interface FolderNode {
  path: string
  name: string
  view_count: number
  total_count: number
}

export function listViews(params: ListViewsParams): Promise<SavedView[]> {
  return getJson<SavedView[]>(buildListViewsPath(params))
}

export function getView(workspaceId: string, viewId: string): Promise<SavedView> {
  return getJson<SavedView>(viewPath(viewId, workspaceId))
}

/** Persisted view state: the backend requires a `spec` key; we also keep the drill spine. */
export interface ViewState {
  spec: ViewQuerySpec
  spine?: unknown[]
}

export interface CreateViewBody {
  workspaceId: string
  name: string
  graphId: string
  graphUri: string
  state: ViewState
  path?: string
  description?: string | null
  graphNames?: string[]
}

/** Create a saved Explore view; `state` carries the compiled spec (+ UI spine). */
export function createView(body: CreateViewBody): Promise<SavedView> {
  return postJson<SavedView>(VIEW_BASE, {
    workspace_id: body.workspaceId,
    name: body.name,
    kind: 'query',
    view_type: 'Explore',
    visibility: 'workspace',
    graph_id: body.graphId,
    graph_uri: body.graphUri,
    state: body.state,
    path: body.path ?? '',
    description: body.description ?? null,
    graph_names: body.graphNames ?? [],
  })
}

export interface UpdateViewBody {
  workspaceId: string
  name?: string
  path?: string
  state?: ViewState
  /** Pass a string to set, '' to clear; omit to leave unchanged. */
  description?: string | null
}

export async function updateView(viewId: string, body: UpdateViewBody): Promise<SavedView> {
  const payload: Record<string, unknown> = { workspace_id: body.workspaceId }
  if (body.name !== undefined) payload.name = body.name
  if (body.path !== undefined) payload.path = body.path
  if (body.state !== undefined) payload.state = body.state
  if (body.description !== undefined) payload.description = body.description
  const res = await authFetch(viewPath(viewId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as SavedView
}

export async function deleteView(workspaceId: string, viewId: string): Promise<void> {
  const res = await authFetch(viewPath(viewId, workspaceId), { method: 'DELETE' })
  if (!res.ok) throw await parseError(res)
}

export function listFolders(workspaceId: string): Promise<{ folders: FolderNode[] }> {
  return getJson<{ folders: FolderNode[] }>(foldersPath(workspaceId))
}

export interface RenameFolderBody {
  workspaceId: string
  fromPath: string
  toPath: string
  merge?: boolean
}

export async function renameFolder(
  body: RenameFolderBody,
): Promise<{ status: string; from_path: string; to_path: string; updated_count: number }> {
  const res = await authFetch(`${VIEW_BASE}/folders/rename`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: body.workspaceId,
      from_path: body.fromPath,
      to_path: body.toPath,
      merge: body.merge ?? false,
    }),
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as { status: string; from_path: string; to_path: string; updated_count: number }
}
