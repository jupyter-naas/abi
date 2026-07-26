'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { eonetEventsToPins } from '../lib/eonet-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsEonet() {
  return (
    <MapsFeedCanvas
      title="EONET"
      loadingLabel="Loading NASA EONET…"
      readyMeta={(n) => `${n} open natural events (all categories, 30d)`}
      emptyTitle="No open EONET events"
      emptyBody="NASA EONET returned no open events for the last 30 days."
      sourceHref="https://eonet.gsfc.nasa.gov/"
      sourceLabel="EONET"
      fetchPins={async (signal) => {
        const res = await fetch(MAPS_PUBLIC_FEEDS.eonet, { signal });
        if (!res.ok) throw new Error(`EONET ${res.status}`);
        const data = (await res.json()) as {
          events?: Array<{
            id?: string;
            title?: string;
            categories?: Array<{ id?: string; title?: string }>;
            geometry?: Array<{
              date?: string;
              type?: string;
              coordinates?: number[];
            }>;
          }>;
        };
        return eonetEventsToPins(data.events ?? []);
      }}
      legend={
        <div className="maps-legend">
          <div className="maps-legend__title">Categories</div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
            <span>Wildfires</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#7c3aed' }} />
            <span>Volcanoes</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#2563eb' }} />
            <span>Storms / other</span>
          </div>
        </div>
      }
    />
  );
}
