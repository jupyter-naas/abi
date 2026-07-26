'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsIss() {
  return (
    <MapsFeedCanvas
      title="ISS"
      loadingLabel="Locating ISS…"
      readyMeta={() => 'International Space Station · open-notify'}
      emptyTitle="ISS position unavailable"
      emptyBody="open-notify did not return a current ISS position."
      sourceHref="http://open-notify.org/Open-Notify-API/ISS-Location-Now/"
      sourceLabel="open-notify"
      refreshMs={15000}
      fitMaxZoom={3}
      fetchPins={(signal) => fetchMapsProxyPins(MAPS_PROXY_ROUTES.iss, signal)}
    />
  );
}
