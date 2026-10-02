import { authFetch } from '@/stores/auth';
import type { AuditEntry, ResourceDetail, ResourceEntry, ResourcePage, ResourceServiceInfo } from './data-types';

export const RESOURCES_API = '/api/admin/system/resources';

export type Fetch = (url: string, init?: RequestInit) => Promise<Response>;

/** Why a call failed. ``confirm`` is set when the change needs the id typed back. */
export interface Failure {
  ok: false;
  status: number;
  reason: string;
  source?: string;
  confirm?: string;
  operation?: string;
}

export type Result<T> = { ok: true; data: T } | Failure;

export interface ListOptions {
  cursor?: string | null;
  query?: string | null;
  limit?: number;
}

export interface DataApi {
  services(): Promise<Result<{ services: ResourceServiceInfo[] }>>;
  list(service: string, parent: string, options?: ListOptions): Promise<Result<ResourcePage>>;
  read(service: string, id: string): Promise<Result<ResourceDetail>>;
  reveal(service: string, id: string): Promise<Result<ResourceDetail>>;
  download(service: string, id: string): Promise<Result<Blob>>;
  write(service: string, id: string, body: Blob | string, confirm?: string): Promise<Result<ResourceEntry>>;
  remove(service: string, id: string, confirm: string): Promise<Result<null>>;
  history(service: string, id: string): Promise<Result<{ entries: AuditEntry[] }>>;
  recent(service?: string): Promise<Result<{ entries: AuditEntry[] }>>;
}

function failure(status: number, body: unknown, fallback: string): Failure {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return { ok: false, status, reason: detail };
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    return { ok: false, status, reason: first?.msg ?? fallback };
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    if (typeof d.limit === 'number') {
      return { ok: false, status, reason: `Too large: the limit is ${formatLimit(d.limit)}.` };
    }
    return {
      ok: false,
      status,
      reason: typeof d.reason === 'string' ? d.reason : fallback,
      source: typeof d.source === 'string' ? d.source : undefined,
      confirm: typeof d.confirm === 'string' ? d.confirm : undefined,
      operation: typeof d.operation === 'string' ? d.operation : undefined,
    };
  }
  return { ok: false, status, reason: fallback };
}

function formatLimit(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} bytes`;
}

async function call<T>(
  fetcher: Fetch,
  path: string,
  init: RequestInit | undefined,
  parse: (res: Response) => Promise<T>,
): Promise<Result<T>> {
  let res: Response;
  try {
    res = await fetcher(`${RESOURCES_API}${path}`, init);
  } catch (error) {
    return { ok: false, status: 0, reason: error instanceof Error ? error.message : String(error) };
  }
  if (res.ok) return { ok: true, data: await parse(res) };
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return failure(res.status, body, res.statusText || `HTTP ${res.status}`);
}

const json = <T,>(res: Response): Promise<T> => res.json() as Promise<T>;

export function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function createDataApi(fetcher: Fetch = authFetch): DataApi {
  const at = (service: string) => `/${encodeURIComponent(service)}`;
  return {
    services: () => call<{ services: ResourceServiceInfo[] }>(fetcher, '', undefined, json),
    list: (service, parent, options = {}) =>
      call<ResourcePage>(
        fetcher,
        `${at(service)}/entries${query({ parent, cursor: options.cursor, query: options.query, limit: options.limit })}`,
        undefined,
        json,
      ),
    read: (service, id) => call<ResourceDetail>(fetcher, `${at(service)}/entry${query({ id })}`, undefined, json),
    reveal: (service, id) =>
      call<ResourceDetail>(fetcher, `${at(service)}/reveal${query({ id })}`, { method: 'POST' }, json),
    download: (service, id) =>
      call<Blob>(fetcher, `${at(service)}/download${query({ id })}`, undefined, (res) => res.blob()),
    write: (service, id, body, confirm) =>
      call<ResourceEntry>(fetcher, `${at(service)}/entry${query({ id, confirm })}`, { method: 'PUT', body }, json),
    remove: (service, id, confirm) =>
      call<null>(fetcher, `${at(service)}/entry${query({ id, confirm })}`, { method: 'DELETE' }, async () => null),
    history: (service, id) =>
      call<{ entries: AuditEntry[] }>(fetcher, `${at(service)}/history${query({ id })}`, undefined, json),
    recent: (service) => call<{ entries: AuditEntry[] }>(fetcher, `/history${query({ service })}`, undefined, json),
  };
}
