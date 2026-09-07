'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { eonetEventsToPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const res = await fetch(MAPS_PUBLIC_FEEDS.volcanoes, { signal });
  if (!res.ok) throw new Error(`EONET volcanoes ${res.status}`);
  return eonetEventsToPins(await res.json(), '#7c3aed');
}

export function MapsVolcanoes() {
  return (
    <MapsFeedCanvas
      title="Volcanoes"
      loadingLabel="Loading volcano events…"
      readyMeta={(n) => `${n} open volcano events (90d) · NASA EONET`}
      emptyTitle="No open volcano events"
      emptyBody="NASA EONET has no open volcano events in the last 90 days."
      sourceHref="https://eonet.gsfc.nasa.gov/"
      sourceLabel="EONET"
      fetchPins={fetchPins}
    />
  );
}
