import { authFetch } from '@/stores/auth';
import { errorText, type PlatformOrganization } from './organizations-model';

export const ORGANIZATIONS_API = '/api/organizations';

export type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export type Answer<T> = { ok: true; data: T } | { ok: false; status: number; error: string };

async function call<T>(fetcher: Fetcher, url: string, options?: RequestInit): Promise<Answer<T>> {
  let res: Response;
  try {
    res = await fetcher(url, options);
  } catch (error) {
    return { ok: false, status: 0, error: error instanceof Error ? error.message : String(error) };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (res.ok) return { ok: true, data: body as T };
  return { ok: false, status: res.status, error: errorText(res.status, body) };
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/** Every organization IAM lets the caller list (the platform admin: all). */
export function listOrganizations(fetcher: Fetcher = authFetch) {
  return call<PlatformOrganization[]>(fetcher, ORGANIZATIONS_API);
}

export function createOrganization(name: string, slug: string, fetcher: Fetcher = authFetch) {
  return call<PlatformOrganization>(fetcher, ORGANIZATIONS_API, json('POST', { name, slug }));
}

export function renameOrganization(id: string, name: string, fetcher: Fetcher = authFetch) {
  return call<PlatformOrganization>(
    fetcher,
    `${ORGANIZATIONS_API}/${encodeURIComponent(id)}`,
    json('PATCH', { name })
  );
}

/** 409 while it still has workspaces, the API naming them. */
export function deleteOrganization(id: string, fetcher: Fetcher = authFetch) {
  return call<{ status: string; id: string }>(
    fetcher,
    `${ORGANIZATIONS_API}/${encodeURIComponent(id)}`,
    { method: 'DELETE' }
  );
}
