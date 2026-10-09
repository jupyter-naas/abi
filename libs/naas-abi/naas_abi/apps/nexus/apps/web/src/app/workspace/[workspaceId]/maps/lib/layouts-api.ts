import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import type { WorkspaceMapLayout } from './layouts';

/** Settings → Maps API: workspace layouts and which layouts are hidden. */

export interface WorkspaceLayoutsResponse {
  layouts: WorkspaceMapLayout[];
  hidden: string[];
  can_edit: boolean;
}

export interface LayoutPreview {
  errors: string[];
  count: number;
  pins: { id: string; label: string; lat: number; lng: number; detail?: string }[];
}

export type LayoutDraft = Omit<WorkspaceMapLayout, 'id'>;

export class LayoutApiError extends Error {
  constructor(message: string, readonly errors: string[] = []) {
    super(message);
  }
}

const base = () => `${getApiUrl()}/api/maps/layouts`;
const ws = (workspaceId: string) => `workspace_id=${encodeURIComponent(workspaceId)}`;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(url, init);
  if (response.ok) return (await response.json()) as T;
  let detail: unknown;
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (detail && typeof detail === 'object' && Array.isArray((detail as { errors?: unknown }).errors)) {
    const errors = (detail as { errors: string[] }).errors;
    throw new LayoutApiError(errors.join('\n'), errors);
  }
  throw new LayoutApiError(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const layoutsApi = {
  list: (workspaceId: string) => request<WorkspaceLayoutsResponse>(`${base()}?${ws(workspaceId)}`),
  save: (workspaceId: string, id: string, draft: LayoutDraft) =>
    request<WorkspaceMapLayout>(`${base()}/${encodeURIComponent(id)}?${ws(workspaceId)}`, json('PUT', draft)),
  remove: (workspaceId: string, id: string) =>
    request<{ message: string }>(`${base()}/${encodeURIComponent(id)}?${ws(workspaceId)}`, { method: 'DELETE' }),
  setHidden: (workspaceId: string, id: string, hidden: boolean) =>
    request<{ hidden: string[] }>(`${base()}/${encodeURIComponent(id)}/visibility?${ws(workspaceId)}`, json('PUT', { hidden })),
  preview: (workspaceId: string, draft: LayoutDraft) =>
    request<LayoutPreview>(`${base()}/preview`, json('POST', { ...draft, workspace_id: workspaceId })),
  feedUrl: (workspaceId: string, id: string) => `${base()}/${encodeURIComponent(id)}/feed?${ws(workspaceId)}`,
};

export function blankLayout(): LayoutDraft {
  return {
    title: '',
    description: '',
    icon: 'MapPin',
    color: '#2563eb',
    graphs: [],
    order: 100,
    query: [
      'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>',
      'PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>',
      '',
      '# Project ?label ?lat ?lng (required) and ?uri ?detail ?graph (optional).',
      'SELECT ?uri ?label ?lat ?lng WHERE {',
      '  ?uri rdfs:label ?label ;',
      '       geo:lat ?lat ;',
      '       geo:long ?lng .',
      '}',
    ].join('\n'),
  };
}
