'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { eonetEventsToPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const res = await fetch(MAPS_PUBLIC_FEEDS.eonetAll, { signal });
  if (!res.ok) throw new Error(`EONET ${res.status}`);
  return eonetEventsToPins(await res.json(), '#7c3aed');
}

export function MapsEonetAll() {
  return (
    <MapsFeedCanvas
      title="EONET Events"
      loadingLabel="Loading NASA EONET…"
      readyMeta={(n) => `${n} open events (30d) · NASA EONET`}
      emptyTitle="No open EONET events"
      emptyBody="NASA EONET returned no open events for the last 30 days."
      sourceHref="https://eonet.gsfc.nasa.gov/"
      sourceLabel="EONET"
      fetchPins={fetchPins}
    />
  );
}
