'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

let lastReason =
  'OpenAQ v3 requires a free API key. Set OPENAQ_API_KEY on the Nexus web host.';

async function fetchPins(signal: AbortSignal) {
  const { pins, reason } = await fetchMapsFeedPins(
    MAPS_PUBLIC_FEEDS.openaq,
    signal,
  );
  if (reason) lastReason = reason;
  return pins;
}

export function MapsOpenaq() {
  return (
    <MapsFeedCanvas
      title="Air Quality"
      loadingLabel="Loading air quality…"
      readyMeta={(n) => `${n} PM2.5 samples · OpenAQ / Open-Meteo`}
      emptyTitle="No air quality samples"
      emptyBody={lastReason}
      sourceHref="https://openaq.org/"
      sourceLabel="openaq.org"
      fetchPins={fetchPins}
    />
  );
}
