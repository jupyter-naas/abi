'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { DEFAULT_BASEMAP_ID, normalizeBasemapId } from '@/app/workspace/[workspaceId]/maps/lib/maps-basemaps';
import type { WorkspaceMapLayout } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import { layoutsApi } from '@/app/workspace/[workspaceId]/maps/lib/layouts-api';

interface WorkspaceLayouts {
  layouts: WorkspaceMapLayout[];
  hidden: string[];
  canEdit: boolean;
}

export interface MapsState {
  /** Which layers are on the All layers map (per browser, like Search). */
  overrides: Record<string, boolean>;
  setLayerOn: (layerId: string, on: boolean) => void;
  setLayersOn: (layerIds: string[], on: boolean) => void;
  /** @deprecated use setLayerOn */
  setLayoutOn: (layerId: string, on: boolean) => void;
  /** @deprecated use setLayersOn */
  setLayoutsOn: (layerIds: string[], on: boolean) => void;
  /** Background tiles; switched from the map (Leaflet layers control). */
  basemapId: string;
  setBasemap: (basemapId: string) => void;

  /** Settings → Maps: workspace SPARQL layers and hidden ids. */
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
      setLayerOn: (layerId, on) => set((state) => ({ overrides: { ...state.overrides, [layerId]: on } })),
      setLayersOn: (layerIds, on) =>
        set((state) => ({
          overrides: { ...state.overrides, ...Object.fromEntries(layerIds.map((id) => [id, on])) },
        })),
      setLayoutOn: (layerId, on) => get().setLayerOn(layerId, on),
      setLayoutsOn: (layerIds, on) => get().setLayersOn(layerIds, on),
      basemapId: DEFAULT_BASEMAP_ID,
      setBasemap: (basemapId) => set({ basemapId: normalizeBasemapId(basemapId) }),

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
          set({ loading: false, error: error instanceof Error ? error.message : 'Could not load map layers' });
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
    { name: 'nexus-maps', partialize: (state) => ({ overrides: state.overrides, basemapId: state.basemapId }) },
  ),
);

export function workspaceLayoutsOf(state: MapsState, workspaceId: string | null): WorkspaceLayouts {
  return (workspaceId && state.byWorkspace[workspaceId]) || EMPTY;
}
