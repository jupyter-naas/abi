'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { FALLBACK_BASEMAP_ID } from '@/app/workspace/[workspaceId]/maps/lib/maps-basemaps';
import type { MapsGroupBy } from '@/app/workspace/[workspaceId]/maps/lib/maps-country-cluster';
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
  /** Feeds switched off in Settings → Maps (all their layers hidden). */
  hiddenFeeds: string[];
  /** Default pin / group-by-country color of layers without a record (built-in, graph). */
  colors: Record<string, string>;
  basemaps: WorkspaceBasemap[];
  hiddenBasemaps: string[];
  defaultBasemapId: string;
  canEdit: boolean;
}

export interface MapsState {
  /** Background tiles; switched from the map (Leaflet layers control). */
  basemapId: string;
  setBasemap: (basemapId: string) => void;
  /** Data points per layer id (and `feed:<id>` per feed) from the last map load. */
  layerCounts: Record<string, number>;
  setLayerCounts: (counts: Record<string, number>) => void;
  /** Map grouping when zoomed out: badges per layer feed (default), per layer, or off. */
  groupBy: MapsGroupBy;
  setGroupBy: (by: MapsGroupBy) => void;
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
  hiddenFeeds: [],
  colors: {},
  basemaps: [],
  hiddenBasemaps: [],
  defaultBasemapId: FALLBACK_BASEMAP_ID,
  canEdit: false,
};

const pendingCatalogs = new Map<string, Promise<void>>();

export const useMapsStore = create<MapsState>()(
  persist(
    (set, get) => {
      const fetchCatalog = async (workspaceId: string): Promise<void> => {
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
                hiddenFeeds: list(data.hidden_feeds),
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
      };
      return {
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

        byWorkspace: {},
        loading: false,
        error: null,
        loadLayouts: (workspaceId, force = false) => {
          if (!force && get().byWorkspace[workspaceId]) return Promise.resolve();
          // Every component on the page asks at mount: one request per workspace.
          const pending = pendingCatalogs.get(workspaceId);
          if (pending) return pending;
          const load = fetchCatalog(workspaceId).finally(() => pendingCatalogs.delete(workspaceId));
          pendingCatalogs.set(workspaceId, load);
          return load;
        },
        applyLayouts: (workspaceId, update) =>
          set((state) => ({
            byWorkspace: {
              ...state.byWorkspace,
              [workspaceId]: { ...(state.byWorkspace[workspaceId] ?? EMPTY), ...update },
            },
          })),
      };
    },
    {
      name: 'nexus-maps',
      partialize: (state) => ({
        basemapId: state.basemapId,
        groupBy: state.groupBy,
      }),
    },
  ),
);

export function workspaceLayoutsOf(state: MapsState, workspaceId: string | null): WorkspaceLayouts {
  return (workspaceId && state.byWorkspace[workspaceId]) || EMPTY;
}
