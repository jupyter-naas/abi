'use client';

import { useCallback, useEffect } from 'react';
import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { usePermissionRevision, usePermissionSessionKey } from '@/lib/permission-cache';
import type { PlatformActions } from '@/app/settings/lib/nav';

export type PlatformSettingsAccessStatus = 'checking' | 'ready' | 'error';

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export interface PlatformSettingsAccessState {
  /** Whose actions these are: a sign-in as someone else asks again. */
  userId: string | null;
  status: PlatformSettingsAccessStatus;
  actions: PlatformActions | null;
  /** The call in flight and whom it is for: a second caller waits for it instead of asking again. */
  pending: { userId: string; promise: Promise<void> } | null;
  load: (userId: string, refresh?: boolean) => Promise<void>;
}

/** Reads the caller's platform-level actions (`GET /api/iam/admin/access`), as IAM decides them. */
export async function fetchPlatformActions(fetcher: Fetcher = authFetch, refresh = false): Promise<PlatformActions> {
  const response = await (refresh && fetcher === authFetch
    ? fetcher('/api/iam/admin/access', { cache: 'reload' }) : fetcher('/api/iam/admin/access'));
  // 401 and 403: the caller may do nothing here, which the shell shows as a 403 page.
  if (response.status === 401 || response.status === 403) return {};
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = (await response.json()) as { actions?: PlatformActions };
  return body.actions ?? {};
}

/**
 * The access store. A failed call keeps the last answer this user had (the API checks
 * every call anyway), so an IAM outage does not hide System, where it shows; with no
 * earlier answer it is an error, which any caller may retry.
 */
export function createPlatformSettingsAccessStore(fetcher: Fetcher = authFetch) {
  return create<PlatformSettingsAccessState>((set, get) => ({
    userId: null,
    status: 'checking',
    actions: null,
    pending: null,
    load: (userId, refresh = false) => {
      const pending = get().pending;
      if (pending?.userId === userId) return pending.promise;
      const known = get().userId === userId ? get().actions : null;
      set({ userId, status: known ? 'ready' : 'checking', actions: known });
      const call: { userId: string; promise: Promise<void> } = { userId, promise: Promise.resolve() };
      call.promise = (async () => {
        try {
          const actions = await fetchPlatformActions(fetcher, refresh);
          if (get().pending === call && get().userId === userId) set({ status: 'ready', actions });
        } catch {
          if (get().pending === call && get().userId === userId) {
            const kept = get().actions;
            set({ status: kept ? 'ready' : 'error', actions: kept });
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

const usePlatformSettingsAccessStore = createPlatformSettingsAccessStore();

/**
 * What the signed-in user may open in Platform Settings. The shell asks again each
 * time it mounts, through the shared permission cache. A fresh cached response is reused;
 * stale data is revalidated without hiding the last navigation. `retry` asks now.
 */
export function usePlatformSettingsAccess({ fresh = false }: { fresh?: boolean } = {}): {
  status: PlatformSettingsAccessStatus;
  actions: PlatformActions | null;
  retry: () => void;
} {
  // The session decides: a user not in the store yet is asked about all the same.
  const userId = usePermissionSessionKey();
  const revision = usePermissionRevision();
  const status = usePlatformSettingsAccessStore((s) => s.status);
  const actions = usePlatformSettingsAccessStore((s) => s.actions);
  const knownUser = usePlatformSettingsAccessStore((s) => s.userId);
  const load = usePlatformSettingsAccessStore((s) => s.load);
  const retry = useCallback(() => void load(userId, true), [load, userId]);

  useEffect(() => {
    void load(userId);
  }, [userId, fresh, load, revision]);

  if (knownUser !== userId) return { status: 'checking', actions: null, retry };
  return { status, actions, retry };
}
