'use client';

import {
  CONFLICT_SEVERITY_COLOR,
  CONFLICT_SITES,
} from '../lib/conflict-sites';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { MapsFeedCanvas } from './maps-feed-canvas';

const PINS: MapsPinMarker[] = CONFLICT_SITES.map((site) => ({
  id: site.id,
  lat: site.lat,
  lng: site.lng,
  label: site.name,
  detail: `${site.country} · ${site.severity} · ${site.type}`,
  color: CONFLICT_SEVERITY_COLOR[site.severity],
  size: site.severity === 'critical' ? 12 : 10,
}));

export function MapsConflict() {
  return (
    <MapsFeedCanvas
      title="Conflict pins"
      loadingLabel="Loading OSINT sites…"
      readyMeta={(n) => `${n} static OSINT sites · WSR v1 (no ACLED key)`}
      emptyTitle="No conflict sites"
      emptyBody="Static OSINT list failed to load."
      sourceHref="https://www.iaea.org/"
      sourceLabel="Public OSINT basis"
      fitMaxZoom={6}
      fetchPins={async () => PINS}
      legend={
        <div className="maps-legend">
          <div className="maps-legend__title">Severity</div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
            <span>Critical</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#ea580c' }} />
            <span>High</span>
          </div>
          <div className="maps-legend__row">
            <span className="maps-legend__dot" style={{ background: '#ca8a04' }} />
            <span>Medium</span>
          </div>
        </div>
      }
    />
  );
}
