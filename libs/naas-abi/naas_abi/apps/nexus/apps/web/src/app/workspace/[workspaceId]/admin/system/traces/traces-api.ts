import { authFetch } from '@/stores/auth';
import { query, type Failure, type Fetch, type Result } from '../data/data-api';
import type { Trace, TraceQuery, TraceSummary } from './traces-types';

export const TRACES_API = '/api/admin/system/traces';

export interface TracesApi {
  services(): Promise<Result<{ services: string[]; ui_url: string | null }>>;
  operations(service: string): Promise<Result<{ operations: { name: string; kind: string }[] }>>;
  search(q: TraceQuery): Promise<Result<{ traces: TraceSummary[] }>>;
  trace(traceId: string): Promise<Result<Trace>>;
}

async function call<T>(fetcher: Fetch, path: string): Promise<Result<T>> {
  let res: Response;
  try {
    res = await fetcher(`${TRACES_API}${path}`);
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

export function createTracesApi(fetcher: Fetch = authFetch): TracesApi {
  return {
    services: () => call(fetcher, '/services'),
    operations: (service) => call(fetcher, `/operations${query({ service })}`),
    search: (q) =>
      call(
        fetcher,
        query({
          service: q.service,
          operation: q.operation,
          lookback: q.lookback,
          min_duration_ms: q.min_duration_ms ?? null,
          max_duration_ms: q.max_duration_ms ?? null,
          errors: q.errors ? 'true' : null,
          limit: q.limit,
        }),
      ),
    trace: (traceId) => call(fetcher, `/${encodeURIComponent(traceId)}`),
  };
}
