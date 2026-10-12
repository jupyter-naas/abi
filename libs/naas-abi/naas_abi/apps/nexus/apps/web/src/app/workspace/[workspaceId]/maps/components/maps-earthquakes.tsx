'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { earthquakesFeedLegend } from '../lib/maps-layer-feed-legends';
import { MapsFeedCanvas } from './maps-feed-canvas';

/**
 * USGS earthquakes (M≥2.5, past day) as pins, so the layer can join the
 * combined map as well as open on its own.
 */
export async function fetchPins(signal: AbortSignal): Promise<MapsPinMarker[]> {
  const res = await fetch(MAPS_PUBLIC_FEEDS.earthquakes, { signal });
  if (!res.ok) throw new Error(`USGS ${res.status}`);
  const gj = (await res.json()) as {
    features?: Array<{
      id?: string;
      properties?: { mag?: number; place?: string };
      geometry?: { coordinates?: number[] };
    }>;
  };
  const pins: MapsPinMarker[] = [];
  for (const feature of gj.features ?? []) {
    const coords = feature.geometry?.coordinates;
    if (!coords || coords.length < 2) continue;
    const [lng, lat] = coords;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const mag = feature.properties?.mag ?? 0;
    pins.push({
      id: String(feature.id ?? `${lat},${lng}`),
      lat,
      lng,
      label: `M${mag.toFixed(1)} · ${feature.properties?.place ?? 'Earthquake'}`,
      color: '#ea580c',
      size: Math.min(18, Math.max(8, 6 + mag * 2)),
    });
  }
  return pins;
}

/** USGS earthquakes (M≥2.5, past day). Maps-owned Public layer. */
export function MapsEarthquakes() {
  return (
    <MapsFeedCanvas
      title="Earthquakes"
      loadingLabel="Loading USGS…"
      readyMeta={(n) => `${n} events (M≥2.5, past day) · USGS`}
      sourceHref={MAPS_PUBLIC_FEEDS.earthquakes}
      sourceLabel="USGS"
      fetchPins={fetchPins}
      fitMaxZoom={5}
      legendLayerId="earthquakes"
      legend={earthquakesFeedLegend()}
    />
  );
}
