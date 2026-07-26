'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchAisPins(signal: AbortSignal): Promise<MapsPinMarker[]> {
  const res = await fetch(MAPS_PROXY_ROUTES.ais, { signal });
  const data = (await res.json()) as {
    pins?: MapsPinMarker[];
    needsKey?: boolean;
    message?: string;
    error?: string;
  };
  if (data.needsKey) {
    // Honest empty canvas: dataset registered, key required for live AIS.
    return [];
  }
  if (!res.ok) {
    throw new Error(data.error ?? `AIS ${res.status}`);
  }
  return (data.pins ?? []).filter(
    (p) => Number.isFinite(p.lat) && Number.isFinite(p.lng),
  );
}

export function MapsAis() {
  return (
    <MapsFeedCanvas
      title="AIS ships"
      loadingLabel="Checking AIS provider…"
      readyMeta={(n) => `${n} vessels · AIS`}
      emptyTitle="Needs AIS API key"
      emptyBody="Set AISSTREAM_API_KEY (or AIS_API_KEY) on nexus-web to populate live vessel pins. Dataset is registered for sidebar toggle; free AIS HTTP snapshots are not wired yet."
      sourceHref="https://aisstream.io/"
      sourceLabel="aisstream.io"
      fetchPins={fetchAisPins}
    />
  );
}
