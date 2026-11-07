import { authFetch } from '@/stores/auth';
import {
  errorText,
  type AdminUser,
  type Deletion,
  type InvitationProviders,
  type InviteOutcome,
} from './users-model';

export const USERS_API = '/api/admin/users';
export const PROVIDERS_API = '/api/invitations/providers';

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

const userUrl = (id: string) => `${USERS_API}/${encodeURIComponent(id)}`;

/** Every account of the platform, and those invited who have none yet. */
export function listUsers(fetcher: Fetcher = authFetch) {
  return call<AdminUser[]>(fetcher, USERS_API);
}

export function inviteUser(
  invite: { email: string; name?: string; provider?: string },
  fetcher: Fetcher = authFetch
) {
  return call<InviteOutcome>(fetcher, `${USERS_API}/invite`, json('POST', invite));
}

export function updateUser(
  id: string,
  change: { name?: string; is_superadmin?: boolean },
  fetcher: Fetcher = authFetch
) {
  return call<AdminUser>(fetcher, userUrl(id), json('PATCH', change));
}

export function deactivateUser(id: string, fetcher: Fetcher = authFetch) {
  return call<AdminUser>(fetcher, `${userUrl(id)}/deactivate`, { method: 'POST' });
}

export function reactivateUser(id: string, fetcher: Fetcher = authFetch) {
  return call<AdminUser>(fetcher, `${userUrl(id)}/reactivate`, { method: 'POST' });
}

/** What deleting the account takes away and what it leaves. */
export function deletionOf(id: string, fetcher: Fetcher = authFetch) {
  return call<Deletion>(fetcher, `${userUrl(id)}/deletion`);
}

/** Sent with the email typed back: the API checks it too. */
export function deleteUser(id: string, confirm: string, fetcher: Fetcher = authFetch) {
  return call<{ deleted: boolean; warning: string | null }>(
    fetcher,
    `${userUrl(id)}?confirm=${encodeURIComponent(confirm)}`,
    { method: 'DELETE' }
  );
}

export function listProviders(fetcher: Fetcher = authFetch) {
  return call<InvitationProviders>(fetcher, PROVIDERS_API);
}
