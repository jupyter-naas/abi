'use client';

import { create } from 'zustand';

/**
 * Shell-owned status footer: page-level Refresh handler + optional coding
 * overrides. User and Business Workspace come from auth/workspace stores.
 * Slides and Code fill repo / branch / Coder when relevant.
 */
interface PlatformStatusState {
  onRefresh: (() => void) | null;
  refreshTitle: string;
  refreshing: boolean;
  /** Forgejo/git repo id when a page knows a better value than route defaults. */
  repoOverride: string | null;
  branchOverride: string | null;
  coderWorkspaceOverride: string | null;
  coderPhaseOverride: string | null;
  coderStatusOverride: string | null;
  coderUiUrlOverride: string | null;
  dirtyOverride: boolean | null;
  setRefresh: (opts: { onRefresh: (() => void) | null; title?: string }) => void;
  setRefreshing: (refreshing: boolean) => void;
  clearRefresh: () => void;
  setCodingOverrides: (meta: {
    repo?: string | null;
    branch?: string | null;
    coderWorkspace?: string | null;
    coderPhase?: string | null;
    coderStatus?: string | null;
    coderUiUrl?: string | null;
    dirty?: boolean | null;
  }) => void;
  clearCodingOverrides: () => void;
}

export const usePlatformStatusStore = create<PlatformStatusState>((set) => ({
  onRefresh: null,
  refreshTitle: 'Refresh',
  refreshing: false,
  repoOverride: null,
  branchOverride: null,
  coderWorkspaceOverride: null,
  coderPhaseOverride: null,
  coderStatusOverride: null,
  coderUiUrlOverride: null,
  dirtyOverride: null,
  setRefresh: ({ onRefresh, title }) =>
    set({
      onRefresh,
      refreshTitle: title ?? 'Refresh',
    }),
  setRefreshing: (refreshing) => set({ refreshing }),
  clearRefresh: () =>
    set({
      onRefresh: null,
      refreshTitle: 'Refresh',
      refreshing: false,
    }),
  setCodingOverrides: (meta) =>
    set((state) => ({
      repoOverride: meta.repo !== undefined ? meta.repo : state.repoOverride,
      branchOverride: meta.branch !== undefined ? meta.branch : state.branchOverride,
      coderWorkspaceOverride:
        meta.coderWorkspace !== undefined
          ? meta.coderWorkspace
          : state.coderWorkspaceOverride,
      coderPhaseOverride:
        meta.coderPhase !== undefined ? meta.coderPhase : state.coderPhaseOverride,
      coderStatusOverride:
        meta.coderStatus !== undefined ? meta.coderStatus : state.coderStatusOverride,
      coderUiUrlOverride:
        meta.coderUiUrl !== undefined ? meta.coderUiUrl : state.coderUiUrlOverride,
      dirtyOverride: meta.dirty !== undefined ? meta.dirty : state.dirtyOverride,
    })),
  clearCodingOverrides: () =>
    set({
      repoOverride: null,
      branchOverride: null,
      coderWorkspaceOverride: null,
      coderPhaseOverride: null,
      coderStatusOverride: null,
      coderUiUrlOverride: null,
      dirtyOverride: null,
    }),
}));
