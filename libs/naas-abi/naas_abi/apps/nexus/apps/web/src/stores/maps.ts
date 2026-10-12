'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { FALLBACK_BASEMAP_ID } from '@/app/workspace/[workspaceId]/maps/lib/maps-basemaps';
import type { MapsGroupArea, MapsGroupBy } from '@/app/workspace/[workspaceId]/maps/lib/maps-country-cluster';
import type { WorkspaceFeedLayer, WorkspaceMapLayout } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import { mapsCatalogApi, type WorkspaceBasemap } from '@/app/workspace/[workspaceId]/maps/lib/basemaps-api';

function list<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

/** The workspace Maps catalog (`/api/maps/catalog`), shared by Settings and the map. */
export interface WorkspaceLayouts {
  /** Feeds (data sources; the API calls them layouts). */
  layouts: WorkspaceMapLayout[];
  /** Layers drawn from those feeds; a feed has one at least. */
  feedLayers: WorkspaceFeedLayer[];
  hidden: string[];
  /** Default pin / group-by-country color of layers without a record (built-in, graph). */
  colors: Record<string, string>;
  basemaps: WorkspaceBasemap[];
  hiddenBasemaps: string[];
  defaultBasemapId: string;
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
  /** Data points per layer id (and `feed:<id>` per feed) from the last map load. */
  layerCounts: Record<string, number>;
  setLayerCounts: (counts: Record<string, number>) => void;
  /** Map grouping when zoomed out: badges per layer feed (default), per layer, or off. */
  groupBy: MapsGroupBy;
  setGroupBy: (by: MapsGroupBy) => void;
  /** Group by country (default) or by continent. */
  groupArea: MapsGroupArea;
  setGroupArea: (area: MapsGroupArea) => void;

  /** Settings → Maps: layer records, basemaps, hidden ids and layer colors. */
  byWorkspace: Record<string, WorkspaceLayouts>;
  loading: boolean;
  error: string | null;
  loadLayouts: (workspaceId: string, force?: boolean) => Promise<void>;

  applyLayouts: (workspaceId: string, update: Partial<WorkspaceLayouts>) => void;
}

const EMPTY: WorkspaceLayouts = {
  layouts: [],
  feedLayers: [],
  hidden: [],
  colors: {},
  basemaps: [],
  hiddenBasemaps: [],
  defaultBasemapId: FALLBACK_BASEMAP_ID,
  canEdit: false,
};

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
      basemapId: FALLBACK_BASEMAP_ID,
      // Normalized against the workspace catalog where it is drawn.
      setBasemap: (basemapId) => set({ basemapId: basemapId || FALLBACK_BASEMAP_ID }),
      layerCounts: {},
      setLayerCounts: (counts) => {
        const current = get().layerCounts;
        if (Object.entries(counts).every(([id, n]) => current[id] === n)) return;
        set({ layerCounts: { ...current, ...counts } });
      },
      groupBy: 'feed',
      setGroupBy: (groupBy) => set({ groupBy }),
      groupArea: 'country',
      setGroupArea: (groupArea) => set({ groupArea }),

      byWorkspace: {},
      loading: false,
      error: null,
      loadLayouts: async (workspaceId, force = false) => {
        if (!force && get().byWorkspace[workspaceId]) return;
        set({ loading: true, error: null });
        try {
          const data = await mapsCatalogApi.get(workspaceId);
          set((state) => ({
            byWorkspace: {
              ...state.byWorkspace,
              [workspaceId]: {
                // A malformed or partial response degrades to an empty catalog.
                layouts: list(data.layouts),
                feedLayers: list(data.feed_layers),
                hidden: list(data.hidden_layouts),
                colors: data.layer_colors ?? {},
                basemaps: list(data.basemaps),
                hiddenBasemaps: list(data.hidden_basemaps),
                defaultBasemapId: data.default_basemap_id ?? EMPTY.defaultBasemapId,
                canEdit: data.can_edit === true,
              },
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
    {
      name: 'nexus-maps',
      partialize: (state) => ({
        overrides: state.overrides,
        basemapId: state.basemapId,
        groupBy: state.groupBy,
        groupArea: state.groupArea,
      }),
    },
  ),
);

export function workspaceLayoutsOf(state: MapsState, workspaceId: string | null): WorkspaceLayouts {
  return (workspaceId && state.byWorkspace[workspaceId]) || EMPTY;
}
