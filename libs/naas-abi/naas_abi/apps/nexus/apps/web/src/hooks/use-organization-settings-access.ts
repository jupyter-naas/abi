'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { authFetch, useAuthStore } from '@/stores/auth';
import { opensRolesAndPermissions } from '@/components/access/access-sections';
import { organizationContainer } from '@/components/access/access-scope';
import type { AccessView } from '@/lib/iam-admin/types';

export type OrganizationSettingsAccessStatus = 'checking' | 'ready' | 'error';

type Fetcher = (url: string) => Promise<Response>;

/** What decides, for one organization the caller lists: their role there (an IAM role
 *  attachment) and, when it is no admin's, what `GET /access` answers at its container. */
export type OrganizationAccess = { role: string | null; access: AccessView | null };

/** At most this many organizations are asked about. */
export const MAX_ORGANIZATIONS = 25;

function opensOne({ role, access }: OrganizationAccess): boolean {
  return role === 'owner' || role === 'admin' || opensRolesAndPermissions(access);
}

/**
 * Whether Organization settings opens a section for the caller in one of their
 * organizations: they are its owner or admin there, or IAM shows them a Roles &
 * permissions section at its scope. Never a workspace's role.
 */
export function opensOrganizationSettings(orgs: OrganizationAccess[]): boolean {
  return orgs.some(opensOne);
}

async function json<T>(fetcher: Fetcher, url: string): Promise<T | null> {
  const response = await fetcher(url);
  // 401, 403, 404: nothing there for the caller.
  if (response.status === 401 || response.status === 403 || response.status === 404) return null;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as T;
}

/** Asks only as needed: an organization's role first, its access when the role does
 *  not open it; stops at the first organization that does. */
export async function fetchOrganizationSettingsAccess(fetcher: Fetcher = authFetch): Promise<boolean> {
  const orgs = (await json<{ id: string }[]>(fetcher, '/api/organizations')) ?? [];
  for (const org of orgs.slice(0, MAX_ORGANIZATIONS)) {
    const id = encodeURIComponent(org.id);
    const detail = await json<{ current_user_role?: string | null }>(fetcher, `/api/organizations/${id}`);
    const role = detail?.current_user_role ?? null;
    if (opensOne({ role, access: null })) return true;
    const scope = encodeURIComponent(organizationContainer(org.id));
    const access = await json<AccessView>(fetcher, `/api/iam/admin/access?scope=${scope}`);
    if (opensOne({ role, access })) return true;
  }
  return false;
}

export interface OrganizationSettingsAccessState {
  userId: string | null;
  status: OrganizationSettingsAccessStatus;
  opens: boolean | null;
  pending: { userId: string; promise: Promise<void> } | null;
  load: (userId: string) => Promise<void>;
}

/** One shared request per user; a failure keeps the last answer this user had. */
export function createOrganizationSettingsAccessStore(fetcher: Fetcher = authFetch) {
  return create<OrganizationSettingsAccessState>((set, get) => ({
    userId: null,
    status: 'checking',
    opens: null,
    pending: null,
    load: (userId) => {
      const pending = get().pending;
      if (pending?.userId === userId) return pending.promise;
      const known = get().userId === userId ? get().opens : null;
      set({ userId, status: known === null ? 'checking' : 'ready', opens: known });
      const call: { userId: string; promise: Promise<void> } = { userId, promise: Promise.resolve() };
      call.promise = (async () => {
        try {
          const opens = await fetchOrganizationSettingsAccess(fetcher);
          if (get().userId === userId) set({ status: 'ready', opens });
        } catch {
          if (get().userId === userId) {
            const kept = get().opens;
            set({ status: kept === null ? 'error' : 'ready', opens: kept });
          }
        } finally {
          if (get().pending === call) set({ pending: null });
        }
      })();
      set({ pending: call });
      return call.promise;
    },
  }));
}

const useOrganizationSettingsAccessStore = createOrganizationSettingsAccessStore();

/** Whether the account menu shows Organization Settings: false while checking. Asked
 *  again when the user changes or the last read failed. */
export function useOrganizationSettingsAccess(): boolean {
  const userId = useAuthStore((s) => s.user?.id ?? 'session');
  const opens = useOrganizationSettingsAccessStore((s) => s.opens);
  const knownUser = useOrganizationSettingsAccessStore((s) => s.userId);
  const load = useOrganizationSettingsAccessStore((s) => s.load);

  useEffect(() => {
    const state = useOrganizationSettingsAccessStore.getState();
    if (state.userId !== userId || state.status === 'error') void load(userId);
  }, [userId, load]);

  return knownUser === userId && opens === true;
}
