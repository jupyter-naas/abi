'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { authFetch, useAuthStore } from '@/stores/auth';
import { fetchAnalyticsAccess, type Fetcher } from '@/components/analytics/api';
import { analyticsScopeKey, type AnalyticsScope } from '@/components/analytics/scope';
import type { AnalyticsAccess } from '@/components/analytics/types';

export type AnalyticsAccessStatus = 'checking' | 'ready' | 'error';

export interface AnalyticsAccessEntry {
  status: AnalyticsAccessStatus;
  access: AnalyticsAccess | null;
}

export interface AnalyticsAccessState {
  /** The user the entries were read for: another user starts from nothing. */
  userId: string | null;
  entries: Record<string, AnalyticsAccessEntry>;
  pending: Record<string, Promise<void>>;
  load: (userId: string, scope: AnalyticsScope) => Promise<void>;
}

/**
 * What the caller may read of each scope's analytics (`GET {base}/analytics/access`), one
 * shared request per user and scope: the settings nav, the layout and the page all ask.
 * A failed read keeps the last answer for that scope.
 */
export function createAnalyticsAccessStore(fetcher: Fetcher = authFetch) {
  return create<AnalyticsAccessState>((set, get) => ({
    userId: null,
    entries: {},
    pending: {},
    load: (userId, scope) => {
      const key = analyticsScopeKey(scope);
      if (get().userId !== userId) set({ userId, entries: {}, pending: {} });
      const inFlight = get().pending[key];
      if (inFlight) return inFlight;
      const known = get().entries[key]?.access ?? null;
      set((s) => ({ entries: { ...s.entries, [key]: { status: known ? 'ready' : 'checking', access: known } } }));
      const read = async () => {
        try {
          const access = await fetchAnalyticsAccess(scope, fetcher);
          if (get().userId === userId) {
            set((s) => ({ entries: { ...s.entries, [key]: { status: 'ready', access } } }));
          }
        } catch {
          if (get().userId === userId) {
            const kept = get().entries[key]?.access ?? null;
            set((s) => ({ entries: { ...s.entries, [key]: { status: kept ? 'ready' : 'error', access: kept } } }));
          }
        }
      };
      const promise: Promise<void> = read().finally(() => {
        if (get().pending[key] === promise) {
          set((s) => {
            const rest = { ...s.pending };
            delete rest[key];
            return { pending: rest };
          });
        }
      });
      set((s) => ({ pending: { ...s.pending, [key]: promise } }));
      return promise;
    },
  }));
}

export const useAnalyticsAccessStore = createAnalyticsAccessStore();

const CHECKING: AnalyticsAccessEntry = { status: 'checking', access: null };

/**
 * What the caller may read of a scope's analytics; `checking` until the first answer.
 * Pass null while the scope is not known (nothing is asked). `refresh` asks again on mount
 * even when an answer is known (the Analytics page: a timezone or a policy changed since),
 * keeping the last answer meanwhile.
 */
export function useAnalyticsAccess(
  scope: AnalyticsScope | null,
  { refresh = false }: { refresh?: boolean } = {}
): AnalyticsAccessEntry {
  const userId = useAuthStore((s) => s.user?.id ?? 'session');
  const key = scope ? analyticsScopeKey(scope) : null;
  const knownUser = useAnalyticsAccessStore((s) => s.userId);
  const entry = useAnalyticsAccessStore((s) => (key ? s.entries[key] : undefined));
  const load = useAnalyticsAccessStore((s) => s.load);

  useEffect(() => {
    if (!scope || !key) return;
    const state = useAnalyticsAccessStore.getState();
    const current = state.userId === userId ? state.entries[key] : undefined;
    if (refresh || !current || current.status === 'error') void load(userId, scope);
    // The scope is read through its key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, key, load, refresh]);

  if (!key || knownUser !== userId || !entry) return CHECKING;
  return entry;
}

/** Whether the scope's Analytics entry is shown: only once `can_read` is known true. */
export function useReadsAnalytics(scope: AnalyticsScope | null): boolean {
  const { access } = useAnalyticsAccess(scope);
  return access?.can_read === true;
}
