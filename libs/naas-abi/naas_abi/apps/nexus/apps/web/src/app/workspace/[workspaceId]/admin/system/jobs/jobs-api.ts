import { authFetch } from '@/stores/auth';
import { query, type Failure, type Fetch, type Result } from '../data/data-api';
import type { JobsOverview, RunDetail, RunsPage } from './jobs-types';

export const JOBS_API = '/api/admin/system/jobs';

export interface RunFilters {
  module?: string | null;
  job?: string | null;
  statuses?: string[];
  trigger?: string | null;
  before?: string | null;
  limit?: number;
}

export interface JobsApi {
  overview(): Promise<Result<JobsOverview>>;
  runs(filters?: RunFilters): Promise<Result<RunsPage>>;
  run(moduleId: string, runId: string): Promise<Result<RunDetail>>;
  trigger(moduleId: string, job: string, payload: Record<string, unknown>): Promise<Result<{ run_id: string; key: string }>>;
  cancel(moduleId: string, runId: string): Promise<Result<{ ok: boolean }>>;
}

async function call<T>(fetcher: Fetch, path: string, init?: RequestInit): Promise<Result<T>> {
  let res: Response;
  try {
    res = await fetcher(`${JOBS_API}${path}`, init);
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

export function createJobsApi(fetcher: Fetch = authFetch): JobsApi {
  return {
    overview: () => call(fetcher, ''),
    runs: (f = {}) =>
      call(
        fetcher,
        `/runs${query({
          module: f.module,
          job: f.job,
          status: f.statuses?.length ? f.statuses.join(',') : null,
          trigger: f.trigger,
          before: f.before,
          limit: f.limit,
        })}`,
      ),
    run: (moduleId, runId) => call(fetcher, `/runs/${seg(moduleId)}/${seg(runId)}`),
    trigger: (moduleId, job, payload) =>
      call(fetcher, `/${seg(moduleId)}/${seg(job)}/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload }),
      }),
    cancel: (moduleId, runId) => call(fetcher, `/runs/${seg(moduleId)}/${seg(runId)}/cancel`, { method: 'POST' }),
  };
}
