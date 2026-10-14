'use client';

import type { ReactNode } from 'react';
import { CONFLICT_SEVERITY_COLOR } from './conflict-sites';

export function earthquakesFeedLegend(): ReactNode {
  return (
    <div className="maps-legend__row">
      <span className="maps-legend__dot" style={{ background: '#ea580c' }} />
      <span>M≥2.5 · past 24h · size ∝ magnitude</span>
    </div>
  );
}

export function temperatureFeedLegend(): ReactNode {
  return (
    <>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: '#2563eb' }} />
        <span>Cold (≤ 0)</span>
      </div>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: '#4ade80' }} />
        <span>Mild (10-18)</span>
      </div>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: '#f97316' }} />
        <span>Warm (26-32)</span>
      </div>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
        <span>Hot (&gt; 32)</span>
      </div>
    </>
  );
}

export function wildfiresFeedLegend(options?: { firmsEnabled?: boolean }): ReactNode {
  const firmsEnabled = options?.firmsEnabled ?? false;
  return (
    <>
      {firmsEnabled ? (
        <div className="maps-legend__row">
          <span className="maps-legend__dot" style={{ background: '#f97316' }} />
          <span>NASA FIRMS VIIRS active fires (last 24h)</span>
        </div>
      ) : null}
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
        <span>EONET named open wildfires (last 7 days)</span>
      </div>
    </>
  );
}

export function conflictFeedLegend(): ReactNode {
  return (
    <>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: CONFLICT_SEVERITY_COLOR.critical }} />
        <span>Critical</span>
      </div>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: CONFLICT_SEVERITY_COLOR.high }} />
        <span>High</span>
      </div>
      <div className="maps-legend__row">
        <span className="maps-legend__dot" style={{ background: CONFLICT_SEVERITY_COLOR.medium }} />
        <span>Medium</span>
      </div>
    </>
  );
}

export function gulfStrikesFeedLegend(): ReactNode {
  return (
    <>
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
        <span>Elevated</span>
      </div>
    </>
  );
}

export function mapsLayerFeedLegend(
  layerId: string,
  options?: { firmsEnabled?: boolean },
): ReactNode | undefined {
  switch (layerId) {
    case 'earthquakes':
      return earthquakesFeedLegend();
    case 'temperature':
      return temperatureFeedLegend();
    case 'wildfires':
      return wildfiresFeedLegend(options);
    case 'conflict':
      return conflictFeedLegend();
    case 'gulf-strikes':
      return gulfStrikesFeedLegend();
    default:
      return undefined;
  }
}

export function mapsLayerFeedLegendsFor(layerIds: string[]): Record<string, ReactNode> {
  const out: Record<string, ReactNode> = {};
  for (const id of layerIds) {
    const legend = mapsLayerFeedLegend(id);
    if (legend) out[id] = legend;
  }
  return out;
}
