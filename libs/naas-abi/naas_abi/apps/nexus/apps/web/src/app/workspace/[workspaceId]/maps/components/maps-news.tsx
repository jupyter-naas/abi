'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsNews() {
  return (
    <MapsFeedCanvas
      title="News geopin"
      loadingLabel="Loading headlines…"
      readyMeta={(n) => `${n} geocoded headlines · BBC + Al Jazeera`}
      emptyTitle="No geocoded headlines"
      emptyBody="RSS feeds returned no titles matching the region keyword table."
      sourceHref="https://www.bbc.com/news/world"
      sourceLabel="BBC World"
      refreshMs={180000}
      fetchPins={(signal) =>
        fetchMapsProxyPins(MAPS_PROXY_ROUTES.news, signal)
      }
    />
  );
}
