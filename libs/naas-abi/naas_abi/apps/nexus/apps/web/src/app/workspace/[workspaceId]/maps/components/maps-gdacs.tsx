'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.gdacs, signal);
  return pins;
}

export function MapsGdacs() {
  return (
    <MapsFeedCanvas
      title="GDACS"
      loadingLabel="Loading GDACS hazards…"
      readyMeta={(n) => `${n} multi-hazard events · GDACS`}
      emptyTitle="No GDACS events"
      emptyBody="The GDACS MAP feed returned no active events."
      sourceHref="https://www.gdacs.org/"
      sourceLabel="GDACS"
      fetchPins={fetchPins}
    />
  );
}
