'use client';

import { useEffect, useMemo, useState } from 'react';
import { MAPS_CUSTOM_DATASETS } from '@/lib/maps-custom-datasets';
import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { useWorkspaceStore } from '@/stores/workspace';
import { MAPS_DATASETS } from './datasets';
import { normalizeBasemapId } from './maps-basemaps';
import { buildLayoutEntries, isLayerOn, visibleEntries, type LayoutEntry } from './layouts';
import {
  loadImportedMapLayers,
  subscribeImportedLayers,
} from './maps-imported-layers';
import {
  loadCustomLayerGroups,
  subscribeCustomLayerGroups,
  type CustomLayerGroup,
} from './maps-layer-groups';
import {
  getWorkspaceLayerGroupId,
  subscribeWorkspaceLayerMeta,
} from './maps-workspace-layer-meta';
import { useGraphMapLayers } from './use-graph-map-layers';

const CUSTOM_IDS: ReadonlySet<string> = new Set(MAPS_CUSTOM_DATASETS.map((d) => d.id));

/**
 * Every Maps data layer for the current workspace. `entries` omits layers hidden
 * in Settings → Maps; `all` includes them (for that settings page).
 */
export function useMapLayers() {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const graphLayers = useGraphMapLayers();
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const workspace = useMapsStore((s) => workspaceLayoutsOf(s, workspaceId));
  const overrides = useMapsStore((s) => s.overrides);
  const storedBasemap = useMapsStore((s) => s.basemapId);
  const storeLoading = useMapsStore((s) => s.loading);
  const storeError = useMapsStore((s) => s.error);

  useEffect(() => {
    if (workspaceId) void loadLayouts(workspaceId);
  }, [workspaceId, loadLayouts]);

  const [importedLayers, setImportedLayers] = useState(() =>
    workspaceId ? loadImportedMapLayers(workspaceId) : [],
  );

  useEffect(() => {
    if (!workspaceId) {
      setImportedLayers([]);
      return;
    }
    setImportedLayers(loadImportedMapLayers(workspaceId));
    return subscribeImportedLayers(() => {
      setImportedLayers(loadImportedMapLayers(workspaceId));
    });
  }, [workspaceId]);

  const [customLayerGroups, setCustomLayerGroups] = useState<CustomLayerGroup[]>(() =>
    workspaceId ? loadCustomLayerGroups(workspaceId) : [],
  );

  useEffect(() => {
    if (!workspaceId) {
      setCustomLayerGroups([]);
      return;
    }
    setCustomLayerGroups(loadCustomLayerGroups(workspaceId));
    return subscribeCustomLayerGroups(() => {
      setCustomLayerGroups(loadCustomLayerGroups(workspaceId));
    });
  }, [workspaceId]);

  const [workspaceMetaVersion, setWorkspaceMetaVersion] = useState(0);

  useEffect(() => {
    if (!workspaceId) return;
    return subscribeWorkspaceLayerMeta(() => {
      setWorkspaceMetaVersion((v) => v + 1);
    });
  }, [workspaceId]);

  const all = useMemo(
    () =>
      buildLayoutEntries(MAPS_DATASETS, graphLayers.layers, workspace.layouts, {
        customIds: CUSTOM_IDS,
        importedLayers: importedLayers.map((layer) => ({
          ...layer,
          groupId: layer.groupId ?? 'custom',
        })),
        workspaceLayerGroup: workspaceId
          ? (layoutId) => getWorkspaceLayerGroupId(workspaceId, layoutId)
          : undefined,
      }),
    [graphLayers.layers, workspace.layouts, importedLayers, workspaceId, workspaceMetaVersion],
  );
  const entries = useMemo(() => visibleEntries(all, workspace.hidden), [all, workspace.hidden]);
  const isOn = (entry: LayoutEntry) => isLayerOn(entry, overrides);
  const basemapId = normalizeBasemapId(storedBasemap);

  return {
    workspaceId,
    all,
    entries,
    basemapId,
    hidden: workspace.hidden,
    customLayerGroups,
    canEdit: workspace.canEdit,
    workspaceLayouts: workspace.layouts,
    isOn,
    loading: graphLayers.loading || storeLoading,
    error: graphLayers.error || storeError,
  };
}

/** @deprecated use useMapLayers */
export const useMapLayouts = useMapLayers;
