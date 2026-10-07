'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ScopeResult, SearchScope } from '@/lib/search-scopes';
import { runScope } from '@/lib/search-providers';

export interface ScopeRun {
  status: 'loading' | 'done' | 'error';
  result?: ScopeResult;
  error?: string;
}

export const scopeRunKey = (workspaceId: string, scopeId: string, q: string, limit: number) => `${workspaceId}|${scopeId}|${limit}|${q.trim()}`;
const MAX_RUNS = 200;

/**
 * Which scopes the "All" view searches (the sidebar toggles, kept per browser)
 * and the latest results per scope, shared by the page and the sidebar counts.
 */
interface SearchScopesState {
  /** Only what differs from each scope's default (`isScopeOn`). */
  overrides: Record<string, boolean>;
  setScopeOn: (scopeId: string, on: boolean) => void;
  runs: Record<string, ScopeRun>;
  run: (workspaceId: string, scope: SearchScope, q: string, limit: number, force?: boolean) => Promise<void>;
  /** Drop every cached run of a scope (its settings changed). */
  invalidate: (scopeId: string) => void;
  /** Bumped by `refreshAll`: views that fetch on their own refetch when it changes. */
  nonce: number;
  /** Drop every run, so each view searches again (after the server cache was cleared). */
  refreshAll: () => void;
}

export const useSearchScopesStore = create<SearchScopesState>()(
  persist(
    (set, get) => ({
      overrides: {},
      setScopeOn: (scopeId, on) => set(state => ({ overrides: { ...state.overrides, [scopeId]: on } })),
      runs: {},
      nonce: 0,
      refreshAll: () => set(state => ({ runs: {}, nonce: state.nonce + 1 })),
      invalidate: (scopeId) => set(state => ({
        runs: Object.fromEntries(Object.entries(state.runs).filter(([key]) => key.split('|')[1] !== scopeId)),
      })),
      run: async (workspaceId, scope, q, limit, force = false) => {
        const key = scopeRunKey(workspaceId, scope.id, q, limit);
        const existing = get().runs[key];
        if (!force && existing && existing.status !== 'error') return;
        set(state => {
          const keys = Object.keys(state.runs);
          const runs = keys.length > MAX_RUNS ? Object.fromEntries(keys.slice(-MAX_RUNS / 2).map(k => [k, state.runs[k]!])) : { ...state.runs };
          runs[key] = { status: 'loading', result: existing?.result };
          return { runs };
        });
        try {
          const result = await runScope(scope, q.trim(), { workspaceId, limit });
          set(state => ({ runs: { ...state.runs, [key]: { status: 'done', result } } }));
        } catch (error) {
          set(state => ({ runs: { ...state.runs, [key]: { status: 'error', error: error instanceof Error ? error.message : 'Search failed' } } }));
        }
      },
    }),
    { name: 'nexus-search-scopes', partialize: state => ({ overrides: state.overrides }) },
  ),
);
