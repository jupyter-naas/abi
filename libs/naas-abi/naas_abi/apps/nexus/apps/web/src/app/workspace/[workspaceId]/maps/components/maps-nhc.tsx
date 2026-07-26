'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsNhc() {
  return (
    <MapsFeedCanvas
      title="Tropical storms"
      loadingLabel="Loading NHC storms…"
      readyMeta={(n) => `${n} active tropical cyclones · NOAA NHC`}
      emptyTitle="No active tropical storms"
      emptyBody="NHC CurrentStorms.json has no active cyclones right now (quiet season is normal)."
      sourceHref="https://www.nhc.noaa.gov/"
      sourceLabel="nhc.noaa.gov"
      fitMaxZoom={3}
      fetchPins={(signal) => fetchMapsProxyPins(MAPS_PROXY_ROUTES.nhc, signal)}
    />
  );
}
