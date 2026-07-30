'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(
    MAPS_PUBLIC_FEEDS.ontologistNorthAmerica,
    signal,
  );
  return pins;
}

export function MapsOntologistNorthAmerica() {
  return (
    <MapsFeedCanvas
      title="Ontologist, North America"
      loadingLabel="Loading Ontologist pins…"
      readyMeta={(n) =>
        `${n} Ontologists · Sanax observation 2026-07-31 · Zen intelligence`
      }
      emptyTitle="No Ontologist pins"
      emptyBody="Run the Zen intelligence pipeline (make intelligence-pipeline) to build this layer from the Sanax export."
      sourceHref="/api/intelligence/ontologist-north-america"
      sourceLabel="Intelligence feed"
      fetchPins={fetchPins}
      fitMaxZoom={4}
    />
  );
}
