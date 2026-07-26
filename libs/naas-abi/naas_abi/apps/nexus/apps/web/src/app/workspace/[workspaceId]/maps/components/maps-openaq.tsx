'use client';

import { MAPS_PROXY_ROUTES } from '../lib/datasets';
import { fetchMapsProxyPins } from '../lib/maps-proxy-pins';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsOpenaq() {
  return (
    <MapsFeedCanvas
      title="Air quality"
      loadingLabel="Loading air quality…"
      readyMeta={(n) => `${n} PM2.5 samples · OpenAQ / Open-Meteo`}
      emptyTitle="No air quality samples"
      emptyBody="OpenAQ and Open-Meteo returned no mappable PM2.5 points."
      sourceHref="https://openaq.org/"
      sourceLabel="openaq.org"
      fetchPins={(signal) =>
        fetchMapsProxyPins(MAPS_PROXY_ROUTES.openaq, signal)
      }
      legend={
        <div className="maps-legend">
          <div className="maps-legend__title">PM2.5 (µg/m³)</div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#16a34a' }} />
            <span>≤ 12 good</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#ca8a04' }} />
            <span>≤ 35 moderate</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#ea580c' }} />
            <span>≤ 55 unhealthy (sensitive)</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
            <span>&gt; 55 unhealthy+</span>
          </div>
        </div>
      }
    />
  );
}
