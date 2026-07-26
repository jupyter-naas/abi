'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.iss, signal);
  return pins;
}

export function MapsIss() {
  return (
    <MapsFeedCanvas
      title="ISS"
      loadingLabel="Locating ISS…"
      readyMeta={() => 'International Space Station · open-notify'}
      emptyTitle="ISS position unavailable"
      emptyBody="open-notify did not return a current ISS position."
      sourceHref="http://open-notify.org/Open-Notify-API/ISS-Location-Now/"
      sourceLabel="open-notify"
      fetchPins={fetchPins}
      refreshMs={15000}
      fitMaxZoom={3}
    />
  );
}
