'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsFlights() {
  return (
    <MapsFeedCanvas
      title="Flights"
      loadingLabel="Loading aircraft…"
      readyMeta={(n) => `${n} aircraft · airplanes.live (regional samples)`}
      emptyTitle="No aircraft in sample regions"
      emptyBody="airplanes.live returned no positions for the sampled regions."
      sourceHref="https://airplanes.live/"
      sourceLabel="airplanes.live"
      refreshMs={45000}
      fetchPins={(signal) =>
        fetchMapsProxyPins(MAPS_PROXY_ROUTES.flights, signal)
      }
      legend={
        <div className="maps-legend">
          <div className="maps-legend__title">Legend</div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#2563eb' }} />
            <span>Civil</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
            <span>Military flag</span>
          </div>
        </div>
      }
    />
  );
}
