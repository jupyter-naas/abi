'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { WorkspaceMapLayout } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import { layoutsApi } from '@/app/workspace/[workspaceId]/maps/lib/layouts-api';

interface WorkspaceLayouts {
  layouts: WorkspaceMapLayout[];
  hidden: string[];
  canEdit: boolean;
}

export interface MapsState {
  /**
   * Which layouts are on the All layouts map (the sidebar switches, kept per
   * browser like Search). Only what differs from each layout's default.
   */
  overrides: Record<string, boolean>;
  setLayoutOn: (layoutId: string, on: boolean) => void;
  setLayoutsOn: (layoutIds: string[], on: boolean) => void;

  /** Settings → Maps: the workspace's own layouts and hidden layouts. */
  byWorkspace: Record<string, WorkspaceLayouts>;
  loading: boolean;
  error: string | null;
  loadLayouts: (workspaceId: string, force?: boolean) => Promise<void>;
  applyLayouts: (workspaceId: string, update: Partial<WorkspaceLayouts>) => void;
}

const EMPTY: WorkspaceLayouts = { layouts: [], hidden: [], canEdit: false };

export const useMapsStore = create<MapsState>()(
  persist(
    (set, get) => ({
      overrides: {},
      setLayoutOn: (layoutId, on) => set((state) => ({ overrides: { ...state.overrides, [layoutId]: on } })),
      setLayoutsOn: (layoutIds, on) =>
        set((state) => ({
          overrides: { ...state.overrides, ...Object.fromEntries(layoutIds.map((id) => [id, on])) },
        })),

      byWorkspace: {},
      loading: false,
      error: null,
      loadLayouts: async (workspaceId, force = false) => {
        if (!force && get().byWorkspace[workspaceId]) return;
        set({ loading: true, error: null });
        try {
          const data = await layoutsApi.list(workspaceId);
          set((state) => ({
            byWorkspace: {
              ...state.byWorkspace,
              [workspaceId]: { layouts: data.layouts, hidden: data.hidden, canEdit: data.can_edit },
            },
            loading: false,
          }));
        } catch (error) {
          set({ loading: false, error: error instanceof Error ? error.message : 'Could not load map layouts' });
        }
      },
      applyLayouts: (workspaceId, update) =>
        set((state) => ({
          byWorkspace: {
            ...state.byWorkspace,
            [workspaceId]: { ...(state.byWorkspace[workspaceId] ?? EMPTY), ...update },
          },
        })),
    }),
    { name: 'nexus-maps', partialize: (state) => ({ overrides: state.overrides }) },
  ),
);

export function workspaceLayoutsOf(state: MapsState, workspaceId: string | null): WorkspaceLayouts {
  return (workspaceId && state.byWorkspace[workspaceId]) || EMPTY;
}
