'use client';

import { useCallback, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { defaultLayerOn, type LayoutEntry } from './layouts';
import { hasMapsLayerChoice, mapsPath, parseMapsLayerIds } from './maps-route';
import { useMapLayers } from './use-map-layouts';

export function useMapsLayerParams() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { entries } = useMapLayers();

  const rawLayerIds = useMemo(() => parseMapsLayerIds(searchParams), [searchParams]);
  const hasLayerChoice = useMemo(() => hasMapsLayerChoice(searchParams), [searchParams]);
  const knownIds = useMemo(() => new Set(entries.map((e) => e.id)), [entries]);

  const layerIds = useMemo(
    () => rawLayerIds.filter((id) => knownIds.has(id)),
    [rawLayerIds, knownIds],
  );

  const replaceLayers = useCallback(
    (next: string[]) => {
      router.replace(mapsPath(workspaceId, next, { explicit: true }));
    },
    [router, workspaceId],
  );

  const isOn = useCallback(
    (entry: LayoutEntry) => entry.combinable && layerIds.includes(entry.id),
    [layerIds],
  );

  const setLayerOn = useCallback(
    (layerId: string, on: boolean) => {
      if (on) {
        if (layerIds.includes(layerId)) return;
        replaceLayers([...layerIds, layerId]);
        return;
      }
      replaceLayers(layerIds.filter((id) => id !== layerId));
    },
    [layerIds, replaceLayers],
  );

  const setLayersOn = useCallback(
    (ids: string[], on: boolean) => {
      if (on) {
        replaceLayers([...new Set([...layerIds, ...ids])]);
        return;
      }
      const drop = new Set(ids);
      replaceLayers(layerIds.filter((id) => !drop.has(id)));
    },
    [layerIds, replaceLayers],
  );

  const selectLayerExclusive = useCallback(
    (layerId: string) => {
      replaceLayers([layerId]);
    },
    [replaceLayers],
  );

  const defaultLayerIds = useMemo(
    () => entries.filter((e) => defaultLayerOn(e)).map((e) => e.id),
    [entries],
  );

  return {
    workspaceId,
    layerIds,
    rawLayerIds,
    /** The URL holds a layer choice, even an empty one: defaults do not apply. */
    hasLayerChoice,
    entries,
    isOn,
    setLayerOn,
    setLayersOn,
    selectLayerExclusive,
    replaceLayers,
    defaultLayerIds,
  };
}
