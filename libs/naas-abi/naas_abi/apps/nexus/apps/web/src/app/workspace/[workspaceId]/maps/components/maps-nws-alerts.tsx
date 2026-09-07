'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.nwsAlerts, signal);
  return pins;
}

export function MapsNwsAlerts() {
  return (
    <MapsFeedCanvas
      title="NWS Alerts"
      loadingLabel="Loading NWS alerts…"
      readyMeta={(n) => `${n} active alerts (centroids) · NWS`}
      emptyTitle="No active NWS alerts"
      emptyBody="api.weather.gov returned no active alerts with geometry."
      sourceHref="https://www.weather.gov/"
      sourceLabel="NWS"
      fetchPins={fetchPins}
      fitMaxZoom={6}
    />
  );
}
