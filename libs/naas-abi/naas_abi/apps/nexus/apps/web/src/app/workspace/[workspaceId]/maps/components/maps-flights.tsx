'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins, withMapsView } from '../lib/maps-feed';
import type { MapsFeedView } from '../lib/maps-view';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchFeed(signal: AbortSignal, view?: MapsFeedView) {
  return fetchMapsFeedPins(withMapsView(MAPS_PUBLIC_FEEDS.flights, view), signal);
}

export function MapsFlights() {
  return (
    <MapsFeedCanvas
      title="Flights"
      loadingLabel="Loading aircraft…"
      readyMeta={(n) => `${n} aircraft`}
      emptyTitle="No aircraft in view"
      emptyBody="Zoom in over a busy region to load live aircraft, or wait for the global sample."
      sourceHref="https://adsb.lol/"
      sourceLabel="adsb.lol / airplanes.live"
      fetchPins={fetchFeed}
      refreshMs={30000}
      viewportBound
    />
  );
}
