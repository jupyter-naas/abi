'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
  const { pins } = await fetchMapsFeedPins(MAPS_PUBLIC_FEEDS.news, signal);
  return pins;
}

export function MapsNews() {
  return (
    <MapsFeedCanvas
      title="News"
      loadingLabel="Loading world news…"
      readyMeta={(n) => `${n} headlines · BBC / Al Jazeera / Reuters`}
      emptyTitle="No geocoded headlines"
      emptyBody="RSS feeds returned no region-matched headlines right now."
      sourceHref="https://www.bbc.com/news/world"
      sourceLabel="BBC World"
      fetchPins={fetchPins}
      refreshMs={120000}
    />
  );
}
