'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { useWorkspaceStore } from '@/stores/workspace';
import { MAPS_DATASETS } from './datasets';
import { buildLayoutEntries, isLayerOn, visibleEntries, type LayoutEntry } from './layouts';
import { layoutsApi } from './layouts-api';
import {
  loadImportedMapLayers,
  relabelImportedLayerGroups,
  subscribeImportedLayers,
} from './maps-imported-layers';
import {
  DEFAULT_LAYER_GROUP,
  layerGroupKey,
  layerGroupLabels,
  layoutGroup,
  takeLegacyLocalGroups,
} from './maps-layer-groups';
import { useGraphMapLayers } from './use-graph-map-layers';

/**
 * Every Maps data layer for the current workspace. `entries` omits layers hidden
 * in Settings → Maps, and those of feeds switched off there; `all` includes them
 * (for that settings page).
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
  const catalogLoaded = useMapsStore((s) => Boolean(workspaceId && s.byWorkspace[workspaceId]));

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

  // Groups older versions kept in this browser move onto the records once the
  // catalog is loaded (layer records need an admin; imported layers are local).
  useEffect(() => {
    if (!workspaceId || storeLoading || !catalogLoaded) return;
    const legacy = takeLegacyLocalGroups(workspaceId);
    relabelImportedLayerGroups(workspaceId, legacy.labels);
    if (!workspace.canEdit) return;
    const custom = layerGroupKey(DEFAULT_LAYER_GROUP);
    const moves = workspace.layouts.filter(
      (feed) =>
        !feed.shared_from
        && legacy.layers[feed.id]
        && layerGroupKey(layoutGroup(feed)) === custom,
    );
    if (!moves.length) return;
    void Promise.allSettled(
      moves.map(({ id, ...feed }) =>
        layoutsApi.save(workspaceId, id, { ...feed, group: legacy.layers[id] }),
      ),
    ).then(() => loadLayouts(workspaceId, true));
  }, [workspaceId, storeLoading, catalogLoaded, workspace.canEdit, workspace.layouts, loadLayouts]);

  const all = useMemo(
    () =>
      buildLayoutEntries(MAPS_DATASETS, graphLayers.layers, workspace.layouts, {
        colors: workspace.colors,
        // The API gives every feed a layer; fall back to one per feed until it has.
        feedLayers: workspace.feedLayers.length ? workspace.feedLayers : undefined,
        importedLayers: importedLayers.map((layer) => ({
          ...layer,
          group: layer.group ?? DEFAULT_LAYER_GROUP,
        })),
      }),
    [graphLayers.layers, workspace.layouts, workspace.feedLayers, workspace.colors, importedLayers],
  );
  const entries = useMemo(
    () => visibleEntries(all, workspace.hidden, workspace.hiddenFeeds),
    [all, workspace.hidden, workspace.hiddenFeeds],
  );
  // Every group label in use (hidden layers included), for the group pickers.
  const layerGroups = useMemo(() => layerGroupLabels(all.map((entry) => entry.group)), [all]);
  const isOn = (entry: LayoutEntry) => isLayerOn(entry, overrides);
  const basemapId = storedBasemap;

  return {
    workspaceId,
    all,
    entries,
    basemapId,
    hidden: workspace.hidden,
    hiddenFeeds: workspace.hiddenFeeds,
    layerColors: workspace.colors,
    layerGroups,
    canEdit: workspace.canEdit,
    workspaceLayouts: workspace.layouts,
    feedLayers: workspace.feedLayers,
    isOn,
    loading: graphLayers.loading || storeLoading,
    error: graphLayers.error || storeError,
  };
}

/** @deprecated use useMapLayers */
export const useMapLayouts = useMapLayers;
