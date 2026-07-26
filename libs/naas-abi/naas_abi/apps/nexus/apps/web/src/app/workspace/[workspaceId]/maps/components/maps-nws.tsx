'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsNws() {
  return (
    <MapsFeedCanvas
      title="NWS alerts"
      loadingLabel="Loading NWS alerts…"
      readyMeta={(n) => `${n} active US weather alerts · NWS`}
      emptyTitle="No active NWS alerts"
      emptyBody="api.weather.gov returned no active alerts with geometry."
      sourceHref="https://www.weather.gov/"
      sourceLabel="weather.gov"
      fitMaxZoom={4}
      fetchPins={(signal) => fetchMapsProxyPins(MAPS_PROXY_ROUTES.nws, signal)}
    />
  );
}
