import { apiFetch, apiFetchRaw, buildQuery, type RequestOptions } from './client';
import {
  GraphListResponseSchema,
  GraphViewListResponseSchema,
  NetworkResponseSchema,
  OverviewSchema,
  FilterOptionsResponseSchema,
  TriplePreviewResponseSchema,
  OntologyClassesResponseSchema,
  CreatedEntitySchema,
  extractCreatedId,
  type ApiNode,
  type ApiEdge,
  type GraphViewInfo,
  type FilterOptionsResponse,
  type TriplePreviewResponse,
} from '@/lib/schemas/graph';
import { z } from 'zod';

export interface GraphSelection {
  workspaceId: string;
  graphId: string | null;
  visibleGraphIds: string[];
  savedViewId: string | null;
  /** Ordered list of graph ids known to exist (used as a fallback). */
  knownGraphIds: string[];
}

export interface NetworkResult {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

export interface GraphListItem {
  id: string;
  name: string;
}

function effectiveGraphIds(sel: GraphSelection): string[] {
  if (sel.graphId) return [sel.graphId];
  const fromVisible = sel.visibleGraphIds.filter((id) => !id.includes('#layer='));
  if (fromVisible.length > 0) return fromVisible;
  return sel.knownGraphIds;
}

/* ---------------- queries ---------------- */

export async function fetchGraphList(
  workspaceId: string,
  options: RequestOptions = {},
): Promise<{ items: GraphListItem[]; defaultGraphId: string | null }> {
  const data = await apiFetch(
    `/api/graph/list${buildQuery({ workspace_id: workspaceId })}`,
    GraphListResponseSchema,
    options,
  );

  const flat: Array<{ id: string; label?: string }> = Array.isArray(data)
    ? data.flatMap((entry) =>
        entry && typeof entry === 'object' && 'graphs' in entry
          ? entry.graphs
          : [entry as { id: string; label?: string }],
      )
    : data.graphs;

  const items: GraphListItem[] = flat.map((g) => ({
    id: g.id,
    name: g.label ?? g.id,
  }));

  return {
    items,
    defaultGraphId: items[0]?.id ?? null,
  };
}

export async function fetchNetwork(
  sel: GraphSelection,
  options: RequestOptions = {},
): Promise<NetworkResult> {
  const limit = '500';
  let path: string;

  if (sel.savedViewId) {
    path =
      `/api/view/${encodeURIComponent(sel.savedViewId)}/network` +
      buildQuery({ workspace_id: sel.workspaceId, limit });
    const data = await apiFetch(path, NetworkResponseSchema, options);
    return { nodes: data.nodes ?? [], edges: data.edges ?? [] };
  }

  const ids = effectiveGraphIds(sel);
  if (ids.length === 0) return { nodes: [], edges: [] };
  // Currently the backend serves one graph at a time; the multi-graph aggregation
  // happens here so we can lift it later without changing the call sites.
  const merged: NetworkResult = { nodes: [], edges: [] };
  const seenNodes = new Set<string>();
  const seenEdges = new Set<string>();
  for (const id of ids) {
    const data = await apiFetch(
      `/api/graph/${encodeURIComponent(id)}/network` +
        buildQuery({ workspace_id: sel.workspaceId, limit }),
      NetworkResponseSchema,
      options,
    );
    for (const n of data.nodes ?? []) {
      if (seenNodes.has(n.id)) continue;
      seenNodes.add(n.id);
      merged.nodes.push(n);
    }
    for (const e of data.edges ?? []) {
      if (seenEdges.has(e.id)) continue;
      seenEdges.add(e.id);
      merged.edges.push(e);
    }
  }
  return merged;
}

export async function fetchOverview(
  sel: GraphSelection,
  options: RequestOptions = {},
) {
  if (sel.savedViewId) {
    return apiFetch(
      `/api/view/${encodeURIComponent(sel.savedViewId)}/overview` +
        buildQuery({ workspace_id: sel.workspaceId }),
      OverviewSchema,
      options,
    );
  }
  const ids = effectiveGraphIds(sel);
  const id = ids[0];
  if (!id) return null;
  return apiFetch(
    `/api/graph/${encodeURIComponent(id)}/overview` +
      buildQuery({ workspace_id: sel.workspaceId }),
    OverviewSchema,
    options,
  );
}

export interface GraphViewInfoDefaulted {
  workspace_id?: string;
  id: string;
  label: string;
  graph_names: string[];
  graph_filters: string[];
  scope: 'workspace' | 'user';
  user_id?: string | null;
  created_at?: string;
}

export async function fetchViews(
  workspaceId: string,
  options: RequestOptions = {},
): Promise<GraphViewInfoDefaulted[]> {
  const items = await apiFetch(
    `/api/view/list${buildQuery({ workspace_id: workspaceId })}`,
    GraphViewListResponseSchema,
    options,
  );
  return items.map((view) => ({
    ...view,
    graph_names: view.graph_names ?? [],
    graph_filters: view.graph_filters ?? [],
  }));
}

export interface NodeIris {
  graphIds: string[];
  nodeIris: string[];
}

export async function fetchNetworkParents(
  workspaceId: string,
  iris: NodeIris,
  options: RequestOptions = {},
): Promise<NetworkResult> {
  const graphNames = iris.graphIds.map((id) => `http://ontology.naas.ai/graph/${id}`);
  const data = await apiFetch(
    `/api/graph/network/parents` +
      buildQuery({
        workspace_id: workspaceId,
        graph_names: graphNames,
        node_iris: iris.nodeIris,
      }),
    NetworkResponseSchema,
    options,
  );
  return { nodes: data.nodes ?? [], edges: data.edges ?? [] };
}

export async function fetchOntologyClasses(options: RequestOptions = {}) {
  const data = await apiFetch(
    `/api/ontology/classes`,
    OntologyClassesResponseSchema,
    options,
  );
  const items = Array.isArray(data) ? data : data.items ?? [];
  return items
    .map((item) => {
      const id = item.id ?? item.iri ?? '';
      const name = item.name ?? item.label ?? item.iri ?? '';
      const description = item.description ?? item.definition ?? '';
      return id && name ? { id, name, description } : null;
    })
    .filter((item): item is { id: string; name: string; description: string } => item !== null)
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
}

export interface ViewFilterDraft {
  subject_uri: string;
  predicate_uri: string;
  object_uri: string;
}

export async function fetchFilterOptions(
  workspaceId: string,
  graphIds: string[],
  row: ViewFilterDraft,
  options: RequestOptions = {},
): Promise<FilterOptionsResponse> {
  const names = graphIds.length > 0 ? graphIds : ['default'];
  const params: Record<string, string | string[] | undefined> = {
    workspace_id: workspaceId,
    graph_names: names,
  };
  if (row.subject_uri.trim()) params.subject_uri = row.subject_uri.trim();
  if (row.predicate_uri.trim()) params.predicate_uri = row.predicate_uri.trim();
  if (row.object_uri.trim()) params.object_uri = row.object_uri.trim();
  return apiFetch(`/api/view/filters/options${buildQuery(params)}`, FilterOptionsResponseSchema, options);
}

export async function fetchTriplePreview(args: {
  workspaceId: string;
  graphIds: string[];
  filters: ViewFilterDraft[];
  limit?: number;
  options?: RequestOptions;
}): Promise<TriplePreviewResponse> {
  return apiFetch(
    `/api/view/filters/preview`,
    TriplePreviewResponseSchema,
    {
      ...args.options,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(args.options?.headers ?? {}) },
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        graph_names: args.graphIds.length > 0 ? args.graphIds : ['default'],
        filters: args.filters,
        limit: args.limit ?? 10,
      }),
    },
  );
}

/* ---------------- mutations ---------------- */

export async function createGraph(args: {
  workspaceId: string;
  label: string;
  description?: string;
}): Promise<{ id: string }> {
  const body: { workspace_id: string; label: string; description?: string } = {
    workspace_id: args.workspaceId,
    label: args.label,
  };
  if (args.description) body.description = args.description;
  const data = await apiFetch(`/api/graph/create`, CreatedEntitySchema, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const id = extractCreatedId(data);
  if (!id) throw new Error('Created graph response is missing an id.');
  return { id };
}

export async function createIndividual(args: {
  workspaceId: string;
  label: string;
  classId?: string;
  className?: string;
}): Promise<void> {
  await apiFetchRaw(`/api/graph/nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: args.workspaceId,
      type: 'Individual',
      label: args.label,
      properties: args.classId
        ? { class_id: args.classId, class_label: args.className ?? args.classId }
        : {},
    }),
  });
}

export async function updateNode(args: {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}): Promise<void> {
  await apiFetchRaw(`/api/graph/nodes/${encodeURIComponent(args.id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      label: args.label,
      type: args.type,
      properties: args.properties,
    }),
  });
}

export async function deleteNode(id: string): Promise<void> {
  await apiFetchRaw(`/api/graph/nodes/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export interface ViewPayload {
  workspaceId: string;
  name: string;
  description?: string;
  graphIds: string[];
  filters: ViewFilterDraft[];
}

const SavedViewResponseSchema = CreatedEntitySchema;

export async function createView(payload: ViewPayload): Promise<{ id: string }> {
  const data = await apiFetch(`/api/view/`, SavedViewResponseSchema, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: payload.workspaceId,
      name: payload.name,
      description: payload.description ?? undefined,
      graph_names: payload.graphIds,
      filters: payload.filters,
    }),
  });
  const id = extractCreatedId(data);
  if (!id) throw new Error('Created view response is missing an id.');
  return { id };
}

export async function updateView(viewId: string, payload: ViewPayload): Promise<{ id: string }> {
  const data = await apiFetch(
    `/api/view/${encodeURIComponent(viewId)}` +
      buildQuery({ workspace_id: payload.workspaceId }),
    SavedViewResponseSchema,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: payload.workspaceId,
        name: payload.name,
        description: payload.description ?? undefined,
        graph_names: payload.graphIds,
        filters: payload.filters,
      }),
    },
  );
  const id = extractCreatedId(data) ?? viewId;
  return { id };
}

/* ---------------- query keys ---------------- */

/**
 * Centralised query key builders. Consumers should use these, never inline
 * arrays — that way a backend rename propagates to one place.
 */
export const graphKeys = {
  all: (workspaceId: string) => ['graph', workspaceId] as const,
  list: (workspaceId: string) => ['graph', workspaceId, 'list'] as const,
  views: (workspaceId: string) => ['graph', workspaceId, 'views'] as const,
  network: (sel: GraphSelection) =>
    [
      'graph',
      sel.workspaceId,
      'network',
      sel.savedViewId,
      sel.graphId,
      [...sel.visibleGraphIds].sort(),
    ] as const,
  overview: (sel: GraphSelection) =>
    [
      'graph',
      sel.workspaceId,
      'overview',
      sel.savedViewId,
      sel.graphId,
      [...sel.visibleGraphIds].sort(),
    ] as const,
  parents: (workspaceId: string, frontierIds: string[]) =>
    ['graph', workspaceId, 'parents', [...frontierIds].sort()] as const,
};

// Re-exports so consumers don't need to know about the schemas folder.
export { extractCreatedId };
export { z };
