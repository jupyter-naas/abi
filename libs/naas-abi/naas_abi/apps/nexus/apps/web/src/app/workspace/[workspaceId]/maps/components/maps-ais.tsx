'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

let lastReason =
  'No free keyless AIS feed is configured. This layer is reserved for a licensed source.';

async function fetchPins(signal: AbortSignal) {
  const { pins, reason } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.ais, signal);
  if (reason) lastReason = reason;
  return pins;
}

export function MapsAis() {
  return (
    <MapsFeedCanvas
      title="AIS Vessels"
      loadingLabel="Checking AIS source…"
      readyMeta={(n) => `${n} vessels`}
      emptyTitle="AIS not configured"
      emptyBody={lastReason}
      sourceHref="https://aisstream.io/"
      sourceLabel="AISStream (registration)"
      fetchPins={fetchPins}
    />
  );
}
