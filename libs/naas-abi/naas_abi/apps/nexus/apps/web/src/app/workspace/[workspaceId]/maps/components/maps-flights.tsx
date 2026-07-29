'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.flights, signal);
  return pins;
}

export function MapsFlights() {
  return (
    <MapsFeedCanvas
      title="Flights"
      loadingLabel="Loading aircraft…"
      readyMeta={(n) => `${n} aircraft (global sample) · airplanes.live`}
      emptyTitle="No aircraft in sample tiles"
      emptyBody="airplanes.live returned no positions for the Maps sample regions."
      sourceHref="https://airplanes.live/"
      sourceLabel="airplanes.live"
      fetchPins={fetchPins}
      refreshMs={45000}
      fitMaxZoom={4}
    />
  );
}
