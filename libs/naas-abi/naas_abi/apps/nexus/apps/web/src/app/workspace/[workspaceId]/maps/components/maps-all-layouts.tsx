'use client';

import { useMemo, useRef, useState } from 'react';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { layerPinColor } from '../lib/maps-layer-colors';
import { layoutPinSource } from '../lib/layout-sources';
import type { LayoutEntry } from '../lib/layouts';
import type { MapsFeedResult } from '../lib/maps-feed';
import type { MapsFeedView } from '../lib/maps-view';
import { useMapLayers } from '../lib/use-map-layouts';
import type { LayerLegendStatus } from './maps-active-layers-legend';
import { aggregateLayerLegendSublayers } from '../lib/maps-layer-legend-utils';
import { mapsLayerFeedLegendsFor } from '../lib/maps-layer-feed-legends';
import { MapsFeedCanvas } from './maps-feed-canvas';

/** Layers whose feed depends on the map bounds (live traffic). */
const VIEWPORT_BOUND_IDS = new Set(['flights', 'ais']);

/**
 * All layers on one map: every layer switched on in the sidebar, overlaid on
 * the basemap chosen from the map control.
 */
export function MapsAllLayers({ layerIds }: { layerIds: string[] }) {
  const { workspaceId, entries, loading } = useMapLayers();
  const activeIds = useMemo(() => new Set(layerIds), [layerIds]);
  const onEntries = useMemo(
    () => entries.filter((e) => activeIds.has(e.id)),
    [entries, activeIds],
  );
  const [statuses, setStatuses] = useState<Record<string, LayerLegendStatus>>({});
  const onKey = onEntries.map((e) => e.id).join(',');
  const entriesRef = useRef<LayoutEntry[]>(onEntries);
  entriesRef.current = onEntries;

  const viewportBound = onEntries.some((e) => VIEWPORT_BOUND_IDS.has(e.id));
  const inspectable = onEntries.some((e) => e.kind !== 'builtin');

  const fetchPins = async (signal: AbortSignal, view?: MapsFeedView): Promise<MapsFeedResult> => {
    const layers = entriesRef.current;
    if (!layers.length) {
      setStatuses({});
      signal.throwIfAborted();
      return { pins: [], empty: true };
    }
    const results = await Promise.allSettled(
      layers.map(async (entry) => {
        const source = workspaceId ? layoutPinSource(entry, workspaceId) : null;
        if (!source) throw new Error('Not available');
        return source(signal, view);
      }),
    );
    const pins: MapsPinMarker[] = [];
    const next: Record<string, LayerLegendStatus> = {};
    results.forEach((result, index) => {
      const entry = layers[index];
      const color = layerPinColor(entry);
      if (result.status === 'fulfilled') {
        const layerPins = result.value.pins;
        for (const pin of layerPins) {
          pins.push({
            ...pin,
            id: `${entry.id}:${pin.id}`,
            color,
            markerIcon: entry.icon,
          });
        }
        next[entry.id] = {
          count: layerPins.length,
          sublayers: aggregateLayerLegendSublayers(layerPins),
        };
      } else {
        next[entry.id] = { error: result.reason instanceof Error ? result.reason.message : 'Failed to load' };
      }
    });
    setStatuses(next);
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
      key={`${workspaceId}:${onKey}`}
      title="Active layers"
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

/** @deprecated use MapsAllLayers */
export const MapsAllLayouts = MapsAllLayers;
