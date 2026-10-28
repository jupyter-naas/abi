'use client';

import { CONFLICT_SEVERITY_COLOR, CONFLICT_SITES } from '../lib/conflict-sites';
import { conflictFeedLegend } from '../lib/maps-layer-feed-legends';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { MapsFeedCanvas } from './maps-feed-canvas';

export async function fetchPins(_signal: AbortSignal): Promise<MapsPinMarker[]> {
  return CONFLICT_SITES.map((site) => ({
    id: site.id,
    lat: site.lat,
    lng: site.lng,
    label: site.name,
    detail: `${site.severity} · ${site.country} · ${site.type}`,
    color: CONFLICT_SEVERITY_COLOR[site.severity],
    size: site.severity === 'critical' ? 12 : site.severity === 'high' ? 10 : 8,
  }));
}

export function MapsConflict() {
  return (
    <MapsFeedCanvas
      title="Conflict Sites"
      loadingLabel="Loading conflict pins…"
      readyMeta={(n) => `${n} curated OSINT sites · Maps static list`}
      emptyTitle="No conflict sites"
      emptyBody="The Maps conflict pin list is empty."
      fetchPins={fetchPins}
      fitMaxZoom={5}
      legendLayerId="conflict"
      legend={conflictFeedLegend()}
    />
  );
}
