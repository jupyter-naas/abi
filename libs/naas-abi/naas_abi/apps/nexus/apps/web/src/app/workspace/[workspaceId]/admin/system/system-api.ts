import { authFetch } from '@/stores/auth';

export const SYSTEM_API = '/api/admin/system';

export type Loaded<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; source?: string; reason: string };

type Fetcher = (url: string) => Promise<Response>;

/** GET a SysAdmin view. A 503 names the source that is down (NATS, discovery, monitor). */
export async function loadSystem<T>(path: string, fetcher: Fetcher = authFetch): Promise<Loaded<T>> {
  let res: Response;
  try {
    res = await fetcher(`${SYSTEM_API}${path}`);
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
  if (detail && typeof detail === 'object' && 'reason' in detail) {
    const { source, reason } = detail as { source?: string; reason?: string };
    return { ok: false, status: res.status, source, reason: reason ?? res.statusText };
  }
  return {
    ok: false,
    status: res.status,
    reason: typeof detail === 'string' ? detail : res.statusText || `HTTP ${res.status}`,
  };
}
