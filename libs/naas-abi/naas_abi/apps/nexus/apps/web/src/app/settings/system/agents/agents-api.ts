import { authFetch } from '@/stores/auth';
import { query, type Failure, type Fetch, type Result } from '../data/data-api';
import type { AgentRunDetail, AgentRunsPage } from './agents-types';

export const AGENTS_API = '/api/admin/system/agents';

export interface AgentRunFilters {
  module?: string | null;
  agent?: string | null;
  statuses?: string[];
  before?: string | null;
  limit?: number;
}

export interface AgentsApi {
  /** Reads take an optional ``signal``: a poll aborts the request it no longer needs. */
  runs(filters?: AgentRunFilters, signal?: AbortSignal): Promise<Result<AgentRunsPage>>;
  run(moduleId: string, runId: string, signal?: AbortSignal): Promise<Result<AgentRunDetail>>;
  cancel(moduleId: string, runId: string): Promise<Result<{ ok: boolean }>>;
}

async function call<T>(fetcher: Fetch, path: string, init?: RequestInit): Promise<Result<T>> {
  let res: Response;
  try {
    res = await fetcher(`${AGENTS_API}${path}`, init);
  } catch (error) {
    return { ok: false, status: 0, reason: error instanceof Error ? error.message : String(error) };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (res.ok) return { ok: true, data: body as T };
  const detail = (body as { detail?: unknown } | null)?.detail;
  const failure: Failure = { ok: false, status: res.status, reason: res.statusText || `HTTP ${res.status}` };
  if (typeof detail === 'string') failure.reason = detail;
  else if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    if (typeof d.reason === 'string') failure.reason = d.reason;
    if (typeof d.source === 'string') failure.source = d.source;
  }
  return failure;
}

const seg = (value: string) => encodeURIComponent(value);

export function createAgentsApi(fetcher: Fetch = authFetch): AgentsApi {
  return {
    runs: (f = {}, signal) =>
      call(
        fetcher,
        `/runs${query({
          module: f.module,
          agent: f.agent,
          status: f.statuses?.length ? f.statuses.join(',') : null,
          before: f.before,
          limit: f.limit,
        })}`,
        { signal },
      ),
    run: (moduleId, runId, signal) => call(fetcher, `/runs/${seg(moduleId)}/${seg(runId)}`, { signal }),
    cancel: (moduleId, runId) => call(fetcher, `/runs/${seg(moduleId)}/${seg(runId)}/cancel`, { method: 'POST' }),
  };
}
