'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { authFetch, useAuthStore } from '@/stores/auth';
import type { PlatformActions } from '@/app/settings/lib/nav';

export type PlatformSettingsAccessStatus = 'checking' | 'ready' | 'error';

interface PlatformSettingsAccessState {
  /** Whose actions these are: a sign-in as someone else asks again. */
  userId: string | null;
  status: PlatformSettingsAccessStatus;
  actions: PlatformActions | null;
  load: (userId: string) => Promise<void>;
}

/** Reads the caller's platform-level actions (`GET /api/iam/admin/access`), as IAM decides them. */
export async function fetchPlatformActions(
  fetcher: (url: string) => Promise<Response> = authFetch
): Promise<PlatformActions> {
  const response = await fetcher('/api/iam/admin/access');
  // 401 and 403: the caller may do nothing here, which the shell shows as a 403 page.
  if (response.status === 401 || response.status === 403) return {};
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = (await response.json()) as { actions?: PlatformActions };
  return body.actions ?? {};
}

const usePlatformSettingsAccessStore = create<PlatformSettingsAccessState>((set, get) => ({
  userId: null,
  status: 'checking',
  actions: null,
  load: async (userId) => {
    set({ userId, status: get().userId === userId && get().actions ? 'ready' : 'checking' });
    try {
      const actions = await fetchPlatformActions();
      if (get().userId === userId) set({ status: 'ready', actions });
    } catch {
      if (get().userId === userId) set({ status: 'error', actions: null });
    }
  },
}));

/**
 * What the signed-in user may open in Platform Settings. The shell asks again each
 * time it mounts (`fresh`); the account menu reuses the last answer for this user.
 */
export function usePlatformSettingsAccess({ fresh = false }: { fresh?: boolean } = {}): {
  status: PlatformSettingsAccessStatus;
  actions: PlatformActions | null;
} {
  // The session decides: a user not in the store yet is asked about all the same.
  const userId = useAuthStore((s) => s.user?.id ?? 'session');
  const status = usePlatformSettingsAccessStore((s) => s.status);
  const actions = usePlatformSettingsAccessStore((s) => s.actions);
  const knownUser = usePlatformSettingsAccessStore((s) => s.userId);
  const load = usePlatformSettingsAccessStore((s) => s.load);

  useEffect(() => {
    if (fresh || knownUser !== userId) void load(userId);
    // A fresh read once per mount; otherwise only when the user changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, fresh, load]);

  if (knownUser !== userId) return { status: 'checking', actions: null };
  return { status, actions };
}
