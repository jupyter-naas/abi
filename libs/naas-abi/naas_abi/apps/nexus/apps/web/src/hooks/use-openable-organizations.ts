'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { authFetch, useAuthStore } from '@/stores/auth';
import { openableOrganizations } from '@/hooks/use-organization-settings-access';

type Fetcher = (url: string) => Promise<Response>;

/** `role`: the caller's there, which decides the sections an organization shows them. */
export type OpenableOrganization = { id: string; name: string; role: string | null };
export type OpenableOrganizationsStatus = 'checking' | 'ready' | 'error';

/** How long a list stays fresh: a mount after that reads it again, showing the old one meanwhile. */
export const OPENABLE_ORGANIZATIONS_TTL_MS = 60_000;

type Listed = { id: string; name?: string | null; current_user_role?: string | null };

/** `GET /api/organizations`, then the access of those the role does not open. */
export async function fetchOpenableOrganizations(fetcher: Fetcher = authFetch): Promise<OpenableOrganization[]> {
  const response = await fetcher('/api/organizations');
  if (response.status === 401 || response.status === 403 || response.status === 404) return [];
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const orgs = (await response.json()) as Listed[];
  const open = await openableOrganizations(
    orgs.map((o) => ({ id: o.id, name: o.name || o.id, currentUserRole: o.current_user_role ?? null })),
    fetcher
  );
  return open.map((o) => ({ id: o.id, name: o.name, role: o.currentUserRole }));
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
 * The organizations whose settings open for the caller, shared by the avatar menu and
 * the settings column: one call in flight per user, kept across mounts. A failed
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
          const orgs = await fetchOpenableOrganizations(fetcher);
          if (get().userId === userId) set({ status: 'ready', orgs, loadedAt: now() });
        } catch {
          if (get().userId === userId) {
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
  const userId = useAuthStore((s) => s.user?.id ?? 'session');
  const status = useOpenableOrganizationsStore((s) => s.status);
  const orgs = useOpenableOrganizationsStore((s) => s.orgs);
  const knownUser = useOpenableOrganizationsStore((s) => s.userId);
  const load = useOpenableOrganizationsStore((s) => s.load);

  useEffect(() => {
    if (needsOpenableOrganizations(useOpenableOrganizationsStore.getState(), userId, Date.now())) {
      void load(userId);
    }
  }, [userId, load]);

  if (knownUser !== userId) return { status: 'checking', orgs: [] };
  return { status, orgs: orgs ?? [] };
}
