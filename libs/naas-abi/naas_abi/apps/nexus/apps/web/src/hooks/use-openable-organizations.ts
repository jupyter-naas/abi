'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { usePermissionRevision, usePermissionSessionKey } from '@/lib/permission-cache';
import { openableOrganizations, organizationsOpenedByRole } from '@/hooks/use-organization-settings-access';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

/** `role`: the caller's there, which decides the sections an organization shows them. */
export type OpenableOrganization = { id: string; name: string; role: string | null };
export type OpenableOrganizationsStatus = 'checking' | 'ready' | 'error';

/** How long a list stays fresh: a mount after that reads it again, showing the old one meanwhile. */
export const OPENABLE_ORGANIZATIONS_TTL_MS = 60_000;

type Listed = { id: string; name?: string | null; current_user_role?: string | null };

export type ListedOrganization = { id: string; name: string; currentUserRole: string | null };

function asOpenable(org: ListedOrganization): OpenableOrganization {
  return { id: org.id, name: org.name, role: org.currentUserRole };
}

/** `GET /api/organizations`, with the caller's role in each. Nothing when the list is refused. */
export async function fetchOrganizationList(fetcher: Fetcher = authFetch): Promise<ListedOrganization[]> {
  const response = await (fetcher === authFetch
    ? fetcher('/api/organizations', { cache: 'force-cache' })
    : fetcher('/api/organizations'));
  if (response.status === 401 || response.status === 403 || response.status === 404) return [];
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const orgs = (await response.json()) as Listed[];
  return orgs.map((org) => ({ id: org.id, name: org.name || org.id, currentUserRole: org.current_user_role ?? null }));
}

/** `GET /api/organizations`, then the access of those the role does not open. */
export async function fetchOpenableOrganizations(fetcher: Fetcher = authFetch): Promise<OpenableOrganization[]> {
  const listed = await fetchOrganizationList(fetcher);
  const open = await openableOrganizations(listed, fetcher);
  return open.map(asOpenable);
}

export interface OpenableOrganizationsState {
  userId: string | null;
  status: OpenableOrganizationsStatus;
  orgs: OpenableOrganization[] | null;
  loadedAt: number;
  pending: { userId: string; promise: Promise<void> } | null;
  load: (userId: string) => Promise<void>;
}

/**
 * The organizations whose settings open for the caller, warmed by the avatar and read by
 * the Settings tabs: one call in flight per user, kept across mounts. A failed
 * read keeps the last list this user had.
 */
export function createOpenableOrganizationsStore(fetcher: Fetcher = authFetch, now: () => number = Date.now) {
  return create<OpenableOrganizationsState>((set, get) => ({
    userId: null,
    status: 'checking',
    orgs: null,
    loadedAt: 0,
    pending: null,
    load: (userId) => {
      const pending = get().pending;
      if (pending?.userId === userId) return pending.promise;
      const known = get().userId === userId ? get().orgs : null;
      set({ userId, status: known ? 'ready' : 'checking', orgs: known });
      const call: { userId: string; promise: Promise<void> } = { userId, promise: Promise.resolve() };
      call.promise = (async () => {
        try {
          // The role opens an organization with no further read: publish those so the
          // Settings tabs can paint, then read the access of the rest.
          const listed = await fetchOrganizationList(fetcher);
          const byRole = organizationsOpenedByRole(listed).map(asOpenable);
          if (byRole.length > 0 && get().pending === call && get().userId === userId) {
            set({ status: 'ready', orgs: byRole, loadedAt: now() });
          }
          const orgs = (await openableOrganizations(listed, fetcher)).map(asOpenable);
          if (get().pending === call && get().userId === userId) set({ status: 'ready', orgs, loadedAt: now() });
        } catch {
          if (get().pending === call && get().userId === userId) {
            const kept = get().orgs;
            set({ status: kept ? 'ready' : 'error', orgs: kept });
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

export const useOpenableOrganizationsStore = createOpenableOrganizationsStore();

/** Whether a mount should read the list (again): another user, an error, or a stale list. */
export function needsOpenableOrganizations(
  state: Pick<OpenableOrganizationsState, 'userId' | 'status' | 'loadedAt' | 'pending'>,
  userId: string,
  now: number
): boolean {
  if (state.pending?.userId === userId) return false;
  if (state.userId !== userId || state.status === 'error') return true;
  return state.status === 'ready' && now - state.loadedAt > OPENABLE_ORGANIZATIONS_TTL_MS;
}

/** The caller's openable organizations: `checking` until the first answer for this user. */
export function useOpenableOrganizations(): { status: OpenableOrganizationsStatus; orgs: OpenableOrganization[] } {
  const userId = usePermissionSessionKey();
  const revision = usePermissionRevision();
  const status = useOpenableOrganizationsStore((s) => s.status);
  const orgs = useOpenableOrganizationsStore((s) => s.orgs);
  const knownUser = useOpenableOrganizationsStore((s) => s.userId);
  const load = useOpenableOrganizationsStore((s) => s.load);

  useEffect(() => {
    void load(userId);
  }, [userId, load, revision]);

  if (knownUser !== userId) return { status: 'checking', orgs: [] };
  return { status, orgs: orgs ?? [] };
}
