'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

async function fetchPins(signal: AbortSignal) {
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
      legend={
        <div className="maps-legend">
          <span className="maps-legend__title">Severity</span>
          <div className="maps-legend__row">
            <span
              className="maps-legend__dot"
              style={{ background: '#dc2626' }}
            />
            <span>Critical</span>
          </div>
          <div className="maps-legend__row">
            <span
              className="maps-legend__dot"
              style={{ background: '#ea580c' }}
            />
            <span>High</span>
          </div>
          <div className="maps-legend__row">
            <span
              className="maps-legend__dot"
              style={{ background: '#ca8a04' }}
            />
            <span>Elevated</span>
          </div>
        </div>
      }
    />
  );
}
