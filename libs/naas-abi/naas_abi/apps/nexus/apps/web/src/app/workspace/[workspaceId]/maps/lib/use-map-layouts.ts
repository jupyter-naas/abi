'use client';

import { useEffect, useMemo } from 'react';
import { MAPS_CUSTOM_DATASETS } from '@/lib/maps-custom-datasets';
import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { useWorkspaceStore } from '@/stores/workspace';
import { MAPS_DATASETS } from './datasets';
import { buildLayoutEntries, isLayoutOn, visibleEntries, type LayoutEntry } from './layouts';
import { useGraphMapLayers } from './use-graph-map-layers';

const CUSTOM_IDS: ReadonlySet<string> = new Set(MAPS_CUSTOM_DATASETS.map((d) => d.id));

/**
 * Every Maps layout of the current workspace. `entries` leaves out what an
 * admin hid in Settings → Maps; `all` keeps them (for that settings page).
 */
export function useMapLayouts() {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const graphLayers = useGraphMapLayers();
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const workspace = useMapsStore((s) => workspaceLayoutsOf(s, workspaceId));
  const overrides = useMapsStore((s) => s.overrides);
  const storeLoading = useMapsStore((s) => s.loading);
  const storeError = useMapsStore((s) => s.error);

  useEffect(() => {
    if (workspaceId) void loadLayouts(workspaceId);
  }, [workspaceId, loadLayouts]);

  const all = useMemo(
    () => buildLayoutEntries(MAPS_DATASETS, graphLayers.layers, workspace.layouts, { customIds: CUSTOM_IDS }),
    [graphLayers.layers, workspace.layouts],
  );
  const entries = useMemo(() => visibleEntries(all, workspace.hidden), [all, workspace.hidden]);
  const isOn = (entry: LayoutEntry) => isLayoutOn(entry, overrides);

  return {
    workspaceId,
    all,
    entries,
    hidden: workspace.hidden,
    canEdit: workspace.canEdit,
    workspaceLayouts: workspace.layouts,
    isOn,
    loading: graphLayers.loading || storeLoading,
    error: graphLayers.error || storeError,
  };
}
