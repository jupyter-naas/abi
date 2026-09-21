'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins, withMapsView } from '../lib/maps-feed';
import type { MapsFeedView } from '../lib/maps-view';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchFeed(signal: AbortSignal, view?: MapsFeedView) {
  return fetchMapsFeedPins(withMapsView(MAPS_PUBLIC_FEEDS.ais, view), signal);
}

export function MapsAis() {
  return (
    <MapsFeedCanvas
      title="AIS Vessels"
      loadingLabel="Checking AIS source…"
      readyMeta={(n) => `${n} vessels`}
      emptyTitle="AIS not configured"
      emptyBody="No free keyless AIS feed is configured. This layer is reserved for a licensed source."
      sourceHref="https://aisstream.io/"
      sourceLabel="AISStream"
      fetchPins={fetchFeed}
      refreshMs={10000}
      viewportBound
    />
  );
}
