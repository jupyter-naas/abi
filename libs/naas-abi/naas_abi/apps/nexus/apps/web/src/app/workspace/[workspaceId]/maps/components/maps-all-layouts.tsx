'use client';

import { useMemo, useRef, useState } from 'react';
import { Map } from 'lucide-react';
import Link from 'next/link';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { mapsIconMap } from '../lib/maps-icons';
import { layerPinColor } from '../lib/maps-layer-colors';
import { layoutPinSource } from '../lib/layout-sources';
import type { LayoutEntry } from '../lib/layouts';
import type { MapsFeedResult } from '../lib/maps-feed';
import { mapsDatasetPath } from '../lib/maps-route';
import type { MapsFeedView } from '../lib/maps-view';
import { useMapLayers } from '../lib/use-map-layouts';
import { MapsFeedCanvas } from './maps-feed-canvas';

/** Layers whose feed depends on the map bounds (live traffic). */
const VIEWPORT_BOUND_IDS = new Set(['flights', 'ais']);

type LayerStatus = { count: number } | { error: string };

/**
 * All layers on one map: every layer switched on in the sidebar, overlaid on
 * the basemap chosen from the map control.
 */
export function MapsAllLayers() {
  const { workspaceId, entries, isOn, loading } = useMapLayers();
  const onEntries = useMemo(() => entries.filter(isOn), [entries, isOn]);
  const [statuses, setStatuses] = useState<Record<string, LayerStatus>>({});
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
    const next: Record<string, LayerStatus> = {};
    results.forEach((result, index) => {
      const entry = layers[index];
      const color = layerPinColor(entry);
      if (result.status === 'fulfilled') {
        for (const pin of result.value.pins) {
          pins.push({
            ...pin,
            id: `${entry.id}:${pin.id}`,
            color,
            markerIcon: entry.icon,
          });
        }
        next[entry.id] = { count: result.value.pins.length };
      } else {
        next[entry.id] = { error: result.reason instanceof Error ? result.reason.message : 'Failed to load' };
      }
    });
    setStatuses(next);
    signal.throwIfAborted();
    return { pins, empty: pins.length === 0 };
  };

  const noLayers = onEntries.length === 0;

  return (
    <MapsFeedCanvas
      key={`${workspaceId}:${onKey}`}
      title="All layers"
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
      fetchPins={fetchPins}
      viewportBound={viewportBound}
      inspectable={inspectable && Boolean(workspaceId)}
      workspaceId={workspaceId ?? ''}
      legend={
        <div className="maps-legend">
          <span className="maps-legend__title">Layers</span>
          {noLayers ? (
            <p className="maps-legend__hint">None on — use the sidebar switches to add data.</p>
          ) : null}
          {onEntries.map((entry) => {
            const status = statuses[entry.id];
            const color = layerPinColor(entry);
            const Icon = mapsIconMap[entry.icon] ?? Map;
            return (
              <div key={entry.id} className="maps-legend__row" title={status && 'error' in status ? status.error : undefined}>
                <span className="maps-layer-marker maps-legend__layer-swatch" style={{ background: color }} aria-hidden>
                  <Icon size={11} strokeWidth={2.25} />
                </span>
                <Link href={mapsDatasetPath(workspaceId, entry.id)} className="min-w-0 flex-1 hover:underline">
                  {entry.title}
                </Link>
                <span className="pl-2 tabular-nums text-muted-foreground">
                  {!status ? '…' : 'error' in status ? 'error' : status.count}
                </span>
              </div>
            );
          })}
        </div>
      }
    />
  );
}

/** @deprecated use MapsAllLayers */
export const MapsAllLayouts = MapsAllLayers;
