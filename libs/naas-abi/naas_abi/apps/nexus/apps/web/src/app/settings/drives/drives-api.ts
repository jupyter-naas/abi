import { authFetch } from '@/stores/auth';
import { errorText, type PlatformDrive } from './drives-model';

export const DRIVES_API = '/api/platform/drives';

export type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export type Answer<T> = { ok: true; data: T } | { ok: false; status: number; error: string };

/** Every drive of the platform, each with whether its storage answers (platform admins). */
export async function listDrives(fetcher: Fetcher = authFetch): Promise<Answer<PlatformDrive[]>> {
  let res: Response;
  try {
    res = await fetcher(DRIVES_API);
  } catch (error) {
    return { ok: false, status: 0, error: error instanceof Error ? error.message : String(error) };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (res.ok) return { ok: true, data: (body as PlatformDrive[] | null) ?? [] };
  return { ok: false, status: res.status, error: errorText(res.status, body) };
}
