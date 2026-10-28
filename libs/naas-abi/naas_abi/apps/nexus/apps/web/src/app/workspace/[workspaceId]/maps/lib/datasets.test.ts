import { describe, expect, it } from 'vitest';

import {
  getMapsDataset,
  getMapsDatasetsByGroup,
  isMapsDatasetId,
  mapsCustomFeedUrl,
  MAPS_DATASETS,
  MAPS_PUBLIC_FEEDS,
} from './datasets';
import { CONFLICT_SITES } from './conflict-sites';

const ENVIRONMENT_IDS = [
  'gdacs',
  'earthquakes',
  'wildfires',
  'volcanoes',
  'tropical-storms',
  'nws-alerts',
  'eonet-all',
  'temperature',
  'openaq',
] as const;

const SIGINT_IDS = ['flights', 'ais', 'iss'] as const;

const SITUATION_IDS = ['conflict', 'gulf-strikes', 'news'] as const;

const BUILTIN_IDS = [...ENVIRONMENT_IDS, ...SIGINT_IDS, ...SITUATION_IDS] as const;

describe('MAPS_DATASETS taxonomy', () => {
  it('groups built-in layers by Environment, SIGINT, and Situation', () => {
    expect(getMapsDatasetsByGroup('Environment').map((d) => d.id)).toEqual([...ENVIRONMENT_IDS]);
    expect(getMapsDatasetsByGroup('SIGINT').map((d) => d.id)).toEqual([...SIGINT_IDS]);
    expect(getMapsDatasetsByGroup('situation').map((d) => d.id)).toEqual([...SITUATION_IDS]);
    expect(getMapsDatasetsByGroup('Custom')).toEqual([]);
  });

  it('includes every built-in id once (Custom empty upstream)', () => {
    const ids = MAPS_DATASETS.filter((d) => d.group !== 'Custom').map((d) => d.id);
    expect([...ids].sort()).toEqual([...BUILTIN_IDS].sort());
  });

  it('registers every dataset id', () => {
    for (const dataset of MAPS_DATASETS) {
      expect(isMapsDatasetId(dataset.id)).toBe(true);
    }
    expect(isMapsDatasetId('not-a-dataset')).toBe(false);
    expect(MAPS_DATASETS.filter((d) => d.group !== 'Custom')).toHaveLength(BUILTIN_IDS.length);
  });
});

describe('getMapsDataset', () => {
  it('returns a built-in dataset', () => {
    expect(getMapsDataset('iss')?.title).toBe('ISS');
  });
});

describe('MAPS_PUBLIC_FEEDS', () => {
  it('maps conflict to static list size', () => {
    expect(getMapsDataset('conflict')).toBeTruthy();
    expect(CONFLICT_SITES.length).toBeGreaterThan(0);
  });

  it('exposes proxy routes for upstream feeds', () => {
    expect(MAPS_PUBLIC_FEEDS.firms).toBe('/api/maps/firms');
    expect(MAPS_PUBLIC_FEEDS.earthquakes).toMatch(/earthquake|usgs/i);
    expect(MAPS_PUBLIC_FEEDS.gdacs).toBe('/api/maps/gdacs');
    expect(MAPS_PUBLIC_FEEDS.openaq).toBe('/api/maps/openaq');
    expect(MAPS_PUBLIC_FEEDS.nwsAlerts).toBe('/api/maps/nws');
    expect(MAPS_PUBLIC_FEEDS.tropicalStorms).toBe('/api/maps/nhc');
    expect(MAPS_PUBLIC_FEEDS.flights).toBe('/api/maps/flights');
    expect(MAPS_PUBLIC_FEEDS.gulfStrikes).toBe('/api/maps/gulf-strikes');
    expect(MAPS_PUBLIC_FEEDS.news).toBe('/api/maps/news');
    expect(MAPS_PUBLIC_FEEDS.ais).toBe('/api/maps/ais');
    expect(MAPS_PUBLIC_FEEDS.iss).toBe('/api/maps/iss');
  });

  it('routes Custom datasets through the authed /api/maps/custom proxy', () => {
    expect(mapsCustomFeedUrl('acme-sites', 'ws-1')).toBe(
      '/api/maps/custom/acme-sites?workspace_id=ws-1',
    );
    expect(mapsCustomFeedUrl('acme sites/../x', 'ws 1')).toBe(
      '/api/maps/custom/acme%20sites%2F..%2Fx?workspace_id=ws+1',
    );
  });
});
