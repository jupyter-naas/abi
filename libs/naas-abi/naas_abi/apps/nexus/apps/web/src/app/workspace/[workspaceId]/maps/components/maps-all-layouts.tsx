'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { layoutPinSource } from '../lib/layout-sources';
import type { LayoutEntry } from '../lib/layouts';
import type { MapsFeedResult } from '../lib/maps-feed';
import { mapsDatasetPath } from '../lib/maps-route';
import type { MapsFeedView } from '../lib/maps-view';
import { useMapLayouts } from '../lib/use-map-layouts';
import { MapsFeedCanvas } from './maps-feed-canvas';

/** Layouts whose feed depends on the map bounds (live traffic). */
const VIEWPORT_BOUND_IDS = new Set(['flights', 'ais']);

type LayerStatus = { count: number } | { error: string };

/**
 * The All layouts map: every layout switched on in the sidebar, overlaid on
 * one canvas. Each layout loads on its own (a slow or failing one does not
 * blank the others) and pins keep their layout's colour; the legend shows
 * what each contributed.
 */
export function MapsAllLayouts() {
  const { workspaceId, entries, isOn, loading, basemapId } = useMapLayouts();
  const onEntries = useMemo(() => entries.filter(isOn), [entries, isOn]);
  const [statuses, setStatuses] = useState<Record<string, LayerStatus>>({});
  const onKey = onEntries.map((e) => e.id).join(',');
  const entriesRef = useRef<LayoutEntry[]>(onEntries);
  entriesRef.current = onEntries;

  const viewportBound = onEntries.some((e) => VIEWPORT_BOUND_IDS.has(e.id));
  const inspectable = onEntries.some((e) => e.kind !== 'builtin');

  const fetchPins = async (signal: AbortSignal, view?: MapsFeedView): Promise<MapsFeedResult> => {
    const layers = entriesRef.current;
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
      if (result.status === 'fulfilled') {
        // Ids are only unique within a feed: prefix them with the layout.
        for (const pin of result.value.pins) pins.push({ ...pin, id: `${entry.id}:${pin.id}` });
        next[entry.id] = { count: result.value.pins.length };
      } else {
        next[entry.id] = { error: result.reason instanceof Error ? result.reason.message : 'Failed to load' };
      }
    });
    setStatuses(next);
    signal.throwIfAborted();
    return { pins, empty: pins.length === 0 };
  };

  if (loading && !onEntries.length) return <div className="maps-empty">Loading map layouts…</div>;
  if (!onEntries.length) {
    return (
      <div className="maps-empty">
        <h3>No layout switched on</h3>
        <p>Switch layouts on in the sidebar to overlay them here.</p>
      </div>
    );
  }

  return (
    <MapsFeedCanvas
      key={`${workspaceId}:${basemapId}:${onKey}`}
      basemapId={basemapId}
      title="All layouts"
      loadingLabel={`Loading ${onEntries.length} layout${onEntries.length === 1 ? '' : 's'}…`}
      readyMeta={(n) => `${n} points from ${onEntries.length} layout${onEntries.length === 1 ? '' : 's'}`}
      emptyTitle="No points right now"
      emptyBody="The layouts switched on returned no mappable points."
      fetchPins={fetchPins}
      viewportBound={viewportBound}
      inspectable={inspectable && Boolean(workspaceId)}
      workspaceId={workspaceId ?? ''}
      legend={
        <div className="maps-legend">
          <span className="maps-legend__title">Layouts</span>
          {onEntries.map((entry) => {
            const status = statuses[entry.id];
            return (
              <div key={entry.id} className="maps-legend__row" title={status && 'error' in status ? status.error : undefined}>
                <Link href={mapsDatasetPath(workspaceId, entry.id)} className="hover:underline">
                  {entry.title}
                </Link>
                <span className="ml-auto pl-2 tabular-nums text-muted-foreground">
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
