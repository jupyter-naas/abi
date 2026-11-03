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

/** How many organizations' access is read at once. */
export const ACCESS_BATCH = 8;

/**
 * Whether Organization settings opens for the caller in one organization: they are its
 * owner or admin there, or IAM shows them a Roles & permissions section at its scope.
 * The organization settings pages decide with it too.
 */
export function opensOrganization({ role, access }: OrganizationAccess): boolean {
  return role === 'owner' || role === 'admin' || opensRolesAndPermissions(access);
}

/**
 * Whether Organization settings opens a section for the caller in one of their
 * organizations. Never a workspace's role.
 */
export function opensOrganizationSettings(orgs: OrganizationAccess[]): boolean {
  return orgs.some(opensOrganization);
}

async function json<T>(fetcher: Fetcher, url: string): Promise<T | null> {
  const response = await fetcher(url);
  // 401, 403, 404: nothing there for the caller.
  if (response.status === 401 || response.status === 403 || response.status === 404) return null;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as T;
}

/** The access a caller has at an organization's container (`GET /access`), or null. */
export function fetchOrganizationAccess(orgId: string, fetcher: Fetcher = authFetch): Promise<AccessView | null> {
  const scope = encodeURIComponent(organizationContainer(orgId));
  return json<AccessView>(fetcher, `/api/iam/admin/access?scope=${scope}`);
}

/** One list (`GET /api/organizations` carries the caller's role in each); the access is
 *  read only for the organizations where the role does not open it, `ACCESS_BATCH` at a
 *  time, stopping at the first batch that opens one. Every organization counts. */
export async function fetchOrganizationSettingsAccess(fetcher: Fetcher = authFetch): Promise<boolean> {
  type Listed = { id: string; current_user_role?: string | null };
  const orgs = (await json<Listed[]>(fetcher, '/api/organizations')) ?? [];
  if (orgs.some((org) => opensOrganization({ role: org.current_user_role ?? null, access: null }))) {
    return true;
  }
  for (let start = 0; start < orgs.length; start += ACCESS_BATCH) {
    const batch = orgs.slice(start, start + ACCESS_BATCH);
    const accesses = await Promise.all(batch.map((org) => fetchOrganizationAccess(org.id, fetcher)));
    if (accesses.some((access) => opensRolesAndPermissions(access))) return true;
  }
  return false;
}

/** The organizations whose settings open for the caller, in the order given: owners' and
 *  admins' from the list, the others' once their access is read (`ACCESS_BATCH` at a time). */
export async function openableOrganizations<T extends { id: string; currentUserRole?: string | null }>(
  orgs: T[],
  fetcher: Fetcher = authFetch
): Promise<T[]> {
  const opens = new Set<string>();
  const rest = orgs.filter((org) => {
    if (opensOrganization({ role: org.currentUserRole ?? null, access: null })) {
      opens.add(org.id);
      return false;
    }
    return true;
  });
  for (let start = 0; start < rest.length; start += ACCESS_BATCH) {
    const batch = rest.slice(start, start + ACCESS_BATCH);
    const accesses = await Promise.all(batch.map((org) => fetchOrganizationAccess(org.id, fetcher)));
    batch.forEach((org, i) => {
      if (opensRolesAndPermissions(accesses[i])) opens.add(org.id);
    });
  }
  return orgs.filter((org) => opens.has(org.id));
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
