'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { eonetEventsToPins } from '../lib/eonet-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsVolcanoes() {
  return (
    <MapsFeedCanvas
      title="Volcanoes"
      loadingLabel="Loading volcano events…"
      readyMeta={(n) => `${n} open volcano events · NASA EONET`}
      emptyTitle="No open volcano events"
      emptyBody="EONET volcano category has no open events in the last year."
      sourceHref="https://volcano.si.edu/"
      sourceLabel="Smithsonian GVP"
      fetchPins={async (signal) => {
        const res = await fetch(MAPS_PUBLIC_FEEDS.volcanoes, { signal });
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
        return eonetEventsToPins(data.events ?? [], { color: '#7c3aed' });
      }}
    />
  );
}
