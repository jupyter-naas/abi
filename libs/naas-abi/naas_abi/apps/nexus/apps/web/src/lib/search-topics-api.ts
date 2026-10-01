/** HTTP client for `/api/search/topics` (see `search-topics.ts` for the types). */
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import type { PreviewResult, QueryRole, RoleContract, SearchTopic, TopicDetail, TopicResults } from '@/lib/search-topics';

export class TopicApiError extends Error {
  constructor(message: string, readonly status: number, readonly errors: string[] = []) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(`${getApiUrl()}/api/search/topics${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && Array.isArray((detail as { errors?: unknown }).errors)) {
      const errors = (detail as { errors: string[] }).errors;
      throw new TopicApiError(errors.join('\n'), response.status, errors);
    }
    throw new TopicApiError(typeof detail === 'string' ? detail : `Request failed (${response.status})`, response.status);
  }
  return response.json() as Promise<T>;
}

const ws = (workspaceId: string) => `workspace_id=${encodeURIComponent(workspaceId)}`;

export const topicsApi = {
  list: (workspaceId: string) =>
    request<{ topics: SearchTopic[]; disabled_scopes?: string[]; can_edit: boolean }>(`?${ws(workspaceId)}`),
  /** Switch a Nexus feature or a web engine ("web.<engine>") on or off for the workspace. */
  setScopeEnabled: (workspaceId: string, scopeId: string, enabled: boolean) =>
    request<{ disabled_scopes: string[] }>(`/scopes/${encodeURIComponent(scopeId)}?${ws(workspaceId)}`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),
  contract: () => request<Record<QueryRole, RoleContract>>('/contract'),
  results: (workspaceId: string, topicId: string, q: string, offset = 0, limit = 30) =>
    request<TopicResults>(
      `/${encodeURIComponent(topicId)}/results?${ws(workspaceId)}&${new URLSearchParams({ q, offset: String(offset), limit: String(limit) })}`,
    ),
  detail: (workspaceId: string, topicId: string, uri: string) =>
    request<TopicDetail>(`/${encodeURIComponent(topicId)}/detail?${ws(workspaceId)}&${new URLSearchParams({ uri })}`),
  save: (workspaceId: string, topic: SearchTopic) => {
    const { id, source: _source, ...body } = topic;
    return request<SearchTopic>(`/${encodeURIComponent(id)}?${ws(workspaceId)}`, { method: 'PUT', body: JSON.stringify(body) });
  },
  reset: (workspaceId: string, topicId: string) =>
    request<{ topic: SearchTopic | null }>(`/${encodeURIComponent(topicId)}?${ws(workspaceId)}`, { method: 'DELETE' }),
  preview: (workspaceId: string, role: QueryRole, query: string, params: Record<string, string | number>, graphs: string[] = []) =>
    request<PreviewResult>('/preview', {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, role, query, params, graphs }),
    }),
};
