'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(
    MAPS_PUBLIC_FEEDS.tropicalStorms,
    signal,
  );
  return pins;
}

export function MapsTropicalStorms() {
  return (
    <MapsFeedCanvas
      title="Tropical Storms"
      loadingLabel="Loading NHC storms…"
      readyMeta={(n) => `${n} active cyclone${n === 1 ? '' : 's'} · NHC`}
      emptyTitle="No active tropical storms"
      emptyBody="NHC CurrentStorms reports no active named cyclones right now."
      sourceHref="https://www.nhc.noaa.gov/"
      sourceLabel="NHC"
      fetchPins={fetchPins}
      fitMaxZoom={4}
    />
  );
}
