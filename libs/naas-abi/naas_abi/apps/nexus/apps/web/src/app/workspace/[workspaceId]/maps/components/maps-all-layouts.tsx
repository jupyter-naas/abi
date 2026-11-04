'use client';

import { useMemo, useRef, useState } from 'react';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { layerPaintColor } from '../lib/maps-layer-colors';
import { layerFeedPins, styleLayerPin } from '../lib/maps-layer-class-styles';
import { layerCountsForFeedLoad } from '../lib/maps-layer-counts';
import { layoutPinSource } from '../lib/layout-sources';
import type { LayoutEntry } from '../lib/layouts';
import type { MapsFeedResult } from '../lib/maps-feed';
import type { MapsFeedView } from '../lib/maps-view';
import { useMapLayers } from '../lib/use-map-layouts';
import type { LayerLegendStatus } from './maps-active-layers-legend';
import { aggregateLayerLegendSublayers } from '../lib/maps-layer-legend-utils';
import { mapsLayerFeedLegendsFor } from '../lib/maps-layer-feed-legends';
import { saveLayerGeoJsonDebug } from '../lib/maps-layer-geojson-debug';
import { pinsToFeatureCollection } from '../lib/maps-pin-geojson';
import { useMapsStore } from '@/stores/maps';
import { resolveMapsFeedBasemapId } from '../lib/maps-effective-basemap';
import { useWorkspaceBasemaps } from '../lib/use-workspace-basemaps';
import { MapsFeedCanvas } from './maps-feed-canvas';

/** Layers whose feed depends on the map bounds (live traffic). */
const VIEWPORT_BOUND_IDS = new Set(['flights', 'ais']);

/**
 * All layers on one map: every layer switched on in the sidebar, overlaid on
 * the basemap chosen from the map control.
 */
export function MapsAllLayers({ layerIds }: { layerIds: string[] }) {
  const { workspaceId, entries, loading } = useMapLayers();
  const setLayerCounts = useMapsStore((s) => s.setLayerCounts);
  const allEntriesRef = useRef(entries);
  allEntriesRef.current = entries;
  const globalBasemapId = useMapsStore((s) => s.basemapId);
  const {
    defs: basemapPickerDefs,
    allDefs: basemapDefs,
    defaultBasemapId,
  } = useWorkspaceBasemaps(workspaceId);
  const feedBasemapId = workspaceId
    ? resolveMapsFeedBasemapId({
        layerIds,
        workspaceId,
        globalBasemapId,
        basemapDefs,
        defaultBasemapId,
        entries,
      })
    : globalBasemapId;
  const activeIds = useMemo(() => new Set(layerIds), [layerIds]);
  const onEntries = useMemo(
    () => entries.filter((e) => activeIds.has(e.id)),
    [entries, activeIds],
  );
  const [statuses, setStatuses] = useState<Record<string, LayerLegendStatus>>({});
  const onKey = onEntries.map((e) => e.id).join(',');
  const entriesRef = useRef<LayoutEntry[]>(onEntries);
  entriesRef.current = onEntries;
  const lastDisplayPinsByLayer = useRef<
    Map<string, { title: string; pins: MapsPinMarker[]; fetchedAt: string }>
  >(new Map());

  const viewportBound = onEntries.some((e) => VIEWPORT_BOUND_IDS.has(e.id));
  const inspectable = onEntries.some((e) => e.kind !== 'builtin');

  const fetchPins = async (signal: AbortSignal, view?: MapsFeedView): Promise<MapsFeedResult> => {
    const layers = entriesRef.current;
    if (!layers.length) {
      setStatuses({});
      signal.throwIfAborted();
      return { pins: [], empty: true };
    }
    // Layers of the same feed share one request; each keeps its own slice.
    const loads = new Map<string, Promise<MapsFeedResult>>();
    const results = await Promise.allSettled(
      layers.map(async (entry) => {
        // Stored layers read their object; others their feed.
        const key = entry.storagePath ?? entry.feedId ?? entry.id;
        let load = loads.get(key);
        if (!load) {
          const source = workspaceId ? layoutPinSource(entry, workspaceId) : null;
          load = source ? source(signal, view) : Promise.reject(new Error('Not available'));
          loads.set(key, load);
        }
        return load;
      }),
    );
    const pins: MapsPinMarker[] = [];
    const next: Record<string, LayerLegendStatus> = {};
    results.forEach((result, index) => {
      const entry = layers[index];
      if (result.status === 'fulfilled') {
        const layerPins = layerFeedPins(result.value.pins, entry.classLabels);
        const color = layerPaintColor(entry, layerPins);
        const fetchedAt = new Date().toISOString();
        const layerStyle = {
          id: entry.id,
          color,
          icon: entry.icon,
          ownIcon: entry.ownIcon,
          logoUrl: entry.kind === 'stored' ? entry.feedLogoUrl : undefined,
          feed: entry.feedId
            ? { id: entry.feedId, color: entry.feedColor ?? color, title: entry.feedTitle ?? entry.feedId }
            : { id: entry.id, color, title: entry.title },
        };
        const displayPins = layerPins.map((pin) => styleLayerPin(pin, layerStyle));
        lastDisplayPinsByLayer.current.set(entry.id, {
          title: entry.title,
          pins: displayPins,
          fetchedAt,
        });
        saveLayerGeoJsonDebug(
          entry.id,
          pinsToFeatureCollection(displayPins, {
            layerId: entry.id,
            layerTitle: entry.title,
            fetchedAt,
            featureCount: displayPins.length,
          }),
        );
        pins.push(...displayPins);
        next[entry.id] = {
          count: layerPins.length,
          sublayers: aggregateLayerLegendSublayers(layerPins, color),
        };
      } else {
        next[entry.id] = { error: result.reason instanceof Error ? result.reason.message : 'Failed to load' };
      }
    });
    setStatuses(next);
    const counts: Record<string, number> = {};
    for (const [key, load] of loads) {
      const loaded = await load.catch(() => null);
      if (!loaded) continue;
      Object.assign(counts, layerCountsForFeedLoad(allEntriesRef.current, key, loaded.pins));
    }
    setLayerCounts(counts);
    signal.throwIfAborted();
    return { pins, empty: pins.length === 0 };
  };

  const noLayers = onEntries.length === 0;
  const layerTitleById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of onEntries) map.set(entry.id, entry.title);
    return map;
  }, [onEntries]);
  const feedLegendsByLayerId = useMemo(
    () => mapsLayerFeedLegendsFor(onEntries.map((e) => e.id)),
    [onEntries],
  );

  return (
    <MapsFeedCanvas
      key={`${workspaceId}:${onKey}:${feedBasemapId}`}
      title="Active layers"
      basemapId={feedBasemapId}
      basemapDefs={basemapDefs}
      basemapPickerDefs={basemapPickerDefs}
      loadingLabel={
        noLayers
          ? loading
            ? 'Loading map layers…'
            : 'Basemap only'
          : `Loading ${onEntries.length} layer${onEntries.length === 1 ? '' : 's'}…`
      }
      readyMeta={(n) => `${n} points from ${onEntries.length} layer${onEntries.length === 1 ? '' : 's'}`}
      emptyTitle={noLayers ? 'No layer switched on' : 'No points right now'}
      emptyBody={
        noLayers
          ? 'Switch layers on in the sidebar to overlay data.'
          : 'The layers switched on returned no mappable points.'
      }
      emptyOverlay={!noLayers}
      layerTitleForPin={(pin) => {
        const colon = pin.id.indexOf(':');
        if (colon <= 0) return undefined;
        return layerTitleById.get(pin.id.slice(0, colon));
      }}
      fetchPins={fetchPins}
      viewportBound={viewportBound}
      inspectable={inspectable && Boolean(workspaceId)}
      workspaceId={workspaceId ?? ''}
      legendLayerIds={layerIds}
      legendStatuses={statuses}
      feedLegendsByLayerId={feedLegendsByLayerId}
    />
  );
}
