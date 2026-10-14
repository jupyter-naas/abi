'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { gulfStrikesFeedLegend } from '../lib/maps-layer-feed-legends';
import { MapsFeedCanvas } from './maps-feed-canvas';

export async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(
    MAPS_PUBLIC_FEEDS.gulfStrikes,
    signal,
  );
  return pins;
}

export function MapsGulfStrikes() {
  return (
    <MapsFeedCanvas
      title="Gulf Strikes"
      loadingLabel="Loading Gulf strike headlines…"
      readyMeta={(n) =>
        `${n} strike reports · BBC / Al Jazeera / Reuters (theater filter)`
      }
      emptyTitle="No strike headlines right now"
      emptyBody="RSS feeds returned no Gulf / Iran / Israel strike-matched headlines. Conflict Sites still shows curated infrastructure pins."
      sourceHref="https://www.bbc.com/news/world/middle_east"
      sourceLabel="BBC Middle East"
      fetchPins={fetchPins}
      refreshMs={120000}
      fitMaxZoom={6}
      legendLayerId="gulf-strikes"
      legend={gulfStrikesFeedLegend()}
    />
  );
}
