/** HTTP client for `/api/search/topics` (see `search-topics.ts` for the types). */
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { SEARCH_SOURCE_IDS } from '@/lib/search-scopes';
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
  /**
   * Offer or stop offering a source of the search, a feature or a web engine ("web.<engine>"):
   * a section of the workspace's offer ("<W> access"), written as the caller. IAM refuses a
   * source beyond the organization's offer, or one the caller does not hold. Answers the
   * sources the workspace no longer offers.
   */
  setScopeEnabled: async (workspaceId: string, scopeId: string, enabled: boolean) => {
    const response = await authFetch(
      `${getApiUrl()}/api/workspaces/${encodeURIComponent(workspaceId)}/offer/search-sources`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes: { [scopeId]: enabled } }),
      },
    );
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
      const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`;
      throw new TopicApiError(detail, response.status);
    }
    const state = (await response.json()) as { offered?: { search_sources?: string[] } };
    const offered = new Set(state.offered?.search_sources ?? []);
    return { disabled_scopes: SEARCH_SOURCE_IDS.filter((id) => !offered.has(id)) };
  },
  contract: () => request<Record<QueryRole, RoleContract>>('/contract'),
  results: (workspaceId: string, topicId: string, q: string, offset = 0, limit = 30) =>
    request<TopicResults>(
      `/${encodeURIComponent(topicId)}/results?${ws(workspaceId)}&${new URLSearchParams({ q, offset: String(offset), limit: String(limit) })}`,
    ),
  detail: (workspaceId: string, topicId: string, uri: string) =>
    request<TopicDetail>(`/${encodeURIComponent(topicId)}/detail?${ws(workspaceId)}&${new URLSearchParams({ uri })}`),
  /** Retire the workspace's cached search responses (kept a day): the next search reads the graphs. */
  refreshCache: (workspaceId: string) =>
    request<{ refreshed: boolean }>(`/cache/refresh?${ws(workspaceId)}`, { method: 'POST' }),
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
