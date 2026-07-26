'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsGdacs() {
  return (
    <MapsFeedCanvas
      title="GDACS"
      loadingLabel="Loading GDACS alerts…"
      readyMeta={(n) => `${n} multi-hazard alerts · UN GDACS`}
      emptyTitle="No active GDACS alerts"
      emptyBody="The GDACS map feed returned no geocoded events."
      sourceHref="https://www.gdacs.org/"
      sourceLabel="gdacs.org"
      fetchPins={(signal) =>
        fetchMapsProxyPins(MAPS_PROXY_ROUTES.gdacs, signal)
      }
    />
  );
}
